from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr
from typing import Optional

def get_tongyi_model(api_key: SecretStr, model_name: str, base_url: Optional[str] = None) -> BaseChatModel:
    """
    Get Tongyi model instance.
    If base_url is provided, use ChatOpenAI (for compatible endpoints).
    Otherwise use native ChatTongyi.
    """
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
    )