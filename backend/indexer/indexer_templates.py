import os, json, sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from processing.rag import save_template
from config import settings

REQUIRED_KEYS = ["template_id", "description", "tags", "base_image", "canvas", "overlay_layers"]

def validate(template: dict, path: str):
    for key in REQUIRED_KEYS:
        if key not in template:
            raise ValueError(f"Missing key '{key}' in {path}")
    if not os.path.exists(template["base_image"]):
        raise ValueError(f"base_image not found: {template['base_image']} in {path}")
    if len(template["description"].split()) < 10:
        raise ValueError(f"Description too short in {path} — must be at least 10 words")
    for layer in template["overlay_layers"]:
        if "box" not in layer:
            raise ValueError(f"Field '{layer.get('id')}' missing 'box' in {path}")
        if layer.get("type") == "text":
            s = layer.get("style", {})
            if s.get("font_size_min", 999) >= s.get("font_size", 0):
                raise ValueError(f"font_size_min must be less than font_size for field '{layer.get('id')}'")

def run():
    templates_dir = settings.templates_dir
    if not os.path.exists(templates_dir):
        print(f"ERROR: templates/ folder not found")
        return
    for folder in os.listdir(templates_dir):
        json_path = os.path.join(templates_dir, folder, "overlay.json")
        if not os.path.exists(json_path):
            print(f"SKIP: no overlay.json in {folder}")
            continue
        try:
            with open(json_path, encoding="utf-8") as f:
                template = json.load(f)
            validate(template, json_path)
            save_template(template)
        except Exception as e:
            print(f"ERROR in {folder}: {e}")

if __name__ == "__main__":
    run()