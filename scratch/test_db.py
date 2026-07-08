import sys
import os
sys.path.insert(0, os.path.abspath("."))

from backend.processing.rag import get_all_folders_from_db, search_folder, retrieve_template_overlay

print("All folders in DB:")
try:
    folders = get_all_folders_from_db()
    for f in folders:
        print(f"- {f['folder']}: {f['display_name']} tags={f['tags']} templates={f['templates']}")
except Exception as e:
    print("Error getting folders:", e)

print("\nSearching for 'Holi poster for Rahul Kumar':")
try:
    matches = search_folder("Holi poster for Rahul Kumar")
    for m in matches:
        print(f"Match: {m}")
    
    overlay = retrieve_template_overlay("Holi poster for Rahul Kumar")
    if overlay:
        print("Retrieved overlay template ID:", overlay.get("template_id"))
        print("Overlay layers:")
        for l in overlay.get("overlay_layers", []):
            print(f"  - {l.get('id')}: type={l.get('type')} llm_can_invent={l.get('llm_can_invent')}")
    else:
        print("No overlay retrieved.")
except Exception as e:
    print("Error during search:", e)
