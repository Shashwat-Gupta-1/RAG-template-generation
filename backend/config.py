from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    open_router_api_key: str
    rag_score_threshold: float = 0.70
    max_prompt_length: int = 500
    font_path: str = "fonts/NotoSans.ttf"
    templates_dir: str = "templates"
    output_dir: str = "output"
    chroma_db_path: str = "chroma_db"
    bulk_row_delay_ms: int = 100

    class Config:
        env_file = ".env"

settings = Settings()
