from pydantic_settings import BaseSettings, SettingsConfigDict

class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    CHECKPOINT_DATABASE_URL: str = "postgresql+asyncpg://fufu:fufu@localhost:5432/checkpoints"

checkpoint_setting = Setting() # type: ignore