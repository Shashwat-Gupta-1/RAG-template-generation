import sys
sys.path.insert(0, 'backend')
from processing.rag import search_folder

tests = [
    "i need a poster for a festival where there is water ballons for Rahul",
    "teej festival poster for Priya",
    "loan offer poster",
    "gangaur poster for kishan",
    "dussehra greeting for ravi",
    "hiring college students poster",
    "eid mubarak for Abdul",
    "new year wishes for kumar",
    "festival of colours poster",
    "Rajasthani spring festival poster",
    "rang gulal celebration poster",
    "new branch inauguration poster",
    "local shopkeeper loan QR code poster"
]

for q in tests:
    result = search_folder(q)
    if result:
        r = result[0]
        print(f"MATCH  {r['score']:.3f}  {r['folder']:20s}  ← {q}")
    else:
        print(f"NO MATCH                       ← {q}")
    print()