param(
  [string]$Host = "0.0.0.0",
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "[gitLLM] Starting dev server on $Host:$Port" -ForegroundColor Cyan

# Assumes you created/selected a Python 3.12 environment already.
# Use uv to run the app with the project dependencies.
uv run uvicorn gitllm.main:app --reload --host $Host --port $Port
