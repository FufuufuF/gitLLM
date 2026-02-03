# 临时启用, 后续通过前端配置后从数据库中读取

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    QWEN_MODEL_NAME: str
    QWEN_MODEL_BASE_URL: str
    QWEN_MODEL_API_KEY: str
    QWEN_MODEL_PROVIDER: Optional[str]
    
model_setting = Setting() # type: ignore