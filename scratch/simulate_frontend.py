import requests
import json
import os

API = "http://127.0.0.1:8000"
excel_path = "test_teej001.xlsx"

if not os.path.exists(excel_path):
    print("test_teej001.xlsx not found!")
    exit(1)

with open(excel_path, "rb") as f:
    excel_bytes = f.read()

files = {
    "excel_file": ("test_teej001.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
}

data = {
    "prompt": "ladkiyon ka tyohar"
}

try:
    res = requests.post(f"{API}/bulk/preview", data=data, files=files, timeout=30)
    print("Status code:", res.status_code)
    print("Response:", json.dumps(res.json(), indent=2))
except Exception as e:
    print("Error:", e)
