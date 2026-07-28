from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", validation_alias="GROQ_MODEL")
    groq_model_agent: str = Field(default="llama-3.3-70b-versatile", validation_alias="GROQ_MODEL_AGENT")
    groq_model_single: str = Field(default="llama-3.3-70b-versatile", validation_alias="GROQ_MODEL_SINGLE")
    groq_model_bulk: str = Field(default="llama-3.1-8b-instant", validation_alias="GROQ_MODEL_BULK")

    groq_model_tags: str = Field(default="llama-3.1-8b-instant", validation_alias="GROQ_MODEL_TAGS")
    groq_model_fast: str = Field(default="llama-3.1-8b-instant", validation_alias="GROQ_MODEL_FAST")

    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openrouter/free", validation_alias="OPENROUTER_MODEL")

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_image_model: str = Field(default="gpt-image-2-2026-04-21", validation_alias="OPENAI_IMAGE_MODEL")

    free_model: str = Field(default="llama-3.3-70b-versatile", validation_alias="FREE_MODEL")
    rag_score_threshold: float = 0.60
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

    storage_type: str = Field(default="local", validation_alias="STORAGE_TYPE")
    gcs_bucket_name: str = Field(default="", validation_alias="GCS_BUCKET_NAME")
    gcp_project_id: str = Field(default="", validation_alias="GCP_PROJECT_ID")

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
