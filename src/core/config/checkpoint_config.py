from pydantic_settings import BaseSettings, SettingsConfigDict

class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    CHECKPOINT_DATABASE_URL: str

checkpoint_setting = Setting() # type: ignore