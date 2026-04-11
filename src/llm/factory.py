from pydantic import SecretStr

from src.llm.provider.tongyi import get_tongyi_model

def get_model(
    config: dict
):
    provider = config.get("provider")
    api_key = config.get("api_key")
    model_name = config.get("model_name")
    base_url = config.get("base_url")

    if provider == "tongyi":
        return get_tongyi_model(SecretStr(api_key), model_name, base_url) # type: ignore
    else:
        raise ValueError(f"Unsupported provider: {provider}")