from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database.session import engine, Base
from backend.routes.bulk import router as bulk_router
from backend.routes.generate import router as generate_router
from backend.routes.auth_routes import router as auth_router
from backend.routes.history_routes import router as history_router
from backend.routes.agent_routes import router as agent_router
from backend.phase2.create_agent import _pool as langgraph_pool, get_checkpointer

app = FastAPI(title="MS Fincap Template Generator")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


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


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


app.include_router(auth_router)
app.include_router(history_router)
app.include_router(agent_router)
app.include_router(generate_router)
app.include_router(bulk_router)

from backend.routes.template_routes import router as template_router
app.include_router(template_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

