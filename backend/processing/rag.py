import chromadb
import json
import os
from sentence_transformers import SentenceTransformer
from config import settings

embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
client = chromadb.PersistentClient(path=settings.chroma_db_path)
collection = client.get_or_create_collection("templates")

def health_check() -> bool:
    return collection.count() > 0

def save_template(template: dict) -> None:
    existing = collection.get(ids=[template["template_id"]])
    if existing["ids"]:
        print(f"Already indexed: {template['template_id']} — skipping")
        return
    embed_text = template["description"] + " " + " ".join(template.get("tags", []))
    vector = embedder.encode(embed_text).tolist()
    collection.add(
        ids=[template["template_id"]],
        embeddings=[vector],
        documents=[json.dumps(template)],
        metadatas=[{
            "description": template["description"],
            "type": template.get("type", ""),
            "tags": ", ".join(template.get("tags", []))
        }]
    )
    print(f"Indexed: {template['template_id']}")

def search_template(query: str, top_k: int = 3) -> list[dict]:
    query = query[:settings.max_prompt_length]
    vector = embedder.encode(query).tolist()
    results = collection.query(
        query_embeddings=[vector],
        n_results=min(top_k, collection.count()),
        include=["documents", "distances"]
    )
    matches = []
    for doc, dist in zip(results["documents"][0], results["distances"][0]):
        score = 1 - dist
        if score >= settings.rag_score_threshold:
            matches.append({
                "template": json.loads(doc),
                "score": round(score, 3)
            })
    return matches