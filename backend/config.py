from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openrouter_api_key: str = Field(validation_alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", validation_alias="OPENROUTER_MODEL")
    free_model: str = Field(default="openai/gpt-4o-mini", validation_alias="FREE_MODEL")
    rag_score_threshold: float = 0.55
    ambiguity_gap: float = 0.08
    max_prompt_length: int = 500
    font_path: str = "fonts/NotoSans.ttf"
    templates_dir: str = "templates"
    output_dir: str = "output"
    chroma_db_path: str = "chroma_db"
    bulk_row_delay_ms: int = 100

    class Config:
        env_file = ".env"

    @property
    def open_router_api_key(self) -> str:
        return self.openrouter_api_key

    @property
    def templates_path(self) -> str:
        return self.templates_dir

    @property
    def output_path(self) -> str:
        return self.output_dir

settings = Settings()
