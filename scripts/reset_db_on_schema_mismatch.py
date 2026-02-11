from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Iterable

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import inspect, insert, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import CircularDependencyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.engine import engine
from src.infra.db.models import Base, User  # Import Base to register all models
from src.infra.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _normalize_type_name(type_obj: object) -> str:
    return type(type_obj).__name__.lower()


def _orm_columns_signature() -> dict[str, dict[str, str]]:
    signature: dict[str, dict[str, str]] = {}
    for table_name, table in Base.metadata.tables.items():
        signature[table_name] = {
            column.name: _normalize_type_name(column.type) for column in table.columns
        }
    return signature


def _db_columns_signature(conn: Connection, table_names: Iterable[str]) -> dict[str, dict[str, str]]:
    inspector = inspect(conn)
    signature: dict[str, dict[str, str]] = {}
    for table_name in table_names:
        columns = inspector.get_columns(table_name)
        signature[table_name] = {
            column["name"]: _normalize_type_name(column["type"]) for column in columns
        }
    return signature


def _schema_mismatch(orm_sig: dict[str, dict[str, str]], db_sig: dict[str, dict[str, str]]) -> bool:
    if set(orm_sig.keys()) != set(db_sig.keys()):
        return True
    for table_name, orm_cols in orm_sig.items():
        db_cols = db_sig.get(table_name, {})
        if orm_cols != db_cols:
            return True
    return False


async def reset_db_if_schema_mismatch() -> bool:
    orm_sig = _orm_columns_signature()

    async with engine.begin() as conn:
        db_sig = await conn.run_sync(_db_columns_signature, orm_sig.keys())
        if not _schema_mismatch(orm_sig, db_sig):
            logger.info("Schema matches ORM; no reset needed.")
            return False

        logger.warning("Schema mismatch detected; dropping and recreating all tables.")
        # Try normal drop_all/create_all first; if CircularDependencyError occurs,
        # fall back to disabling MySQL foreign key checks and dropping tables manually.
        try:
            await conn.run_sync(Base.metadata.drop_all)
        except CircularDependencyError:
            logger.warning("CircularDependencyError during drop_all; attempting manual drop (MySQL).")
            # Attempt MySQL-specific workaround: disable FK checks and drop tables
            try:
                await conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
                for table_name in list(Base.metadata.tables.keys()):
                    await conn.execute(text(f"DROP TABLE IF EXISTS `{table_name}`;"))
                await conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
            except Exception as e:
                logger.exception("Failed to manually drop tables: %s", e)
                raise

        # Recreate all tables using metadata
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        await _insert_test_user(session)
        await session.commit()

    logger.info("Database reset completed.")
    return True


async def _insert_test_user(session: AsyncSession) -> None:
    await session.execute(
        insert(User).values(
            id=1,
            username="test",
            password_hash="test",
            display_name="Test User",
            status=1,
        )
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    async def _runner() -> None:
        try:
            await reset_db_if_schema_mismatch()
        finally:
            try:
                # Ensure engine and connection pools are disposed before event loop closes
                await engine.dispose()
            except Exception:
                logger.exception("Error while disposing engine")
            # allow any pending connection cleanup tasks to run
            await asyncio.sleep(0.05)

    asyncio.run(_runner())


if __name__ == "__main__":
    main()
