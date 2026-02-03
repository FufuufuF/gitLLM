from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from src.core.config.checkpoint_config import checkpoint_setting

def get_checkpoint_url() -> str:
    url = checkpoint_setting.CHECKPOINT_DATABASE_URL.strip()
    return url

@asynccontextmanager
async def get_postgres_saver() -> AsyncGenerator[AsyncPostgresSaver, None]:
    """
    提供一个异步的 PostgresSaver 实例。

    Usage:
        async with get_postgres_saver() as saver:
            app = workflow.compile(checkpointer=saver)
            ...

    注意:
    1. 第一次运行时，saver.setup() 会自动创建所需的表 (checkpoints, checkpoint_blobs 等)。
    2. 这个 Context Manager 会处理连接池的开启和关闭。
    """
    checkpoint_url = get_checkpoint_url()

    # langgraph-checkpoint-postgres 的 AsyncPostgresSaver 期望的是 connection string。
    # 为了避免 SQLAlchemy 格式 (+asyncpg) 可能带来的问题（视底层实现而定），我们做一个清理。
    # 通常 PostgresSaver 底层使用 psycopg 3 or generic async driver，可以接受 standard URL.

    # 去除 sqlalchemy 特有的 driver 标识，还原为标准 postgres url
    # 例如: postgresql+asyncpg://... -> postgresql://...
    clean_url = checkpoint_url.replace("+asyncpg", "")

    async with AsyncPostgresSaver.from_conn_string(clean_url) as saver:
        # 首次运行时自动建表
        await saver.setup()
        yield saver