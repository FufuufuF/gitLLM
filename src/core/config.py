from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite:///./gitllm.db"
    chroma_persist_dir: str = "./.chroma"

    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    llm_api_key: str = ""


settings = Settings()
