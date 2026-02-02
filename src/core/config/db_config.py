from pydantic_settings import BaseSettings, SettingsConfigDict

class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    database_url: str = "mysql+aiomysql://fufu:fufu@localhost/gitllm"
    
db_setting = Setting()