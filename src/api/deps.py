from collections.abc import Generator

from src.infra.db.session import get_db_session


def db_session() -> Generator:
    yield from get_db_session()
