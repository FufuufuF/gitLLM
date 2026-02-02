# 临时启用, 后续通过前端配置后从数据库中读取

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    model_name: str
    model_base_url: str
    model_api_key: str
    model_provider: Optional[str]
    
model_setting = Setting() # type: ignore