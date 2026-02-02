from gitllm.core.config import settings


def get_database_url() -> str:
    return settings.database_url
