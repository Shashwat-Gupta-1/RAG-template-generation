import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger("ms_fincap.main")

import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routes.generate import router as generate_router
from routes.bulk import router as bulk_router
from routes.rerender import router as rerender_router
from processing.rag import health_check
from config import settings

app = FastAPI(
    title="MS Fincap Template API",
    description="AI-powered visual template generation"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} "
        f"-> {response.status_code} ({duration_ms:.0f}ms)"
    )
    return response


app.include_router(generate_router)
app.include_router(bulk_router)
app.include_router(rerender_router)


@app.on_event("startup")
async def startup():
    if not os.path.exists(settings.font_path):
        logger.error(
            f"STARTUP ERROR: Font not found at {settings.font_path}. "
            f"Download NotoSans-Regular.ttf into fonts/"
        )
        sys.exit(1)

    if not health_check():
        logger.error(
            "STARTUP ERROR: ChromaDB is empty. "
            "Run: python backend/indexer/indexer.py"
        )
        sys.exit(1)

    os.makedirs(settings.output_dir, exist_ok=True)
    logger.info("MS Fincap API ready.")


@app.get("/health")
def health():
    return {"status": "ok"}