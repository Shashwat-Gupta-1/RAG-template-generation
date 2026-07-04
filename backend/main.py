import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.generate import router as generate_router
from routes.bulk import router as bulk_router
from processing.rag import health_check
from config import settings

app = FastAPI(title="MS Fincap Template API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(generate_router)
app.include_router(bulk_router)

@app.on_event("startup")
async def startup():
    if not os.path.exists(settings.font_path):
        print(f"STARTUP ERROR: Font not found at {settings.font_path}")
        sys.exit(1)
    if not health_check():
        print("STARTUP ERROR: ChromaDB is empty. Run: python backend/indexer/indexer_templates.py")
        sys.exit(1)
    os.makedirs(settings.output_dir, exist_ok=True)
    print("MS Fincap API ready.")