"""OpenAI-compatible LLM client for deep risk analysis.

Works with OpenAI, Groq, Google (OpenAI-compatible endpoint), xAI, Ollama,
or any custom /v1/chat/completions base URL.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.engine import rubric

log = logging.getLogger("scamguard.llm")


class LLMError(Exception):
    pass


def analyze_with_llm(transcript_text: str) -> dict[str, Any]:
    """Call the configured LLM and return a normalised result dict.

    Raises LLMError if the provider is not configured or the call fails.
    """
    s = get_settings()
    base_url = s.default_llm_base_url
    if not s.llm_configured or not base_url:
        raise LLMError(
            "LLM not configured. Set SCAMGUARD_LLM_API_KEY (and optionally "
            "SCAMGUARD_LLM_BASE_URL / SCAMGUARD_LLM_PROVIDER) in .env"
        )

    headers = {"Content-Type": "application/json"}
    if s.llm_api_key:
        headers["Authorization"] = f"Bearer {s.llm_api_key}"

    payload = {
        "model": s.llm_model,
        "temperature": s.llm_temperature,
        "max_tokens": s.llm_max_tokens,
        "messages": [
            {"role": "system", "content": rubric.SYSTEM_PROMPT},
            {"role": "user", "content": rubric.build_user_prompt(transcript_text)},
        ],
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    log.info("Calling LLM %s (model=%s)", url, s.llm_model)
    try:
        resp = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=s.llm_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        raise LLMError(f"LLM HTTP {e.response.status_code}: {e.response.text[:300]}") from e
    except httpx.HTTPError as e:
        raise LLMError(f"LLM request failed: {e}") from e

    try:
        raw = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected LLM response shape: {str(data)[:300]}") from e

    result = rubric.parse_llm_json(raw)
    result["category_label"] = rubric.CATEGORY_LABELS.get(result["category"], result["category"])
    result["summary"] = result.get("summary") or _fallback_summary(result.get("red_flags", []))
    return result


def _fallback_summary(flags: list[dict[str, Any]]) -> str:
    """Fallback summary generator if the LLM returned an empty one."""
    if not flags:
        return "No clear scam indicators detected in this analysis window."
    names = ", ".join(f.get("label", f.get("id", "?")) for f in flags[:4])
    return f"Detected indicator(s): {names}."
