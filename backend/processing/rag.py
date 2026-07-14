import chromadb
import json
import os
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from config import settings
from logging_config import get_logger

logger = get_logger("ms_fincap.rag")

embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
client = chromadb.PersistentClient(
    path=settings.chroma_db_path,
    settings=ChromaSettings(anonymized_telemetry=False)
)
collection = client.get_or_create_collection("folders")

STOP_WORDS = {
    "a", "an", "the", "for", "of", "in", "on", "at", "to", "and",
    "or", "is", "are", "me", "my", "give", "make", "create", "want",
    "need", "please", "i", "can", "you", "generate", "get", "send",
    "show", "us", "our", "their", "we", "it", "this", "that"
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
        chunks.add(f"{words[i]} {words[i + 1]}".lower())

    for i in range(len(words) - 2):
        chunks.add(f"{words[i]} {words[i + 1]} {words[i + 2]}".lower())

    return list(chunks)


def search_folder(query: str, top_k: int = 3) -> list[dict]:
    """
    Stage 1: embed chunks against ChromaDB tag vectors.
    Stage 2 fallback: if nothing scores above threshold, ask LLM to pick.
    Returns list of {folder, display_name, templates, score}.
    """
    query = query[:settings.max_prompt_length]
    logger.info(f"search_folder: query={query!r}")

    if collection.count() == 0:
        logger.warning("search_folder: ChromaDB collection is empty.")
        return []

    chunks = extract_chunks(query)
    logger.debug(f"search_folder: {len(chunks)} chunks extracted: {chunks}")
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
            for doc, dist in zip(
                results["documents"][0],
                results["distances"][0]
            ):
                score = round(1 - dist, 3)
                data = json.loads(doc)
                fid = data["folder"]
                if score > best_scores.get(fid, {}).get("score", 0):
                    best_scores[fid] = {"score": score, "data": data}
        except Exception as e:
            logger.warning(f"search_folder: embedding query for chunk {chunk!r} failed: {e}")
            continue

    # Log the full ranked score table — this is the single most useful line
    # for diagnosing "wrong poster" or "no match" reports.
    ranked = sorted(best_scores.items(), key=lambda kv: kv[1]["score"], reverse=True)
    logger.info(
        "search_folder: scores -> "
        + ", ".join(f"{fid}={info['score']}" for fid, info in ranked[:8])
    )

    # Stage 1 results above threshold
    matches = []
    for fid, info in best_scores.items():
        if info["score"] >= settings.rag_score_threshold:
            matches.append({
                "folder": fid,
                "display_name": info["data"]["display_name"],
                "templates": info["data"]["templates"],
                "score": info["score"]
            })

    if matches:
        matches.sort(key=lambda x: x["score"], reverse=True)
        logger.info(
            f"search_folder: Stage 1 match(es) above threshold "
            f"({settings.rag_score_threshold}): "
            f"{[(m['folder'], m['score']) for m in matches[:top_k]]}"
        )
        return matches[:top_k]

    logger.info(
        f"search_folder: no folder scored >= {settings.rag_score_threshold}. "
        f"Falling back to Stage 2 LLM pick."
    )

    # Stage 2: LLM fallback
    try:
        all_docs = collection.get(include=["documents", "metadatas"])
        folder_list = []
        tag_map = {}
        for doc, meta in zip(
            all_docs["documents"], all_docs["metadatas"]
        ):
            fn = meta.get("folder", "")
            folder_list.append(fn)
            tag_map[fn] = meta.get("tags", "").split(", ")

        from processing.llm import llm_pick_folder
        picked = llm_pick_folder(query, folder_list, tag_map)
        logger.info(f"search_folder: Stage 2 LLM picked: {picked!r}")

        if picked:
            result = collection.get(
                ids=[picked], include=["documents"]
            )
            if result["documents"]:
                data = json.loads(result["documents"][0])
                logger.info(
                    f"search_folder: Stage 2 cached data for {picked!r} -> "
                    f"templates={data.get('templates')!r}"
                )
                return [{
                    "folder": picked,
                    "display_name": data["display_name"],
                    "templates": data["templates"],
                    "score": 0.0
                }]
            else:
                logger.warning(
                    f"search_folder: Stage 2 picked folder {picked!r} but "
                    f"it has no document in ChromaDB — treating as no_match."
                )
    except Exception as e:
        logger.error(f"search_folder: Stage 2 fallback failed: {e}")

    logger.warning("search_folder: returning no_match.")
    return []


def load_template(folder_name: str, template_id: str) -> dict | None:
    overlay_path = os.path.join(
        settings.templates_dir, folder_name, template_id, "overlay.json"
    )
    abs_path = os.path.abspath(overlay_path)
    exists = os.path.exists(overlay_path)
    # FIX: this was logger.debug, but setup_logging() defaults to INFO, so
    # this — the single most important line for diagnosing "template not
    # found" — was being silently suppressed the entire time. Bumped to
    # INFO, and added the absolute path + cwd so a relative-path/cwd
    # discrepancy between requests (if that's what's happening) becomes
    # immediately visible instead of invisible.
    logger.info(
        f"load_template: folder={folder_name!r} template_id={template_id!r} "
        f"cwd={os.getcwd()!r} abs_path={abs_path!r} exists={exists}"
    )
    if not exists:
        return None
    with open(overlay_path, encoding="utf-8") as f:
        data = json.load(f)

    # FIX: overlay.json's internal "template_id" field can drift out of
    # sync with the actual folder name on disk (typos, manual edits, etc).
    # Every caller elsewhere in the app — gallery listings, single-match
    # rendering, /template-info — trusts whatever "template_id" ends up in
    # the returned dict. If that's the internal JSON field instead of the
    # real folder name, any subsequent lookup using it 404s, even though
    # the exact same template was just loaded successfully. Normalizing
    # here, at the single data-access point, guarantees every consumer
    # downstream always gets the correct, disk-matching value.
    if data.get("template_id") != template_id:
        logger.warning(
            f"load_template: overlay.json 'template_id' field "
            f"('{data.get('template_id')}') does not match its actual "
            f"folder name ('{template_id}') under '{folder_name}/'. "
            f"Using the folder name — fix the file to match and avoid "
            f"relying on this normalization."
        )
        data["template_id"] = template_id

    return data


def load_all_templates_in_folder(folder_name: str) -> list[dict]:
    main_path = os.path.join(
        settings.templates_dir, folder_name, "main.json"
    )
    if not os.path.exists(main_path):
        logger.warning(f"load_all_templates_in_folder: no main.json for {folder_name!r}")
        return []
    with open(main_path, encoding="utf-8") as f:
        main = json.load(f)
    templates = []
    for tid in main.get("templates", []):
        t = load_template(folder_name, tid)
        if t:
            templates.append(t)
    return templates