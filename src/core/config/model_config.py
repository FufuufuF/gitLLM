import os
from pathlib import Path

from dotenv import dotenv_values

from src.domain.models import ModelConfig as DomainModelConfig


class EnvModelConfigResolver:
    """Build domain ModelConfig from model key and env vars."""

    def __init__(self, env_file: str = ".env") -> None:
        self._env_file = env_file
        self._dotenv_cache: dict[str, str] = {}

    def _load_dotenv(self) -> dict[str, str]:
        if self._dotenv_cache:
            return self._dotenv_cache

        env_path = Path(self._env_file)
        if not env_path.exists():
            self._dotenv_cache = {}
            return self._dotenv_cache

        raw_values = dotenv_values(env_path)
        self._dotenv_cache = {
            key.upper(): str(value)
            for key, value in raw_values.items()
            if value is not None
        }
        return self._dotenv_cache

    def _resolve_env_value(self, variable: str) -> str | None:
        value = os.getenv(variable)
        if value is not None:
            return value
        return self._load_dotenv().get(variable.upper())

    def _require_env_value(self, variable: str) -> str:
        value = self._resolve_env_value(variable)
        if value is None or not value.strip():
            raise ValueError(f"Missing required env var: {variable}")
        return value

    def get(self, model_key: str, *, config_id: int = 1, user_id: int = 1) -> DomainModelConfig:
        normalized_key = model_key.strip()
        if not normalized_key:
            raise ValueError("model_key cannot be empty")

        prefix = normalized_key.upper()
        model_name = self._require_env_value(f"{prefix}_MODEL_NAME")
        api_key = self._require_env_value(f"{prefix}_MODEL_API_KEY")
        base_url = self._resolve_env_value(f"{prefix}_MODEL_BASE_URL")
        provider = self._resolve_env_value(f"{prefix}_MODEL_PROVIDER") or normalized_key.lower()

        return DomainModelConfig(
            id=config_id,
            provider=provider.lower(),
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            user_id=user_id,
        )


model_config_resolver = EnvModelConfigResolver()


def get_model_config_from_env(
    model_key: str,
    *,
    config_id: int = 1,
    user_id: int = 1,
) -> DomainModelConfig:
    return model_config_resolver.get(model_key=model_key, config_id=config_id, user_id=user_id)