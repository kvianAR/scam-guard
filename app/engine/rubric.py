"""Shared scoring rubric: scam patterns, category labels, prompts, JSON parsing.

Everything the LLM must score against is defined here so the heuristic and LLM
engines stay consistent.
"""
from __future__ import annotations

import json
import re
from typing import Any

# ---------------------------------------------------------------------------
# Scam categories & the patterns that point at them
# ---------------------------------------------------------------------------
PATTERNS: dict[str, list[dict[str, Any]]] = {
    "banking_fraud": [
        {"id": "bank_impostor", "label": "Bank impersonation", "category": "banking_fraud",
         "weight": 90,
         "regex": r"\b(feb|fed)\b|\bfederal reserve\b|\bsec\b|\bsbi\b|\bhsbc\b|\bstate bank\b",
         "why": "Fraudsters impersonate banks/reserve authorities to extract 'verification' details."},
        {"id": "account_compromised", "label": "Claim of compromised account / forced transfer",
         "category": "banking_fraud", "weight": 85,
         "regex": r"your account (is|was) (compromised|flagged|frozen|suspended)|transfer (your )?(entire|all) (balance|funds)|move your money to a (secure|safe) account|verification (number|transfer)",
         "why": "Urgent 'account is compromised, move your money' scripts are a classic banking-fraud play."},
        {"id": "urgent_money_transfer", "label": "Urgent money-transfer demand", "category": "banking_fraud",
         "weight": 70,
         "regex": r"(send|transfer|wire|pay) (us )?(your|a) (money|funds|amount)|wire transfer|crypto (payment|transfer|to protect your money)|bitcoin wallet|gift card payment",
         "why": "Direct requests to wire money or buy gift cards are hallmarks of financial fraud."},
    ],
    "identity_theft": [
        {"id": "id_harvest", "label": "Identity document harvest", "category": "identity_theft",
         "weight": 80,
         "regex": r"your (id|identification|social security number|ssn|dob|date of birth|pan|aadhaar)|send (us )?(your|the) (id|scan|photo of your (id|passport|license))|what is your (full )?(name|address|dob|ssn|password)",
         "why": "Asking for ID documents, SSN or DOB enables account takeovers and identity theft."},
        {"id": "password_credential", "label": "Credential / OTP harvest", "category": "identity_theft",
         "weight": 95,
         "regex": r"(your (password|pin|otp|cvv|two factor|2fa)|don'?t (ever|share) (share )?(the )?(otp|pin|cvv|password)|i (am|'?m) (verifying|checking) your (account|id)|read me the (code|number) (that) (just|came) (in|on) your (phone|sms)|one time password)",
         "why": "No legitimate organization asks a caller to recite their OTP, CVV or password on a phone call."},
    ],
    "advance_fee": [
        {"id": "fee_to_release", "label": "Advance-fee / release-of-funds demand",
         "category": "advance_fee", "weight": 90,
         "regex": r"release (your )?(funds|money|prize|incentive|compensation)|pay (a )?(fee|charge|processing|verification) (to|before) (release|receive)|you (will )?(be|have been) (selected|won|awarded)|congratulations.*(selected|won)|claim (your )?(prize|reward|payout|incentive)",
         "why": "'Pay a small fee first, then receive a large amount' is the advance-fee fraud pattern."},
        {"id": "crypto_reclaim", "label": "Recovery / crypto-asset reclaim promise",
         "category": "advance_fee", "weight": 85,
         "regex": r"(recovery (agent|company)|recover (your )?(crypto|funds|investment|stolen)|investment (portfolio|account) .{0,20}recover|we can get (your )?money (back|recovered))",
         "why": "'Recovery' offers are themselves a second-wave scam on top of the original loss."},
    ],
    "phishing_technical_support": [
        {"id": "tech_support", "label": "Fake IT / tech-support escalation",
         "category": "phishing_technical_support", "weight": 75,
         "regex": r"(microsoft (windows|office) (support|security)|technical (support|team)|your (computer|laptop|device) (is |was )?(infected|flagged|compromised|under attack)|i'?ve (gotten|received) a (security|malware|virus) (alert|warning) (about|from) (your|on) (your )?(device|computer))",
         "why": "Tech-support scams push victims to remote-access their own device to steal data."},
        {"id": "remote_access", "label": "Remote-access / software install request",
         "category": "phishing_technical_support", "weight": 90,
         "regex": r"remote (access|desktop|support (software|tool))|install (teamviewer|anydesk|any desktop|a (remote )?software|the (tool|software))|log into your (banking|email|device) (with|alongside) me|type (your )?(banking|password|login) (credentials|details) (while|i)",
         "why": "Remote-control tools and shared logins are used to hijack banking sessions."},
    ],
    "romance": [
        {"id": "romance_scam", "label": "Romance / relationship pressure for money",
         "category": "romance", "weight": 80,
         "regex": r"i (love|miss) you .{0,20}(send|transfer|money|crypto|gift|wire)|urgent (travel|medical|emergency) (fee|cost)|i (need|must) (send|transfer) (you )?money|airfare|hotel (deposit|reservation) for (us|our) (visit|date|meeting)",
         "why": "Romance-advance-fee scams monetize emotional attachment with 'emergencies'."},
    ],
    "tax_refund": [
        {"id": "tax_refund", "label": "Tax-refund / government benefit claim",
         "category": "tax_refund", "weight": 85,
         "regex": r"(tax (refund|benefit)|irs|hm (rc|revenue)|government (payout|grant|credit)|outstanding (refund|payment) .{0,20}(claim|issue)|pay (a small )?(fee|charge) (to|to) (issue|release) (your )?(refund|check|payment))",
         "why": "Fake tax-refund offers bait victims into paying 'processing fees' for a check that never exists."},
    ],
    "tech_support": [
        {"id": "tech_support_v2", "label": "Tech-support pressure",
         "category": "tech_support", "weight": 70,
         "regex": r"our (it|tech|systems) (team|support)|scheduled (maintenance|update|patch)|your (system|server|workspace) (is|was) (offline|experiencing)|i'?ll (need you to) (install|run) (the )?(tool|app|update)",
         "why": "Pressure to install a tool during 'system maintenance' is social engineering."},
    ],
}

# Generic red-flag keywords that add points regardless of category
GENERIC_FLAGS: list[dict[str, Any]] = [
    {"id": "urgency_pressure", "label": "High-pressure / urgency language",
     "weight": 30,
     "regex": r"\b(hurricane?|immediately|right now|as soon as possible|tonight|by end of day|last chance|time ?sensitive|within the hour|before (it|the) (is|gets))\b|\burgent\b",
     "why": "Urgency is the #1 manipulation lever — it bypasses the victim's normal checks."},
    {"id": "secrecy_demand", "label": "Demands for secrecy / no-tell-others",
     "weight": 30,
     "regex": r"(don'?t (tell|let|inform) (anyone|your (family|spouse|wife|husband|boss|friend)|the (bank|police|authorities))|keep (this|it) (quiet|between us|secret)|please don'?t (discuss|mention|share) (this|it) (with|to) (anyone|family|friends))",
     "why": "Scammers isolate victims from people who might warn them."},
    {"id": "cash_or_giftcard", "label": "Payment via cash / gift card / crypto wallet",
     "weight": 30,
     "regex": r"gift ?cards?|apple ?store ?card|steam ?(wallet|codes?)|amazon ?gift ?card|bitcoin|crypto ?(wallet|payment)|\busdt\b|\busdc\b|wire ?me|pay ?pal ?to ?my",
     "why": "Irreversible, untraceable payment rails are preferred by fraudsters."},
    {"id": "foreign_or_unknown_caller", "label": "Caller from unusual region or with spoofed ID",
     "weight": 20,
     "regex": r"(international|overseas) (calling|number)|caller ?id (spoof|unknown|blocked|private)",
     "why": "Spoofed / unusual caller IDs are a weak but real indicator of fraud."},
]

ALL_PATTERNS = [p for p in PATTERNS.values() for p in p] + GENERIC_FLAGS
PATTERN_BY_ID: dict[str, dict[str, Any]] = {p["id"]: p for p in ALL_PATTERNS}

CATEGORY_LABELS: dict[str, str] = {
    "banking_fraud": "Banking / impersonation fraud",
    "identity_theft": "Identity / credential theft",
    "advance_fee": "Advance-fee / prize scam",
    "phishing_technical_support": "Phishing / fake tech support",
    "romance": "Romance / relationship scam",
    "tax_refund": "Tax-refund / government benefit",
    "tech_support": "Tech-support social engineering",
    "generic_suspicion": "Generic suspicion",
    "legitimate": "Likely legitimate",
}

RISK_LEVEL_THRESHOLDS = [(90, "critical"), (70, "high"), (40, "medium"), (15, "low")]


def level_for(score: int) -> str:
    for threshold, level in RISK_LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return "safe"


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are ScamGuard's fraud-detection LLM. You analyze live phone-call
transcripts and classify scam risk for a consumer fraud-defense product.

Be conservative: false alarms annoy users; missed scams cause financial damage.
Score 0-100 based on manipulation intensity, financial-pressure intensity, and
the credibility of the caller's stated purpose. Use the exact JSON schema
shown in the user prompt — no prose, no markdown fences."""


def build_user_prompt(transcript_text: str) -> str:
    pattern_table = "\n".join(
        f"  - {p['id']}: {p['label']} (weight {p['weight']})"
        for p in ALL_PATTERNS
    )
    return f"""
The transcript below is a live phone call the user is currently in.

TRANSCRIPT:
\"\"\"{transcript_text}\"\"\"

Known scam pattern IDs and weights (you may add new IDs if needed):
{pattern_table}

Respond ONLY with valid JSON matching this exact schema:
{{
  "risk_score": <int 0-100>,
  "risk_level": "safe" | "low" | "medium" | "high" | "critical",
  "category": one of: {list(CATEGORY_LABELS.keys())},
  "verdict": "<one-sentence plain-English verdict>",
  "confidence": <float 0-1>,
  "red_flags": [ {{"id": "<pattern-id>", "label": "<text>", "weight": <int>}} ],
  "recommended_actions": ["<action 1>", "<action 2>", ...],
  "summary": "<2-3 sentence explanation for the user>"
}}
"""


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Parse LLM output, tolerating markdown fences / leading prose."""
    raw = raw.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise ValueError("LLM response did not contain JSON object")
    obj = json.loads(m.group(0))
    # Normalise & clamp
    score = obj.get("risk_score")
    try:
        score = int(score)
    except Exception:
        score = 0
    obj["risk_score"] = max(0, min(100, score))
    lvl = str(obj.get("risk_level", level_for(score))).lower()
    valid_levels = {"safe", "low", "medium", "high", "critical"}
    obj["risk_level"] = lvl if lvl in valid_levels else level_for(score)
    obj.setdefault("category", "generic_suspicion")
    obj.setdefault("verdict", "Unclassified")
    obj.setdefault("confidence", 0.5)
    obj.setdefault("red_flags", [])
    obj.setdefault("recommended_actions", ["Continue the call carefully", "Do not share OTP / PIN / CVV", "Hang up and call the organisation directly on its published number."])
    obj.setdefault("summary", "")
    return obj


BRIEFING_TEMPLATE = """
Here is a summary of the call you just took.

Caller identified as: {category}.
Risk level: {risk_level}.

{summary}

Recommended next steps:
{actions}

Please stay calm. You can safely end the call now.
"""
