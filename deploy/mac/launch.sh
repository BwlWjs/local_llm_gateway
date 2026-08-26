#!/bin/bash
# ModelRelay launcher: start the gateway backend and open the control UI.
set -euo pipefail

HOST="${MODELRELAY_HOST:-127.0.0.1}"
PORT="${MODELRELAY_PORT:-8000}"
URL="http://${HOST}:${PORT}"
PYTHON="${MODELRELAY_PYTHON:-python3}"

if ! curl -s -o /dev/null "${URL}/healthz"; then
  echo "Starting ModelRelay backend on ${HOST}:${PORT} ..."
  nohup "${PYTHON}" -m local_llm_gateway >/tmp/modelrelay.log 2>&1 &
  for _ in $(seq 1 30); do
    curl -s -o /dev/null "${URL}/healthz" && break
    sleep 0.5
  done
fi

open "${URL}"
