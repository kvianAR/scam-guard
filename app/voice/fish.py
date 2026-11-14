"""Fish Audio S2.1 Pro TTS integration.

Endpoint shape mirrors the documented Fish Audio REST TTS v1 pattern:
  POST {base}/v1/tts  with JSON body and Bearer auth.

If Fish Audio's actual endpoint differs, update the base URL / path in
.env (SCAMGUARD_FISH_BASE_URL / SCAMGUARD_FISH_MODEL) — no code change needed.
"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.config import get_settings

log = logging.getLogger("scamguard.fish")

TTS_ENDPOINT = "/v1/tts"


def synthesize(text: str, out_dir: Path) -> Path | None:
    """Generate a WAV briefing for the given text.

    Returns a path to the audio file on success, or None when the provider is
    not configured or the request fails (callers can degrade gracefully).
    """
    s = get_settings()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"briefing_{__import__('uuid').uuid4().hex[:8]}.wav"

    if not s.fish_configured:
        log.info("Fish Audio key not configured — skipping TTS.")
        return None

    headers = {"Authorization": f"Bearer {s.fish_api_key}", "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model": s.fish_model,
        "reference_id": s.fish_reference_id,
        "format": "wav",
    }
    url = f"{s.fish_base_url.rstrip('/')}{TTS_ENDPOINT}"
    log.info("Requesting TTS from %s", url)
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=s.fish_timeout)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)
        return out_path
    except httpx.HTTPError as e:
        log.warning("Fish Audio TTS request failed: %s", e)
        return None
