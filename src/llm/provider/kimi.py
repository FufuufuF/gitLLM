from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr
from typing import Optional

def get_tongyi_model(api_key: SecretStr, model_name: str, base_url: Optional[str] = None) -> BaseChatModel:
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
    )