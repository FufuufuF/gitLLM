"""
一键初始化数据库脚本 — 首次部署时使用。

功能:
1. 创建 MySQL 数据库（如不存在）
2. 创建 MySQL 所有表（通过 Base.metadata.create_all）
3. 插入种子数据（测试用户）
4. 创建 PostgreSQL checkpoints 数据库（如不存在）

运行方式: uv run python scripts/init_db.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from urllib.parse import urlparse

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pymysql
import psycopg
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.db_config import db_setting
from src.core.config.checkpoint_config import checkpoint_setting
from src.infra.db.engine import engine
from src.infra.db.models import Base, User
from src.infra.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. MySQL: 创建数据库
# ---------------------------------------------------------------------------


def _create_mysql_database() -> None:
    """使用 pymysql 直连 MySQL，创建业务数据库（如不存在）。"""
    url = urlparse(db_setting.DATABASE_URL.strip())
    db_name = url.path.lstrip("/")
    host = url.hostname or "127.0.0.1"
    port = url.port or 3306
    user = url.username or "root"
    password = url.password or ""

    conn = pymysql.connect(host=host, port=port, user=user, password=password)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        conn.commit()
        logger.info("MySQL database '%s' ensured.", db_name)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 2. MySQL: 创建表 + 种子数据
# ---------------------------------------------------------------------------


async def _create_mysql_tables() -> None:
    """通过 SQLAlchemy metadata 创建所有 ORM 表。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("MySQL tables created/verified.")


async def _insert_seed_user() -> None:
    """插入测试用户（与 reset_db_on_schema_mismatch.py 保持一致）。"""
    async with SessionLocal() as session:
        # 检查是否已存在
        result = await session.execute(
            text("SELECT id FROM users WHERE id = 1")
        )
        if result.scalar() is not None:
            logger.info("Seed user already exists, skipping.")
            return

        await session.execute(
            insert(User).values(
                id=1,
                username="test",
                password_hash="test",
                display_name="Test User",
                status=1,
            )
        )
        await session.commit()
        logger.info("Seed user inserted.")


# ---------------------------------------------------------------------------
# 3. PostgreSQL: 创建 checkpoints 数据库
# ---------------------------------------------------------------------------


def _create_postgres_database() -> None:
    """连接 PostgreSQL 默认 postgres 库，创建 checkpoints 数据库（如不存在）。"""
    checkpoint_url = checkpoint_setting.CHECKPOINT_DATABASE_URL.strip()
    # 去掉 SQLAlchemy driver 标识以获取标准 postgres URL
    clean_url = checkpoint_url.replace("+asyncpg", "")
    parsed = urlparse(clean_url)
    target_db = parsed.path.lstrip("/")

    # 连接默认 postgres 库
    default_url = clean_url.replace(f"/{target_db}", "/postgres")

    with psycopg.Connection.connect(default_url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (target_db,)
        ).fetchone()
        if row is None:
            conn.execute(
                psycopg.sql.SQL("CREATE DATABASE {}").format(
                    psycopg.sql.Identifier(target_db)
                )
            )
            logger.info("PostgreSQL database '%s' created.", target_db)
        else:
            logger.info("PostgreSQL database '%s' already exists.", target_db)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _async_main() -> None:
    try:
        # Step 1: MySQL 数据库
        _create_mysql_database()

        # Step 2: MySQL 表
        await _create_mysql_tables()

        # Step 3: 种子数据
        await _insert_seed_user()

        # Step 4: PostgreSQL 数据库
        _create_postgres_database()

        logger.info("All databases initialized successfully!")
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
