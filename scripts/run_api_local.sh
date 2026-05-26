#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"

if [ ! -x "${VENV_PYTHON}" ]; then
  echo "Venv nao encontrada. Rode: bash scripts/setup_venv.sh" >&2
  exit 1
fi

cd "${REPO_ROOT}"
"${VENV_PYTHON}" -m uvicorn main:app --app-dir app --host 0.0.0.0 --port "${API_PORT:-8000}" --reload
