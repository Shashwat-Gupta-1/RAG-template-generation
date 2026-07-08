import requests
import json
import os

API = "http://127.0.0.1:8000"
excel_path = "test_holi001.xlsx"

if not os.path.exists(excel_path):
    print("test_holi001.xlsx not found!")
    exit(1)

with open(excel_path, "rb") as f:
    excel_bytes = f.read()

files = {
    "excel_file": ("test_holi001.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
}

def test_prompt(prompt, folder=None, template_id=None):
    print(f"\n--- Testing prompt: '{prompt}' (folder={folder}, template_id={template_id}) ---")
    data = {"prompt": prompt}
    if folder:
        data["folder"] = folder
    if template_id:
        data["template_id"] = template_id
        
    try:
        res = requests.post(f"{API}/bulk/preview", data=data, files=files, timeout=30)
        print("Status code:", res.status_code)
        body = res.json()
        if "preview_image" in body:
            print("Response contains preview_image (Success!)")
            print("Matched template ID:", body.get("template_id"))
        else:
            print("Response:", json.dumps(body, indent=2))
    except Exception as e:
        print("Error:", e)

# Test 1: Ambiguous prompt
test_prompt("ladkiyon aur aurton ka tyohar")

# Test 2: Selecting folder
test_prompt("ladkiyon aur aurton ka tyohar", folder="teej")

# Test 3: Selecting specific template
test_prompt("ladkiyon aur aurton ka tyohar", folder="teej", template_id="teej001")

# Test 4: Holi prompt (direct success if column mapped, but since test_holi001 has full_name and holi001 expects name, it should return 422 with mapping info)
test_prompt("Holi")
