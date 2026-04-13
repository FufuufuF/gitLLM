param(
  [string]$ServerHost = "0.0.0.0",
  [int]$Port = 9090
)

$ErrorActionPreference = "Stop"

# 使用 ${} 明确变量范围
Write-Host "[gitLLM] Starting dev server on ${ServerHost}:${Port}" -ForegroundColor Cyan

# 运行命令
uv run uvicorn src.main:app --reload --host $ServerHost --port $Port