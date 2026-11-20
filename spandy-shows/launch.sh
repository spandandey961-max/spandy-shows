#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ "${1:-}" = "--trusted-local" ]; then
  export SPANDY_EXECUTION_MODE=trusted-local SPANDY_TRUST_LOCAL_CODE=1
fi
printf '%s\n' 'Spandy Shows — See your code, step by step.' 'Open http://127.0.0.1:8000'
exec .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
