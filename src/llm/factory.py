from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr
from typing import Optional

from src.llm.provider import get_tongyi_model

def get_model(
    provider: str,
    api_key: str,
    model_name: str,
    base_url: Optional[str] = None,
):
    if provider == "tongyi":
        return get_tongyi_model(SecretStr(api_key), model_name)
    else:
        raise ValueError(f"Unsupported provider: {provider}")