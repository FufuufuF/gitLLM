# gitLLM 后端项目目录结构设计（MVP）

更新时间：2026-02-01

本文档只聚焦一件事：给出清晰、可扩展的后端项目目录结构，并说明每个目录/关键文件放什么。

技术栈前提：`uv` + Python + FastAPI + LangChain/LangGraph + Chroma。

## 1. 目录结构总览（建议）

> 这是一个“纯后端仓库”，前端在另一个仓库，因此这里不需要 `backend/` 顶层；直接把后端工程文件放在仓库根目录即可。

```text
gitLLM/
  docs/
    PRD.md
    backend-architecture.md

  pyproject.toml
  uv.lock
  README.md
  .env.example

  src/
    gitllm/
      __init__.py
      main.py

      api/
        __init__.py
        deps.py
        error_handlers.py
        v1/
          __init__.py
          router.py
          sessions.py
          threads.py
          messages.py
          merges.py
          settings.py
          auth.py            # 预留：登录/注册（MVP 可不启用）
          model_configs.py   # 预留：模型配置（MVP 可不启用）
        schemas/
          __init__.py
          sessions.py
          threads.py
          messages.py
          merges.py
          settings.py
          auth.py            # 预留
          model_configs.py   # 预留

      domain/
        __init__.py
        enums.py
        models.py
        errors.py

      app/
        __init__.py
        services/
          __init__.py
          session_service.py
          thread_service.py
          message_service.py
          merge_service.py
        policies/
          __init__.py
          merge_policy.py
          suggestion_policy.py

      graph/
        __init__.py
        state.py
        graphs/
          __init__.py
          chat_graph.py
          merge_graph.py
        nodes/
          __init__.py
          load_context.py
          detect_suggestion.py
          generate_reply.py
          generate_brief.py
        prompts/
          __init__.py
          brief.md
          suggestion.md

      infra/
        __init__.py
        db/
          __init__.py
          engine.py
          session.py
          models.py
          repositories/
            __init__.py
            sessions.py
            threads.py
            messages.py
            merges.py
        vectorstore/
          __init__.py
          chroma_client.py
          brief_index.py
        llm/
          __init__.py
          provider.py
          factory.py
        auth/
          __init__.py
          password_hasher.py
          tokens.py

      core/
        __init__.py
        config.py
        logging.py
        time.py
        security.py          # 预留：鉴权依赖/策略

  scripts/
    dev.ps1
    dev.sh

  migrations/               # 可选：Alembic（MVP 可先不加）
    versions/

  tests/                    # 可选：你当前不考虑测试，可暂不创建
    (reserved)
```

## 2. 目录与文件职责说明

### 2.1 仓库根目录

- docs/
  - 产品/架构/接口文档都放这里。
- src/
  - 后端业务代码（可发布的 Python 包）。
- pyproject.toml / uv.lock
  - `uv` 的依赖与锁文件。

（可选）未来扩展：
- services/：多服务拆分时的统一父目录

### 2.2 仓库根（后端工程根）

- pyproject.toml
  - `uv` 的依赖与项目元信息；FastAPI/LangGraph/Chroma 等依赖在这里声明。
- uv.lock
  - 锁定依赖版本，保证 CI/本地一致。
- README.md
  - 后端本地启动、环境变量说明、常用命令。
- .env.example
  - 运行所需环境变量示例（不要放真实密钥）。

### 2.3 src/gitllm/（可发布的 Python 包）

> 推荐使用 `src/` 布局，避免“本地可 import、打包后失败”的常见问题。

- main.py
  - FastAPI 应用入口：创建 `app`、挂载路由、注册异常处理、启动配置。

#### api/（接口层：HTTP/鉴权/Schema 适配）

- api/v1/
  - 按版本管理路由文件；每个文件对应一个资源域（sessions/threads/messages...）。
  - `auth.py`、`model_configs.py` 作为**预留模块**：MVP 可以不在 `router.py` 中注册，后续打开即可。
- api/schemas/
  - Pydantic 请求/响应模型，只做“输入校验 + 输出结构”，不放业务逻辑。
- api/deps.py
  - FastAPI Dependencies：例如获取 DB session、当前用户（未来）、model config（未来）。
- api/error_handlers.py
  - 将领域错误统一映射为 HTTP 错误码与消息（便于前端做友好提示）。

#### domain/（领域层：稳定的业务语言）

- enums.py
  - 领域枚举：ThreadStatus、MessageRole、MessageType 等。
- models.py
  - 领域模型（纯数据结构/不依赖框架）。
- errors.py
  - 领域错误（例如 MergeHasActiveChildren、InvalidParentMerge 等）。

#### app/（用例层：把 PRD 行为变成可调用服务）

- app/services/
  - 用例编排：创建分支、切换、发送消息、合并生成简报。
  - 这里是“业务入口”，路由层只负责调用这些 service。
- app/policies/
  - 业务策略的可替换实现：逐级合并校验、建议频控、简报模板版本选择等。
  - 这样未来做 A/B 或替换策略，不会污染 service。

#### graph/（LangGraph 相关：图定义、节点、提示词）

- graph/state.py
  - LangGraph 状态结构（Pydantic 或 TypedDict）。
- graph/graphs/
  - 多张图拆分：例如 `chat_graph`（生成回复/建议），`merge_graph`（生成简报）。
- graph/nodes/
  - 每个节点一个文件：load_context/detect_suggestion/generate_reply/generate_brief。
- graph/prompts/
  - 提示词模板文件（markdown/jinja2 等），集中管理，便于迭代与版本化。

#### infra/（基础设施层：可替换的“外部世界适配器”）

- infra/db/
  - 数据库连接、ORM 模型、Repository 实现。
  - repositories/：按聚合根拆分（sessions/threads/messages/merges）。
- infra/vectorstore/
  - Chroma 客户端、brief 索引的读写封装（collection 命名、metadata、检索 topK）。
- infra/llm/
  - LLM provider 抽象与工厂：为未来“模型配置/多 provider”留空间。
- infra/auth/
  - 认证相关的基础实现（密码哈希、token 生成/校验）。MVP 可不启用。

#### core/（横切能力：配置、日志、时间、鉴权占位）

- core/config.py
  - 配置读取（环境变量 -> 配置对象）。
- core/logging.py
  - 日志初始化与格式（可加 request_id）。
- core/security.py
  - 鉴权/授权的依赖入口（即使 MVP 不启用，也建议留文件位）。

### 2.4 tests/（可选，暂不考虑）

你当前明确“测试框架暂不考虑”，因此可以先不创建 `tests/` 目录。

但建议在目录树中保留“reserved”位置：等后续需要测试时再补充即可。

### 2.5 scripts/（本地开发脚本）

- scripts/dev.ps1
  - Windows 下启动/迁移/格式化等一键脚本。
- scripts/dev.sh
  - macOS/Linux 同类脚本。

### 2.6 migrations/（可选）

- migrations/
  - 如果引入 Alembic/迁移工具，用于管理数据库 schema 版本。
  - MVP 阶段可先不加，等模型稳定再引入。

## 3. 目录结构的扩展点（对齐“登录/注册/模型配置”）

本目录结构里，以下位置专门为后续扩展预留：

- 登录/注册：`api/v1/auth.py` + `api/schemas/auth.py` + `infra/auth/` + `core/security.py`
- 模型配置：`api/v1/model_configs.py` + `api/schemas/model_configs.py` + `infra/llm/`
- 多租户/权限：在 `api/deps.py` 注入 current_user/workspace，并在 `infra/db/repositories` 层统一加过滤

## 4. 已确认的约束（更新）

1) 这是后端仓库，前端在另一个仓库：本仓库不保留 `backend/` 顶层。
2) 测试框架暂不考虑：`tests/` 目录可先不创建，后续需要时再补。
