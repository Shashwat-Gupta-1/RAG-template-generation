import os
import json
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import chromadb
from sentence_transformers import SentenceTransformer
from backend.config import settings

REQUIRED_KEYS = ["template_id", "description", "tags",
                 "base_image", "canvas", "overlay_layers"]

def get_collection():
    client = chromadb.PersistentClient(path=settings.chroma_db_path)
    return client.get_or_create_collection(
        name="folders",
        metadata={"hnsw:space": "cosine"}
    )

def validate_overlay(template: dict, path: str) -> None:
    for key in REQUIRED_KEYS:
        if key not in template:
            raise ValueError(f"Missing key '{key}' in {path}")
    if not os.path.exists(template["base_image"]):
        raise ValueError(f"base_image not found: {template['base_image']}")
    if len(template["description"].split()) < 10:
        raise ValueError(f"Description too short (need 10+ words) in {path}")
    for layer in template.get("overlay_layers", []):
        if "box" not in layer:
            raise ValueError(f"Field '{layer.get('id')}' missing 'box' in {path}")
        if layer.get("type") == "text":
            s = layer.get("style", {})
            if s.get("font_size_min", 999) >= s.get("font_size", 0):
                raise ValueError(
                    f"font_size_min must be less than font_size "
                    f"for field '{layer.get('id')}' in {path}"
                )

def build_main_json(folder_path: str, folder_name: str) -> dict | None:
    all_descriptions = []
    all_tags = set()
    template_ids = []
    season_months = None

    for item in sorted(os.listdir(folder_path)):
        item_path = os.path.join(folder_path, item)
        if not os.path.isdir(item_path):
            continue
        overlay_path = os.path.join(item_path, "overlay.json")
        if not os.path.exists(overlay_path):
            continue
        try:
            with open(overlay_path, encoding="utf-8") as f:
                overlay = json.load(f)
            validate_overlay(overlay, overlay_path)
            all_descriptions.append(overlay["description"])
            all_tags.update(overlay.get("tags", []))
            template_ids.append(item)
            
            # If the template defines seasonality, capture it (use first template's setting as folder default)
            if "season_months" in overlay and season_months is None:
                season_months = overlay["season_months"]
                
            print(f"    Read: {item}/overlay.json")
        except Exception as e:
            print(f"    ERROR in {item}: {e}")

    if not template_ids:
        return None

    folder_repeated = f"{folder_name} {folder_name}"
    tag_str = " ".join(sorted(all_tags))
    embed_text = f"{folder_repeated} {tag_str}"

    main = {
        "folder": folder_name,
        "display_name": folder_name.replace("_", " ").title(),
        "embed_text": embed_text,
        "tags": sorted(list(all_tags)),
        "templates": sorted(template_ids)
    }
    if season_months:
        main["season_months"] = season_months

    main_path = os.path.join(folder_path, "main.json")
    with open(main_path, "w", encoding="utf-8") as f:
        json.dump(main, f, indent=2, ensure_ascii=False)

    return main


def index_folder(folder_name: str, main: dict) -> None:
    collection = get_collection()
    embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    vector = embedder.encode(main["embed_text"]).tolist()
    
    try:
        collection.upsert(
            ids=[folder_name],
            embeddings=[vector],
            documents=[json.dumps(main)]
        )
    except Exception as e:
        try:
            collection.add(
                ids=[folder_name],
                embeddings=[vector],
                documents=[json.dumps(main)]
            )
        except Exception:
            pass
    print(f"  Indexed: {folder_name} ({len(main['templates'])} template(s))")

def run():
    templates_dir = settings.templates_dir
    print(f"Scanning: {os.path.abspath(templates_dir)}\n")

    if not os.path.exists(templates_dir):
        print("ERROR: templates/ folder not found")
        return

    count = 0
    for folder_name in sorted(os.listdir(templates_dir)):
        folder_path = os.path.join(templates_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        print(f"Processing: {folder_name}/")
        main = build_main_json(folder_path, folder_name)
        if main is None:
            print(f"  SKIP: no valid templates in {folder_name}/")
            continue
        index_folder(folder_name, main)
        count += 1

    print(f"\nDone. {count} folder(s) indexed.")

if __name__ == "__main__":
    run()
