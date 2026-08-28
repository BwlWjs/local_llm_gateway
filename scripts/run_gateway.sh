#!/bin/bash
# ModelRelay gateway launcher (portable: repo venv by default, overridable).
# Sources .env, then runs uvicorn. Used by the systemd unit and manual starts.
# - VM / standard dev: relies on the repo-local .venv/bin/python (default).
# - Host local copy: set MODELRELAY_PYTHON to a venv with the project installed.
set -euo pipefail

cd "$(dirname "$0")/.."

# Load runtime configuration (GATEWAY_* vars). .env is per-environment, gitignored.
if [ -f ./.env ]; then
  set -o allexport
  # shellcheck source=/dev/null
  source ./.env
  set +o allexport
fi

PYTHON="${MODELRELAY_PYTHON:-./.venv/bin/python}"
HOST="${MODELRELAY_HOST:-0.0.0.0}"
PORT="${MODELRELAY_PORT:-8000}"

echo "Starting ModelRelay on ${HOST}:${PORT} (python: ${PYTHON})"
exec "${PYTHON}" -m uvicorn local_llm_gateway.main:app --host "${HOST}" --port "${PORT}"
