from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openrouter_api_key: str = Field(validation_alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", validation_alias="OPENROUTER_MODEL")
    free_model: str = Field(default="openai/gpt-4o-mini", validation_alias="FREE_MODEL")
    rag_score_threshold: float = 0.55
    ambiguity_gap: float = 0.15
    max_prompt_length: int = 500
    font_path: str = "fonts/NotoSans.ttf"
    templates_dir: str = "templates"
    output_dir: str = "output"
    chroma_db_path: str = "chroma_db"
    bulk_row_delay_ms: int = 100
    database_url: str = Field(validation_alias="DATABASE_URL")
    langgraph_db_url: str = Field(validation_alias="LANGGRAPH_DB_URL")
    secret_key: str = Field(validation_alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", validation_alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=480, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")

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
