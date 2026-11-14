#!/usr/bin/env bash
# One-command local start: venv + deps + seed + serve on :8000
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
mkdir -p data audio/briefings
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
