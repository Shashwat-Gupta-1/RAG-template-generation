# pyrefly: ignore [missing-import]
import chromadb
import json
import os
import sys
import openai
import re
import time
from datetime import date
from sentence_transformers import SentenceTransformer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings

# ── Globals ───────────────────────────────────────────────────────────────────
embedder = None
client = None
collection = None
llm_client = None


def _get_embedder():
    global embedder
    if embedder is None:
        embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return embedder


def _get_collection():
    global client, collection
    if collection is None:
        client = chromadb.PersistentClient(path=settings.chroma_db_path)
        collection = client.get_or_create_collection(
            name="folders",
            metadata={"hnsw:space": "cosine"}
        )
    return collection


def _get_llm_client():
    global llm_client
    if llm_client is None:
        llm_client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
            default_headers={
                "HTTP-Referer": "https://msfincap.com",
                "X-Title": "MS Fincap Template System"
            }
        )
    return llm_client

# ── Health check ──────────────────────────────────────────────────────────────
def health_check() -> bool:
    return _get_collection().count() > 0

# ── Get all folders from DB ───────────────────────────────────────────────────
def get_all_folders_from_db() -> list[dict]:
    results = _get_collection().get(include=["documents"])
    folders = []
    for doc in results["documents"]:
        data = json.loads(doc)
        folders.append({
            "folder": data["folder"],
            "display_name": data.get("display_name", ""),
            "tags": data.get("tags", []),
            "templates": data.get("templates", [])
        })
    return folders


# ── Step 1 — LLM generates tags from user query ───────────────────────────────
def generate_tags_from_query(query: str, valid_folders: list[dict]) -> str:

    folder_list = "\n".join([
        f"- {f['folder']}: [{', '.join(f['tags'])}]"
        for f in valid_folders
    ])

    system_prompt = f"""You are a search tag generator for a poster template system.

The user will describe what poster they want. Your job is to:
1. Identify which folder best matches their request
2. Return the folder name + its most relevant tags and related contextual terms as a space-separated string

Available folders and their tags:
{folder_list}

Rules:
1. Return ONLY a space-separated string of words. No JSON, no explanation, no punctuation.
2. Start by repeating the matched folder name(s) twice each (e.g. 'teej teej'). If the query matches multiple folders (e.g., 'rajasthan's festival' matches both 'teej' and 'gangaur'), repeat BOTH folder names twice (e.g., 'teej teej gangaur gangaur').
3. Special Case: Teej and Gangaur are both traditional Rajasthani festivals for women. If the user asks for a 'women's festival', 'beauty festival', 'festival of swings', 'puja/worship festival for women', or similar broad Rajasthani cultural terms without naming a specific one, it matches BOTH. You MUST repeat both folder names: 'teej teej gangaur gangaur'.
4. You may include highly relevant contextual terms, synonyms, or associated concepts (e.g. 'festival', 'celebration', 'women', 'rajasthan', 'finance') to help semantic matching.
5. If the query is broad or matches multiple folders, do NOT return 'unknown'. Generate tags and repeat the folder names for all related folders.

Example output: holi holi festival colours gulal spring celebration greeting
Example output: hiring hiring job recruitment college campus fresher placement
Example output: loan_offer loan_offer finance interest emi scheme nbfc"""

    for attempt in range(3):
        try:
            response = _get_llm_client().chat.completions.create(
                model=settings.free_model,
                max_tokens=60,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f'Generate search tags for: "{query}"'}
                ]
            )
            result = response.choices[0].message.content or ""
            result = result.strip().lower()
            result = result.replace(",", " ").replace(".", " ").replace("\n", " ")
            result = " ".join(result.split())

            print(f"LLM tags for '{query}': '{result}'")

            if result and result != "unknown":
                return result
            else:
                print("LLM returned unknown")
                return ""

        except Exception as e:
            print(f"LLM tag generation failed (attempt {attempt+1}): {e}")
            if attempt == 2:
                return ""
            time.sleep(1)

    return ""

# ── Step 2 — Embed tags and search ChromaDB ───────────────────────────────────
def search_by_tags(tags_string: str, top_k: int = 3) -> list[dict]:
    active_collection = _get_collection()
    if not tags_string or active_collection.count() == 0:
        return []

    vector = _get_embedder().encode(tags_string).tolist()
    results = active_collection.query(
        query_embeddings=[vector],
        n_results=active_collection.count(),
        include=["documents", "distances"]
    )

    matches = []
    for doc, dist in zip(results["documents"][0], results["distances"][0]):
        score = round(1 - dist, 3)
        folder_data = json.loads(doc)
        matches.append({
            "folder": folder_data["folder"],
            "display_name": folder_data["display_name"],
            "templates": folder_data["templates"],
            "score": score
        })

    # Boost folders that the LLM explicitly repeated twice in the tag string (e.g. "teej teej")
    words = tags_string.lower().replace(",", " ").split()
    boosted_folders = []
    for m in matches:
        folder_name = m["folder"].lower()
        if words.count(folder_name) >= 2:
            boosted_folders.append(m["folder"])

    if len(boosted_folders) == 1:
        # Only one folder was explicitly selected by the LLM.
        # Make it the absolute winner by boosting its score to 1.0 and setting others to 0.0.
        for m in matches:
            if m["folder"] == boosted_folders[0]:
                m["score"] = 1.0
            else:
                m["score"] = 0.0
    elif len(boosted_folders) > 1:
        # Multiple folders were explicitly selected by the LLM.
        # Boost all of them to 0.95 so they remain ambiguous.
        for m in matches:
            if m["folder"] in boosted_folders:
                m["score"] = 0.95

    matches.sort(key=lambda x: x["score"], reverse=True)
    above = [m for m in matches if m["score"] >= settings.rag_score_threshold]
    return above[:top_k]

# ── Main search function ──────────────────────────────────────────────────────
def search_folder(query: str, top_k: int = 3) -> list[dict]:
    query = query.strip()[:settings.max_prompt_length]

    if _get_collection().count() == 0:
        return []

    print(f"\nSearching: '{query}'")

    # Get all folders so LLM knows what's available
    valid_folders = get_all_folders_from_db()
    # LLM generates tags from the query
    tags_string = generate_tags_from_query(query, valid_folders)

    if not tags_string:
        print("LLM could not generate tags — no match")
        return []

    # Embed the tags and search
    results = search_by_tags(tags_string, top_k)

    if results:
        print(f"Match: {results[0]['folder']} score={results[0]['score']}")
    else:
        print(f"No match above threshold ({settings.rag_score_threshold})")

    return results

# ── Template loaders ──────────────────────────────────────────────────────────
def load_template(folder_name: str, template_id: str) -> dict | None:
    overlay_path = os.path.join(
        settings.templates_dir, folder_name, template_id, "overlay.json"
    )
    if not os.path.exists(overlay_path):
        return None
    with open(overlay_path, encoding="utf-8") as f:
        data = json.load(f)
    if data:
        data["template_id"] = template_id
    return data

def load_all_templates_in_folder(folder_name: str) -> list[dict]:
    main_path = os.path.join(settings.templates_dir, folder_name, "main.json")
    if not os.path.exists(main_path):
        return []
    with open(main_path, encoding="utf-8") as f:
        main = json.load(f)
    templates = []
    for tid in main.get("templates", []):
        t = load_template(folder_name, tid)
        if t:
            templates.append(t)
    return templates


def retrieve_template_overlay(prompt: str) -> dict | None:
    """Return the best matching overlay for bulk generation."""
    matches = search_folder(prompt, top_k=1)
    if not matches:
        return None

    best = matches[0]
    templates = best.get("templates") or []
    if not templates:
        return None

    template = load_template(best["folder"], templates[0])
    if template:
        template["folder"] = best["folder"]
    return template

def save_template_to_index(template: dict, folder_name: str) -> None:
    folder_path = os.path.join(settings.templates_dir, folder_name)
    from indexer.indexer_templates import build_main_json, index_folder
    main = build_main_json(folder_path, folder_name)
    if main:
        index_folder(folder_name, main)