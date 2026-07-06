from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.jobs.job_tracker import init_db
from backend.routes.bulk import router as bulk_router
from backend.routes.generate import router as generate_router


app = FastAPI(title="MS Fincap Template Generator")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
	init_db()


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


app.include_router(generate_router)
app.include_router(bulk_router)

