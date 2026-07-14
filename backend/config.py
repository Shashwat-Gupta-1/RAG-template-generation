from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openrouter_api_key: str
    free_model: str = "meta-llama/llama-3.1-8b-instruct:free"
    rag_score_threshold: float = 0.55
    ambiguity_gap: float = 0.08
    max_prompt_length: int = 500
    font_path: str = "fonts/NotoSans-Regular.ttf"
    templates_dir: str = "templates"
    output_dir: str = "output"
    chroma_db_path: str = "chroma_db"
    bulk_row_delay_ms: int = 200

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()