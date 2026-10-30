#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "Missing .env: run cp .env.example .env first (empty keys = evaluation mode)" >&2; exit 1; }
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi
set -a; . ./.env; set +a
export PORT="${PORT:-8010}"
echo "Nutrient audit evidence extraction on http://localhost:${PORT}"
exec ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
