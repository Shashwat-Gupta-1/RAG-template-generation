from backend.processing.rag import query_templates

tests = [
    "Holi poster for Rahul Kumar",
    "new employee joining announcement poster",
    "quarterly financial report for board meeting"
]

for prompt in tests:
    print("PROMPT:", prompt)
    results = query_templates(prompt, top_k=1)
    for r in results:
        print("  ->", r["template_id"], " score=", round(r["score"], 3))
    print()