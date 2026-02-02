# 数据库基建（异步 SQLAlchemy）与 Alembic 迁移指南

本文针对当前项目 `gitLLM` 的后端代码结构，提供一套“异步数据库连接 + 异步 CRUD +（可选）Alembic 迁移”的最小可用基建。

目标：
- 所有数据库连接与 CRUD 操作都使用异步（`AsyncEngine` / `AsyncSession`）
- 代码可直接复制粘贴到对应文件
- 解释每个文件的职责与关键点
- 介绍 Alembic 迁移是什么，以及在本项目中如何使用

> 说明：你当前阶段不写 `src/infra/db/models.py`，本文会把模型相关内容保持为“可插拔”，等你补齐 ORM 模型后即可接入迁移与 Repository。

---

## 1. 依赖与数据库 URL 约定

### 1.1 需要的依赖

把以下依赖加入项目（你也可以只添加你需要的数据库驱动）：

- `sqlalchemy[asyncio]`：SQLAlchemy 2.x 异步支持
- `aiosqlite`：SQLite 的异步驱动（如果你用 SQLite）
- `alembic`：迁移工具（可选但强烈建议）
- `asyncpg`：如果你用 Postgres（可选）

你当前项目使用 `pyproject.toml` 管理依赖。建议配置（可直接粘贴覆盖对应段落）见下文“文件代码”。

### 1.2 数据库 URL（异步版）

建议在 `.env` 或配置中使用异步 URL：

- SQLite：`sqlite+aiosqlite:///./gitllm.db`
- Postgres：`postgresql+asyncpg://user:pass@localhost:5432/gitllm`

本项目的 `src/infra/db/engine.py` 会对常见“同步 URL”做兼容转换（例如把 `sqlite:///...` 转成 `sqlite+aiosqlite:///...`），但建议你最终统一写异步 URL，减少认知成本。

---

## 2. 文件代码（可直接粘贴）

下面每个小节都给出“目标文件路径 + 完整代码”。

### 2.1 [pyproject.toml](../pyproject.toml)

用途：声明数据库相关依赖。

```toml
[project]
name = "gitllm"
version = "0.1.0"
description = "gitLLM backend (MVP)"
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.24",
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "python-dotenv>=1.0",

  # Database (async)
  "sqlalchemy[asyncio]>=2.0",
  "aiosqlite>=0.20",

  # Migrations
  "alembic>=1.13",

  # LLM / Graph / Vectorstore (MVP placeholders)
  "langchain>=0.2",
  "langgraph>=0.2",
  "chromadb>=0.5",
]

[project.optional-dependencies]
dev = [
  "ruff>=0.4",
]

[build-system]
requires = ["hatchling>=1.21"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/gitllm"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

解释：
- `sqlalchemy[asyncio]` 提供 `create_async_engine`、`AsyncSession`、`async_sessionmaker` 等。
- `aiosqlite` 仅在 SQLite 时需要；如果你换 Postgres，把驱动换成 `asyncpg`。
- `alembic` 用于 schema 迁移；后面章节会讲怎么 init 与使用。

---

### 2.2 [src/core/config.py](../src/core/config.py)

用途：集中配置，提供 `database_url`。

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8000

    # Async SQLAlchemy URL. Examples:
    # - sqlite+aiosqlite:///./gitllm.db
    # - postgresql+asyncpg://user:pass@localhost:5432/gitllm
    database_url: str = "sqlite+aiosqlite:///./gitllm.db"
    chroma_persist_dir: str = "./.chroma"

    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    llm_api_key: str = ""


settings = Settings()
```

解释：
- 这里建议默认就是异步 URL（`sqlite+aiosqlite`）。
- 你也可以通过 `.env` 覆盖 `DATABASE_URL`（Pydantic Settings 会自动映射为 `database_url`）。

---

### 2.3 [src/infra/db/engine.py](../src/infra/db/engine.py)

用途：创建全局 `AsyncEngine`，并提供一个“URL 归一化”函数。

```python
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.core.config import settings


def get_database_url() -> str:
    """Return an Async SQLAlchemy URL.

    If the user provides a sync URL (e.g. sqlite:///...), we upgrade it to the
    async driver variant (sqlite+aiosqlite:///...).
    """

    url = settings.database_url.strip()
    if url.startswith("sqlite:///") and not url.startswith("sqlite+aiosqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        # Common default for async Postgres.
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine: AsyncEngine = create_async_engine(
    get_database_url(),
    pool_pre_ping=True,
)
```

解释：
- `engine` 是全局异步 Engine，会被 `session.py` 绑定。
- `pool_pre_ping=True` 可以减少长连接断开导致的异常（对 Postgres/MySQL 更有意义）。
- `get_database_url()` 做了“同步 URL → 异步 URL”的轻量兼容，方便你早期从 SQLite/同步配置迁移。

---

### 2.4 [src/infra/db/session.py](../src/infra/db/session.py)

用途：创建 `async_sessionmaker`，并提供 FastAPI 依赖：`get_db_session()`。

```python
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.db.engine import engine


SessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: provides an AsyncSession.

    Notes:
    - We rollback on exceptions to keep connections clean.
    - We do not auto-commit; let services/repos decide when to commit.
    """

    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

解释：
- `SessionLocal()` 生成 `AsyncSession`。
- `expire_on_commit=False`：commit 后对象属性不会过期，符合多数 API 场景（减少二次查询）。
- 该依赖不自动 commit：
  - 优点：写操作的事务边界由 service/repository 决定，更可控。
  - 你可以在 service 层显式 `await session.commit()`，或使用 `async with session.begin(): ...`。

---

### 2.5 [src/api/deps.py](../src/api/deps.py)

用途：对外提供依赖注入函数，供 API 路由使用。

```python
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.session import get_db_session


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session
```

解释：
- 这里把底层 `get_db_session()` 包一层，方便未来你想统一注入额外逻辑（比如 request-id、审计日志、强制只读事务等）。

---

### 2.6 [src/infra/db/repositories/base.py](../src/infra/db/repositories/base.py)

用途：提供一个通用的异步 CRUD Repository 基类（不依赖你的具体 ORM 模型）。

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

TModel = TypeVar("TModel")


@dataclass(slots=True)
class BaseRepository(Generic[TModel]):
    session: AsyncSession
    model: Type[TModel]

    async def get(self, id: Any) -> TModel | None:
        return await self.session.get(self.model, id)

    def list_stmt(self) -> Select[tuple[TModel]]:
        return select(self.model)

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[TModel]:
        stmt = self.list_stmt().offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, obj: TModel) -> TModel:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, obj: TModel) -> None:
        await self.session.delete(obj)

    async def delete_by_id(self, id: Any) -> int:
        stmt = delete(self.model).where(getattr(self.model, "id") == id)
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)
```

解释：
- 这是“最小可用”的 CRUD：`get/list/add/delete/delete_by_id`。
- 事务提交不在这里做：
  - 你可以在 service 层 `await session.commit()`
  - 或用 `async with session.begin(): ...` 自动提交/回滚

---

### 2.7 [src/infra/db/repositories/__init__.py](../src/infra/db/repositories/__init__.py)

用途：对外导出 `BaseRepository`。

```python
from src.infra.db.repositories.base import BaseRepository

__all__ = ["BaseRepository"]
```

解释：
- 让上层可以用 `from src.infra.db.repositories import BaseRepository`。

---

## 3. 如何在 Service / API 中使用（异步 CRUD 示例）

> 这段示例不要求你现在就有 ORM 模型，只是展示“依赖注入 + Repository + 事务提交”的写法。

典型写法：
- API 层拿到 `session: AsyncSession`
- Service 层创建 repository 并执行操作
- 写操作显式 commit（或 `session.begin()`）

伪代码示例（等你创建好 ORM Model 后替换 `YourModel`）：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import db_session
from src.infra.db.repositories import BaseRepository

router = APIRouter()

@router.get("/items")
async def list_items(session: AsyncSession = Depends(db_session)):
    repo = BaseRepository(session=session, model=YourModel)
    return await repo.list(limit=50)

@router.post("/items")
async def create_item(payload: dict, session: AsyncSession = Depends(db_session)):
    async with session.begin():
        repo = BaseRepository(session=session, model=YourModel)
        obj = YourModel(**payload)
        await repo.add(obj)
    return obj
```

关键点：
- **读操作**一般不需要事务；直接查询即可。
- **写操作**推荐使用 `async with session.begin():`，自动提交/异常回滚。

---

## 4. Alembic 迁移是什么？为什么需要它？

### 4.1 Alembic 是什么

Alembic 是 SQLAlchemy 官方生态中最常用的数据库 schema 迁移工具。

它解决的问题是：
- 你的 ORM 模型（或你想要的表结构）在迭代
- 生产/测试/本地数据库里已经有旧表结构
- 你需要一种**可追踪、可回滚、可协作**的方式，把 schema 从版本 A 演进到版本 B

核心概念：
- **revision（迁移版本）**：每次变更 schema，生成一个版本文件（Python 脚本）
- **upgrade / downgrade**：升级到新版本或回滚到旧版本
- **autogenerate**：根据 `Base.metadata` 对比当前数据库结构，生成“候选迁移脚本”（仍需人工 review）

### 4.2 你在本项目中如何使用（推荐流程）

前提：当你准备开始写 `models.py`（ORM 模型）时，再接入 autogenerate 会更顺。

1) 初始化 Alembic（只做一次）

在项目根目录运行：

- `alembic init alembic`

它会生成：
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/`（存放迁移脚本）

2) 配置 `alembic.ini` 的连接 URL

把 `sqlalchemy.url = ...` 改成你的数据库 URL。

建议写异步 URL 也可以，但更推荐让 `env.py` 从你的 `settings` 读取（避免重复配置）。

3) 修改 `alembic/env.py`（让它认识你的 metadata，并支持 async）

当你写好 ORM 的 `Base.metadata` 后，把 `target_metadata` 指向它。

下面是一个适配 AsyncEngine 的 `alembic/env.py` 参考模板（可直接替换 Alembic 生成的 env.py 里的核心逻辑）：

```python
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.infra.db.engine import get_database_url

# 如果你后续在 models.py 定义了 Base = declarative_base()，这里引入它：
# from src.infra.db.models import Base
# target_metadata = Base.metadata

target_metadata = None

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

4) 生成迁移脚本

- `alembic revision --autogenerate -m "create tables"`

5) 应用迁移到数据库

- `alembic upgrade head`

常用命令：
- 查看当前版本：`alembic current`
- 查看历史：`alembic history`
- 回滚一个版本：`alembic downgrade -1`

### 4.3 关于 autogenerate 的注意事项

- autogenerate 生成的是“候选迁移”，一定要 review。
- 一些变更（列重命名、复杂索引/约束、数据迁移）需要你手写迁移逻辑。

---

## 5. 你接下来可以做什么

- 先决定数据库：SQLite（快速）还是 Postgres（更贴近生产）
- 开始写 `src/infra/db/models.py` 的 ORM 模型后：
  - 再 `alembic init` 并把 `target_metadata` 指过去
  - 用 `revision --autogenerate` 维护 schema 演进

如果你愿意，我也可以：
- 按你 PRD/数据库设计文档把第一版 ORM 模型（threads/sessions/messages/merges）补齐
- 直接帮你生成 Alembic scaffold（`alembic.ini` + `alembic/env.py` + 目录结构），并配置好异步迁移
