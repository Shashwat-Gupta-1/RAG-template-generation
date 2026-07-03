import sys
sys.path.insert(0, 'backend')
import chromadb
import json
from sentence_transformers import SentenceTransformer

embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
client = chromadb.PersistentClient(path='chroma_db')
collection = client.get_collection('folders')

print('Count:', collection.count())
print('Metadata:', collection.metadata)
print()

queries = ['holi poster for Rahul', 'teej festival for ravi ', 'loan offer poster']

for query in queries:
    print(f"Query: '{query}'")
    vector = embedder.encode(query).tolist()
    results = collection.query(
        query_embeddings=[vector],
        n_results=collection.count(),
        include=['documents', 'distances']
    )
    for doc, dist in zip(results['documents'][0], results['distances'][0]):
        t = json.loads(doc)
        print(f"  {1-dist:.3f}  {t['folder']}")
    print()