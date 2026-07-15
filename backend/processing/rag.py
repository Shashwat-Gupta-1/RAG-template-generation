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
            "templates": data.get("templates", []),
            "season_months": data.get("season_months", None)
        })
    return folders

# ── Festival seasonality (month ranges for seasonal festivals) ────────────────
# ── Seasonality resolution helper ─────────────────────────────────────────────
def _get_festival_ranges(valid_folders: list[dict]) -> dict[str, tuple[int, int]]:
    """Build festival ranges dictionary dynamically from folders loaded from ChromaDB."""
    ranges = {}
    for f in valid_folders:
        months = f.get("season_months")
        if months and len(months) == 2:
            ranges[f["folder"]] = (int(months[0]), int(months[1]))
    return ranges


def _is_upcoming_query(query: str) -> bool:
    """Classify if the user query is asking for upcoming/next/future events using LLM reasoning."""
    system_prompt = (
        "You are an assistant that classifies user query intent. "
        "Determine if the user query is asking for an upcoming, next, future, soon-to-happen, "
        "or recently coming event or festival (e.g., 'upcoming festivals', 'next events', 'festivals coming soon', 'latest festival', 'aane wale tyohar', 'around the corner'). "
        "Answer with ONLY 'YES' or 'NO'. Do not include explanations, punctuation, or formatting."
    )
    try:
        response = _get_llm_client().chat.completions.create(
            model=settings.free_model,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": f'Query: "{query}"'}],
            temperature=0.0,
            max_tokens=5
        )
        ans = (response.choices[0].message.content or "").strip().upper()
        print(f"[rag] LLM upcoming classification for '{query}': {ans}")
        return "YES" in ans
    except Exception as e:
        print(f"Upcoming classification fallback to keywords: {e}")
        # fallback to safe keyword check
        keywords = {"upcoming", "next", "latest", "coming soon", "aane wala", "agla", "nazdik", "recent", "around the corner"}
        q = query.lower()
        return any(kw in q for kw in keywords)


def _is_past_query(query: str) -> bool:
    """Classify if the user query is asking for past, completed, or already occurred events using LLM reasoning."""
    system_prompt = (
        "You are an assistant that classifies user query intent. "
        "Determine if the user query is asking for past festivals, events that have already passed, "
        "occurred, ended, completed, or are over for this year (e.g., 'past festivals', 'festivals that have passed', "
        "'completed events', 'which festivals are over', 'ho chuke tyohar'). "
        "Answer with ONLY 'YES' or 'NO'. Do not include explanations, punctuation, or formatting."
    )
    try:
        response = _get_llm_client().chat.completions.create(
            model=settings.free_model,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": f'Query: "{query}"'}],
            temperature=0.0,
            max_tokens=5
        )
        ans = (response.choices[0].message.content or "").strip().upper()
        print(f"[rag] LLM past classification for '{query}': {ans}")
        return "YES" in ans
    except Exception as e:
        print(f"Past classification fallback to keywords: {e}")
        keywords = {"passed", "past", "already over", "over", "history", "completed", "expired", "gone", "ho chuke", "chale gaye", "purane"}
        q = query.lower()
        return any(kw in q for kw in keywords)


def _mentions_specific_festival(query: str, valid_folders: list[dict]) -> bool:
    """Return True if the query contains the name of any valid folder."""
    q = query.lower()
    for f in valid_folders:
        folder_name = f["folder"].lower()
        if folder_name in q:
            return True
    return False


def months_until_next(current_month: int, start: int, end: int) -> int:
    """Return months from current_month to the start of the festival season range.
    Returns 0 if current_month is inside the start-end range (inclusive)."""
    if start <= end:
        if start <= current_month <= end:
            return 0
    else:  # Crosses year boundary (e.g., 12 to 1)
        if current_month >= start or current_month <= end:
            return 0
    return (start - current_month) % 12


def _is_festival_past(current_month: int, start: int, end: int) -> bool:
    """Return True if the festival season has already fully passed for this year."""
    if start <= end:
        return current_month > end
    # For ranges crossing year boundary (e.g. 12 to 1), they don't fully pass during
    # the rest of the year since the next occurrence (Dec) starts within the year.
    return False


def _get_past_folders(valid_folders: list[dict], current_month: int, festival_ranges: dict, n: int) -> list[dict]:
    """Return the seasonal folders that have already passed relative to current_month, sorted by how recently they passed."""
    past_folders = []
    for f in valid_folders:
        folder_name = f["folder"].lower()
        if folder_name in festival_ranges:
            start, end = festival_ranges[folder_name]
            if _is_festival_past(current_month, start, end):
                # Calculate how many months ago it ended
                # e.g., if end is 4 (April) and current is 7 (July), months ago is (7 - 4) % 12 = 3
                months_ago = (current_month - end) % 12
                past_folders.append((f, months_ago))
    
    # Sort by how recently they passed (smaller months_ago first)
    past_folders.sort(key=lambda x: (x[1], x[0]["folder"]))
    return [item[0] for item in past_folders[:n]]


def _parse_upcoming_count(query: str, default: int = 3) -> int:
    """Parse number from query (e.g. 'top 5 upcoming' -> 5, 'show 4' -> 4)."""
    q = query.lower()
    num_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
    }
    # Look for digits (e.g., '5')
    digit_match = re.search(r"\b(\d+)\b", q)
    if digit_match:
        try:
            return int(digit_match.group(1))
        except ValueError:
            pass

    # Look for word-based numbers (e.g., 'five')
    for word, val in num_map.items():
        if re.search(r"\b" + word + r"\b", q):
            return val

    return default


def _get_top_n_upcoming_folders(valid_folders: list[dict], current_month: int, festival_ranges: dict, n: int) -> list[dict]:
    """Return the top n seasonal folders closest to current_month."""
    seasonal_folders = []
    for f in valid_folders:
        folder_name = f["folder"].lower()
        if folder_name in festival_ranges:
            start, end = festival_ranges[folder_name]
            dist = months_until_next(current_month, start, end)
            seasonal_folders.append((f, dist))
    
    # Sort primarily by proximity (months until next), secondarily by folder name
    seasonal_folders.sort(key=lambda x: (x[1], x[0]["folder"]))
    return [item[0] for item in seasonal_folders[:n]]


# ── Step 1 — LLM generates tags from user query ───────────────────────────────
def generate_tags_from_query(query: str, valid_folders: list[dict]) -> str:
    today = date.today()
    today_str = today.strftime("%B %d, %Y")  # e.g. "July 13, 2026"
    festival_ranges = _get_festival_ranges(valid_folders)

    # For 'upcoming' queries, strip out seasonal festivals that have already passed
    if _is_upcoming_query(query):
        past_folders = {
            f["folder"] for f in valid_folders
            if f["folder"].lower() in festival_ranges and
            _is_festival_past(today.month, *festival_ranges[f["folder"].lower()])
        }
        query_folders = [f for f in valid_folders if f["folder"] not in past_folders]
        print(f"[rag] upcoming query detected — removed past folders: {past_folders}")
    else:
        query_folders = valid_folders

    folder_list = "\n".join([
        f"- {f['folder']}: [{', '.join(f['tags'])}]"
        for f in query_folders
    ])

    # Approximate month ranges for each festival folder
    festival_calendar = """
Festival calendar ranges:
- teej: July to August (Monsoon season)
- gangaur: March to April (Spring season/Chaitra month)
- holi: February to March (Spring season)
- dussehra: September to October (Autumn/Festive season)
- new_year: December to January
- eid: varies by Islamic calendar (variable dates)"""

    system_prompt = f"""You are a search tag generator for a poster template system.
Today's date is {today_str}.

The user will describe what poster they want. Your job is to:
1. Identify which folder best matches their request
2. Return the folder name + its most relevant tags and related contextual terms as a space-separated string

Available folders and their tags:
{folder_list}
{festival_calendar}

Rules:
1. Return ONLY a space-separated string of words. No JSON, no explanation, no punctuation.
2. Start by repeating the matched folder name(s) twice each (e.g. 'teej teej'). If the query matches multiple folders (e.g., 'rajasthan's festival' matches both 'teej' and 'gangaur'), repeat BOTH folder names twice (e.g., 'teej teej gangaur gangaur').
3. Special Case: Teej and Gangaur are both traditional Rajasthani festivals for women. If the user asks for a 'women's festival', 'beauty festival', 'festival of swings', 'puja/worship festival for women', or similar broad Rajasthani cultural terms without naming a specific one, it matches BOTH. You MUST repeat both folder names: 'teej teej gangaur gangaur'.
4. You may include highly relevant contextual terms, synonyms, or associated concepts (e.g. 'festival', 'celebration', 'women', 'rajasthan', 'finance') to help semantic matching.
5. If the query is broad or matches multiple folders, do NOT return 'unknown'. Generate tags and repeat the folder names for all related folders.
6. IMPORTANT: If the user mentions 'upcoming', 'next', 'latest', 'coming', or 'soon', use today's date and the festival calendar above to ONLY match festivals that have NOT yet passed this year. Skip any festival whose season has already passed relative to today's date.

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
    festival_ranges = _get_festival_ranges(valid_folders)

    # Intercept generic 'upcoming festivals' queries (no specific folder mentioned)
    # and return the top n closest upcoming seasonal folders with equal score
    if _is_upcoming_query(query) and not _mentions_specific_festival(query, valid_folders):
        today = date.today()
        count = _parse_upcoming_count(query, default=3)
        top_n = _get_top_n_upcoming_folders(valid_folders, today.month, festival_ranges, count)
        results = []
        for f in top_n:
            results.append({
                "folder": f["folder"],
                "display_name": f.get("display_name", f["folder"].replace("_", " ").title()),
                "templates": f.get("templates", []),
                "score": 0.95
            })
        print(f"[rag] generic upcoming query (count={count}) — returning: {[r['folder'] for r in results]}")
        return results

    # Intercept generic 'past/passed festivals' queries (no specific folder mentioned)
    # and return the folders whose seasons have already passed this year
    if _is_past_query(query) and not _mentions_specific_festival(query, valid_folders):
        today = date.today()
        count = _parse_upcoming_count(query, default=3)
        past_list = _get_past_folders(valid_folders, today.month, festival_ranges, count)
        results = []
        for f in past_list:
            results.append({
                "folder": f["folder"],
                "display_name": f.get("display_name", f["folder"].replace("_", " ").title()),
                "templates": f.get("templates", []),
                "score": 0.95
            })
        print(f"[rag] generic past query (count={count}) — returning: {[r['folder'] for r in results]}")
        return results

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