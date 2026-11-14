# Scam Guard — AI Scam Call Detection & Defense Agent

Live call conversations ko screen karta hai, scam indicators detect karta hai,
aur user ko real-time warning + voice briefing deta hai.

- **Hybrid risk engine** — deterministic heuristics (regex + weighted red flags)
  hamesha chalte hain; agar LLM API key configure hai toh LLM deep analysis
  karta hai aur final score heuristics ke floor se neeche nahi jaata
  (conservative flagging).
- **Real-time feed** — WebSocket per call: har transcript segment par live
  provisional score, phir final LLM analysis.
- **Voice briefings** — Fish Audio S2.1 Pro se spoken incident summary
  (graceful degradation: key na ho toh text-only).
- **Dashboard** — dark-theme single-page app: simulator, live screening,
  incident log, defense stats, red-flag breakdown.
- **Storage** — SQLite, zero-config. Webhook-ready API (Twilio-style
  transcription ingest).

## Architecture

```
                        +---------------------+
 WebSocket /ws/calls/*  |      EventHub       |
 ---------------------->|  (in-memory pubsub) |
                        +----------+----------+
                                   |
+--------+   +-----------+   +-----v------+   +-------------+
| FastAPI|-->| CallStore |-->| RiskEngine |--->|  SQLite    |
|  /api  |   |  (SQLite) |   +-----+------+   +-------------+
+--------+                 |     |
                            |     |  heuristics (always)
                            |     |  LLM (OpenAI-compatible, if key set)
                            +-----+
                                   |
                        +----------v----------+
                        | Fish Audio S2.1 Pro |  (TTS briefings, if key set)
                        +---------------------+
```

## Quick start

```bash
cd scam-guard
./run.sh                 # venv + deps + uvicorn on :8000
# browser: http://localhost:8000
```

Ya manually:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # apne keys daalo
uvicorn app.main:app --reload --port 8000
```

Pehli baar chalne par 4 sample calls seed ho jate hain
(benign appointment, bank OTP scam, fake IRS refund, fake tech support).

## Configuration (.env)

| Var | Default | Notes |
|---|---|---|
| `SCAMGUARD_LLM_PROVIDER` | `openai` | `openai` / `groq` / `google` / `xai` / `local` (Ollama) / `custom` |
| `SCAMGUARD_LLM_API_KEY` | — | koi bhi OpenAI-compatible key. Khaali ho toh heuristics-only mode. |
| `SCAMGUARD_LLM_MODEL` | `gpt-4o-mini` | provider ke hisaab se |
| `SCAMGUARD_LLM_BASE_URL` | provider preset | custom endpoints (proxy, Ollama) ke liye |
| `SCAMGUARD_USE_HEURISTICS` | `1` | deterministic layer |
| `SCAMGUARD_HARD_FLAG_THRESHOLD` | `70` | is threshold se upar heuristics floor LLM score ko override karta hai |
| `SCAMGUARD_FISH_API_KEY` | — | Fish Audio key; khaali ho toh briefings text-only |
| `SCAMGUARD_FISH_MODEL` | `S2.1` | Fish Audio model id |
| `SCAMGUARD_FISH_BASE_URL` | `https://api.fish.audio` | |
| `SCAMGUARD_FISH_REFERENCE_ID` | — | optional voice-clone reference |
| `SCAMGUARD_DB_PATH` | `data/scamguard.db` | |
| `SCAMGUARD_SEED_ON_START` | `1` | |
| `SCAMGUARD_SIM_SEGMENT_DELAY` | `0.5` | simulator ke beech segment delay (sec) |

### Fish Audio endpoint note

TTS call `POST {base}/v1/tts` jaati hai JSON body + Bearer auth ke saath.
Agar Fish Audio ke current docs ka endpoint/path alag hai toh bas
`SCAMGUARD_FISH_BASE_URL` adjust karein — code change nahi.

## API

Swagger docs: `http://localhost:8000/docs`

- `GET /health` — status + configured providers
- `GET /api/calls?status=&min_risk=&limit=` — incident list
- `GET /api/calls/{id}` / `PATCH` / `DELETE` — incident manage
  (`status: dismissed | confirmed_scam`)
- `POST /api/calls` — webhook ingest (transcript ke saath; auto-analyze)
- `POST /api/calls/{id}/analyze` — manual re-run
- `GET /api/calls/stats` — dashboard KPIs
- `GET /api/simulator/scenarios` — bundled scenarios
- `POST /api/simulator/run` — simulated live call (202 + call id)
- `WS /ws/calls/{id}` — live events: `call_state`, `segment` (provisional
  score ke saath), `analysis_completed`, `stream_done`
- `POST /api/tts/briefing/{id}` — spoken briefing generate karo
- `GET /api/tts/briefing/{id}/audio` — WAV stream
- `POST /api/tts/synthesize` — free-form TTS (connectivity test)

### Webhook example (Twilio-style)

```bash
curl -X POST http://localhost:8000/api/calls \
  -H 'Content-Type: application/json' \
  -d '{"source_number":"+1-212-555-0187","caller_id_name":"Chase Bank Security",
       "transcript":[
         {"speaker":"caller","text":"Your account is compromised. Read me the one time password."},
         {"speaker":"user","text":"What password?"}]}'
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests LLM/Fish keys use nahi karte — heuristics fallback aur API
graceful-degradation paths hi cover hote hain.

## Production notes

- Multi-worker scaling ke liye `app/realtime/hub.py` ke in-memory hub ko
  Redis/MQTT-backed implementation se swap karein (interface same).
- Auth: production mein `/api/calls` (write) par bearer-token gate lagayein —
  abhi CORS open hai dev ke liye.
- Audio briefings disk par `data/audio/briefings/` mein store hote hain;
  object storage se serve karne ka option baad mein add karein.
