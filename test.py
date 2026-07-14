import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import requests

# Test 1 — valid Excel
import pandas as pd
import io

# Create a test Excel file
df = pd.DataFrame({
    "emp_id": ["EMP001", "EMP002", "EMP003"],
    "name": ["Rahul Kumar", "Priya Singh", ""],   # EMP003 has blank name
})
df.to_excel("test_bulk_input.xlsx", index=False)
print("Created test_bulk_input.xlsx")

# Send to bulk endpoint
with open("test_bulk_input.xlsx", "rb") as f:
    response = requests.post(
        "http://localhost:8000/bulk",
        data={"prompt": "Holi poster for our employees"},
        files={"excel": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

print("Status code:", response.status_code)
print("Response:", response.json())