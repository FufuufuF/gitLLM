#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "[gitLLM] Starting dev server on ${HOST}:${PORT}"

uv run uvicorn src.main:app --reload --host "${HOST}" --port "${PORT}"
