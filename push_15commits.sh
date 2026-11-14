#!/usr/bin/env bash
# Scam Guard — 15 logical commits + push to github.com/kvianAR/scam-guard
# Run from: /Users/Apple/Projects/Claude/scam-guard

set -euo pipefail

GH_USER="kvianAR"
REPO="scam-guard"

echo "=== Scam Guard: 15 commits + push to $GH_USER/$REPO ==="

# 1. Init
git init
git config user.name "kvianAR"
git config user.email "kvianar@users.noreply.github.com"

# Commit 1: Config & environment
git add .env.example .gitignore requirements.txt requirements-dev.txt
git commit -m "chore: add project config, dependencies, and environment template"

# Commit 2: Core models & enums
git add app/models.py
git commit -m "feat: add core models (Call, RiskLevel, CallStatus, CallType, TranscriptSegment)"

# Commit 3: Configuration system
git add app/config.py
git commit -m "feat: add pydantic-settings based configuration with provider presets"

# Commit 4: SQLite storage layer
git add app/storage.py
git commit -m "feat: add SQLite storage with CallStore (CRUD, stats, indexes)"

# Commit 5: Scam pattern rubric (16 patterns)
git add app/engine/rubric.py
git commit -m "feat: add scam detection rubric with 16 weighted patterns and LLM prompts"

# Commit 6: Heuristic scorer (deterministic)
git add app/engine/heuristics.py
git commit -m "feat: add deterministic heuristic scorer with regex-based red flags"

# Commit 7: LLM client (OpenAI-compatible)
git add app/engine/llm.py
git commit -m "feat: add OpenAI-compatible LLM client for deep risk analysis"

# Commit 8: Hybrid RiskEngine
git add app/engine/risk.py
git commit -m "feat: add hybrid RiskEngine (heuristics floor + LLM refinement)"

# Commit 9: API routes - calls CRUD + webhook
git add app/api/calls.py
git commit -m "feat: add calls API (list, create, analyze, update, delete, stats)"

# Commit 10: API routes - simulator
git add app/api/simulator.py
git commit -m "feat: add call simulator with scenario loading and live streaming"

# Commit 11: API routes - TTS voice briefings
git add app/api/tts.py
git commit -m "feat: add Fish Audio S2.1 Pro TTS integration for voice briefings"

# Commit 12: API routes - WebSocket live feed
git add app/api/ws.py
git commit -m "feat: add WebSocket endpoint for real-time call screening events"

# Commit 13: FastAPI app + health + static mounting
git add app/main.py app/__init__.py
git commit -m "feat: add FastAPI application with lifespan, CORS, health endpoint"

# Commit 14: Dashboard (dark theme, simulator, live ring, stats)
git add static/index.html
git commit -m "feat: add dark-theme dashboard with live screening, incident log, stats"

# Commit 15: Tests, seed data, Docker, docs
git add tests/ scripts/seed_data.py tests/fixtures/calls/ Dockerfile docker-compose.yml .dockerignore run.sh README.md
git commit -m "feat: add tests, fixtures, seed data, Docker, and documentation"

# Push
git branch -M main
git remote add origin https://github.com/$GH_USER/$REPO.git
echo "Pushing to https://github.com/$GH_USER/$REPO ..."
git push -u origin main

echo "=== DONE: $REPO pushed with 15 commits ==="