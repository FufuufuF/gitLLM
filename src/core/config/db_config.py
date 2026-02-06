from pydantic_settings import BaseSettings, SettingsConfigDict

class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    DATABASE_URL: str = "mysql+aiomysql://fufu:fufu@127.0.0.1:3306/gitllm"
    
db_setting = Setting()