# gitLLM

后端仓库（MVP）：`uv` + Python 3.12 + FastAPI +（预留）LangChain/LangGraph/Chroma。

## 本地开发（Windows / PowerShell）

1) 安装/准备 Python 3.12

- 如果你使用 `pyenv-win`：确保当前目录选择 `3.12.x`
- 或者直接安装官方 Python 3.12

2) 安装依赖并生成锁文件

```powershell
uv sync
```

3) 启动服务

```powershell
./scripts/dev.ps1
```

服务默认：

- Health: `GET http://localhost:8000/health`
- API: `GET http://localhost:8000/api/v1/settings`

## 环境变量

参考 `.env.example`，本地可新建 `.env` 覆盖默认配置。
