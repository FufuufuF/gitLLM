from langchain_community.chat_models.tongyi import ChatTongyi
from pydantic import SecretStr

def get_tongyi_model(api_key: SecretStr, model_name: str) -> ChatTongyi:
    llm = ChatTongyi(
        model=model_name,
        api_key=api_key,
    )
    return llm