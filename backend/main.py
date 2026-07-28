from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles
import os

from backend.database.session import engine, Base
from backend.routes.bulk import router as bulk_router
from backend.routes.generate import router as generate_router
from backend.routes.auth_routes import router as auth_router
from backend.routes.history_routes import router as history_router
from backend.routes.agent_routes import router as agent_router
from backend.routes.admin_routes import router as admin_router
from backend.phase2.create_agent import _pool as langgraph_pool, get_checkpointer

app = FastAPI(title="MS Fincap Template Generator")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Serve generated output posters statically
output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
os.makedirs(output_dir, exist_ok=True)
app.mount("/output", StaticFiles(directory=output_dir), name="output")

# Serve workspace templates directory statically for template PNG images
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
if os.path.exists(templates_dir):
	app.mount("/templates", StaticFiles(directory=templates_dir), name="templates")

# Serve brand assets statically for logo and branding
brand_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "brand_config.py")
if os.path.exists(brand_dir):
	app.mount("/brand", StaticFiles(directory=brand_dir), name="brand")


@app.on_event("startup")
async def startup() -> None:
	# Start LangGraph Postgres Checkpointer pool
	if langgraph_pool is not None:
		await langgraph_pool.open()
		# Initialize the LangGraph saver/checkpointer schema tables
		checkpointer = get_checkpointer()
		await checkpointer.setup()

	# Initialize database tables
	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)
		from sqlalchemy import text
		await conn.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS prompt_versions JSON;"))


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


app.include_router(auth_router)
app.include_router(history_router)
app.include_router(agent_router)
app.include_router(generate_router)
app.include_router(bulk_router)
app.include_router(admin_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

