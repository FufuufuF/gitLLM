# Checkpoint PostgreSQL Infrastructure Setup Guide

本文档详细介绍了如何为 LangGraph 配置 PostgreSQL 作为 Checkpoint 持久化存储。

## 1. 依赖安装

由于本项目使用异步环境，我们需要安装 `langgraph-checkpoint-postgres` 以及异步 PostgreSQL 驱动 `asyncpg`。

请在 `pyproject.toml` 中添加以下依赖或直接安装：

```bash
pip install langgraph-checkpoint-postgres asyncpg
```

## 2. 配置更新

我们需要在配置中添加 PostgreSQL 的连接字符串。

**文件**: `src/core/config/db_config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 原有的业务数据库 (MySQL)
    database_url: str = "mysql+aiomysql://fufu:fufu@localhost/gitllm"

    # [新增] Checkpoint 数据库 (Postgres)
    # 格式: postgresql+asyncpg://user:password@host:port/dbname
    checkpoint_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/checkpoints"

db_setting = Setting()
```

> **注意**: 请确保你本地的 Postgres 数据库中已经创建了 `checkpoints` 数据库 (或者你指定的数据库名)。

## 3. 基础设施代码实现

参考 `src/infra/db` 的设计，我们创建一个新的模块 `src/infra/checkpoint` 来专门管理 Checkpoint 的连接。

建议目录结构：

```
src/
  infra/
    checkpoint/
      __init__.py
      postgres.py
```

**文件**: `src/infra/checkpoint/postgres.py`

```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
# 注意：在较新版本的 langgraph-checkpoint-postgres 中，推荐使用 AsyncPostgresSaver.from_conn_string
from src.core.config.db_config import db_setting

def get_checkpoint_url() -> str:
    # 确保使用 asyncpg 驱动
    url = db_setting.checkpoint_database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://")
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
```

### 代码详解

1.  **Dependencies**: 我们引入了 `langgraph.checkpoint.postgres.aio.AsyncPostgresSaver`，这是 LangGraph 官方提供的异步 Postgres 存储后端。
2.  **Configuration**: 从 `db_setting` 获取 URL。LangGraph Checkpointer 通常直接使用底层的 DB 连接库，所以连接字符串格式可能需要微调（去掉 SQLAlchemy 特有的 `+asyncpg` 标识）。
3.  **Context Manager**: 使用 `asynccontextmanager` 封装 `get_postgres_saver`。这是一个最佳实践，因为它确保了连接资源在使用后被正确释放。
4.  **`saver.setup()`**: 这是一个幂等操作。每次启动时调用它，它会检查并创建必要的表（如果表不存在）。

## 4. 在应用中集成

这是如何在你的业务逻辑（例如 `src/app.py` 或 Agent 初始化位置）中使用它的示例。

```python
from src.infra.checkpoint.postgres import get_postgres_saver
from src.graph.my_agent import build_graph # 假设你的 graph 构建逻辑在这里

async def run_agent_with_checkpoint():
    # 获取 saver
    async with get_postgres_saver() as checkpointer:

        # 编译 Graph 时传入 checkpointer
        # 你的 graph 构建函数应该只定义结构，compile 放在这里
        graph = build_graph()
        app = graph.compile(checkpointer=checkpointer)

        # 配置 thread_id (关联到业务 session_id)
        config = {"configurable": {"thread_id": "session_user_123"}}

        # 调用
        inputs = {"messages": [("user", "你好，请记住我。")]}
        async for event in app.astream(inputs, config=config):
            print(event)

        # 此时，状态已经自动持久化到 Postgres 中。
        # 如果再次运行并传入相同的 thread_id，它会恢复之前的状态。
```

## 5. 常见问题 (FAQ)

### Q: 为什么不仅使用现有的 MySQL?

A: LangGraph 目前官方仅对 Postgres (`PostgresSaver`) 和 SQLite (`SqliteSaver`) 提供了一级支持。虽然这可以扩展支持 MySQL，但在生产环境中，利用 Postgres 强大的 JSONB 处理能力来存储复杂的 Graph State 是目前的最佳实践。

### Q: 数据库需要预先建表吗？

A: 不需要。`checkpointer.setup()` 方法会自动检测并创建所需的表结构（如 `checkpoints`, `writes` 等）。您只需要确保有一个空的数据库（Database）存在，并且连接用户有建表权限。

### Q: 本地开发没有 Postgres 怎么办？

A: 可以使用 Docker 快速启动一个：

```bash
docker run --name langgraph-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:16
```

然后创建一个名为 `checkpoints` 的数据库：

```bash
docker exec -it langgraph-pg createdb -U postgres checkpoints
```
