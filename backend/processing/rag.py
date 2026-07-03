import chromadb
import json
import os
from sentence_transformers import SentenceTransformer
from config import settings

embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
client = chromadb.PersistentClient(path=settings.chroma_db_path)
collection = client.get_or_create_collection(
    name="folders",
    metadata={"hnsw:space": "cosine"}
)

STOP_WORDS = {
    "a", "an", "the", "for", "of", "in", "on", "at", "to", "and",
    "or", "is", "are", "me", "my", "give", "make", "create", "want",
    "need", "please", "i", "can", "you", "generate", "poster",
    "template", "design", "get", "send", "show"
}

def health_check() -> bool:
    return collection.count() > 0

def extract_chunks(query: str) -> list[str]:
    query = query.strip()
    words = query.split()
    chunks = {query}
    for word in words:
        w = word.lower().strip(".,!?")
        if w and w not in STOP_WORDS and len(w) > 2:
            chunks.add(w)
    for i in range(len(words) - 1):
        chunks.add(f"{words[i]} {words[i+1]}".lower())
    for i in range(len(words) - 2):
        chunks.add(f"{words[i]} {words[i+1]} {words[i+2]}".lower())
    return list(chunks)

def get_all_folders_from_db() -> list[dict]:
    results = collection.get(include=["documents"])
    folders = []
    for doc in results["documents"]:
        data = json.loads(doc)
        folders.append({
            "folder": data["folder"],
            "tags": data.get("tags", [])
        })
    return folders

def _score_with_boost(query: str, top_k: int = 3) -> list[dict]:
    query_words = set(query.lower().split())
    chunks = extract_chunks(query)
    best_scores: dict[str, dict] = {}

    for chunk in chunks:
        if not chunk.strip():
            continue
        try:
            vector = embedder.encode(chunk).tolist()
            results = collection.query(
                query_embeddings=[vector],
                n_results=collection.count(),
                include=["documents", "distances"]
            )
            for doc, dist in zip(results["documents"][0], results["distances"][0]):
                semantic = round(1 - dist, 3)
                folder_data = json.loads(doc)
                fid = folder_data["folder"]
                if semantic > best_scores.get(fid, {}).get("semantic", 0):
                    best_scores[fid] = {"semantic": semantic, "data": folder_data}
        except Exception:
            continue

    matches = []
    for fid, info in best_scores.items():
        semantic = info["semantic"]
        folder_data = info["data"]
        tag_words = set(" ".join(folder_data.get("tags", [])).lower().split())
        folder_words = set(fid.lower().replace("_", " ").split())
        matched = query_words & (tag_words | folder_words)
        boost = 0.25 if matched else 0.0
        final = round(semantic + boost, 3)
        matches.append({
            "folder": fid,
            "display_name": folder_data["display_name"],
            "templates": folder_data["templates"],
            "score": final,
            "semantic": semantic,
            "boost": boost
        })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches

def search_folder(query: str, top_k: int = 3) -> list[dict]:
    query = query[:settings.max_prompt_length]
    if collection.count() == 0:
        return []

    # Stage 1 — direct embedding + keyword boost
    matches = _score_with_boost(query, top_k)
    above_threshold = [m for m in matches if m["score"] >= settings.rag_score_threshold]

    if above_threshold:
        print(f"Stage 1 match: {above_threshold[0]['folder']} score={above_threshold[0]['score']}")
        return above_threshold[:top_k]

    print(f"Stage 1 failed (best={matches[0]['score'] if matches else 0}) — trying LLM Stage 2")

    # Stage 2 — constrained LLM classification
    try:
        from processing.llm import extract_folder_and_tags
        valid_folders = get_all_folders_from_db()
        extraction = extract_folder_and_tags(query, valid_folders)

        if not extraction or not extraction.get("folder"):
            print("Stage 2: LLM returned no match")
            return []

        folder_name = extraction["folder"]
        relevant_tags = extraction.get("relevant_tags", [])
        print(f"Stage 2: LLM matched folder={folder_name} tags={relevant_tags}")

        # Build enriched query — repeat tags twice for stronger signal
        enriched = (
            f"{folder_name} {folder_name} "
            f"{' '.join(relevant_tags)} {' '.join(relevant_tags)}"
        ).strip()
        print(f"Stage 2: enriched query = '{enriched}'")

        # Run Stage 1 again with enriched query
        enriched_matches = _score_with_boost(enriched, top_k)
        above_threshold = [m for m in enriched_matches if m["score"] >= settings.rag_score_threshold]

        if above_threshold:
            print(f"Stage 2 match: {above_threshold[0]['folder']} score={above_threshold[0]['score']}")
            return above_threshold[:top_k]

        print("Stage 2: enriched query still below threshold")
        return []

    except Exception as e:
        print(f"Stage 2 failed: {e}")
        return []
def load_template(folder_name: str, template_id: str) -> dict | None:
    overlay_path = os.path.join(
        settings.templates_dir, folder_name, template_id, "overlay.json"
    )
    if not os.path.exists(overlay_path):
        return None
    with open(overlay_path, encoding="utf-8") as f:
        return json.load(f)

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

def save_template_to_index(template: dict, folder_name: str) -> None:
    folder_path = os.path.join(settings.templates_dir, folder_name)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from indexer.indexer_templates import build_main_json, index_folder
    main = build_main_json(folder_path, folder_name)
    if main:
        index_folder(folder_name, main)