"""Deterministic gates. These run before any model and fail closed."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import settings

HOLD_PATTERNS = [
    (r"\b(otp|one[- ]time|password|pin code|cvv)\b", "secret or one-time code"),
    (r"\b(pay|payment|upi|gpay|phonepe|refund|invoice|rs\.?\s?\d+)\b", "money"),
    (r"\b(meet|meeting|call me|confirm|available at|kal aana)\b", "commitment"),
    (r"\b(address|aadhaar|pan card|bank account)\b", "private detail"),
    (r"\b(doctor|medicine|dose|emergency)\b", "health"),
]

AWAY_TEMPLATES = {
    "en": "Hey, I saw this. I will reply properly when I am free.",
    "hi": "Namaste, message mil gaya. Thodi der mein properly reply karta hoon.",
    "hinglish": "Hey, message dekh liya. Free hote hi reply karta hoon.",
}


def load_rules() -> dict:
    candidates = [
        settings.data_dir / "kb" / "rules.json",
        Path(__file__).resolve().parent.parent / "data" / "kb" / "rules.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {"keywords": [], "away": AWAY_TEMPLATES["hinglish"]}


def detect_script(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    hinglish = re.search(r"\b(kya|hai|nahi|bhai|yaar|kal|abhi|theek|haan)\b", text, re.I)
    return "hinglish" if hinglish else "en"


def in_quiet_hours(now: datetime | None = None) -> bool:
    zone = ZoneInfo(settings.timezone)
    current = now.astimezone(zone) if now else datetime.now(zone)
    start_h, start_m = [int(part) for part in settings.quiet_start.split(":")]
    end_h, end_m = [int(part) for part in settings.quiet_end.split(":")]
    start = current.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = current.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def hold_reason(text: str) -> str | None:
    lowered = text.lower()
    for pattern, reason in HOLD_PATTERNS:
        if re.search(pattern, lowered, re.I):
            return reason
    return None


def keyword_reply(text: str, rules: dict) -> str | None:
    lowered = text.lower()
    for rule in rules.get("keywords", []):
        needles = [item.lower() for item in rule.get("match", [])]
        if any(needle in lowered for needle in needles):
            return rule.get("reply")
    return None


def disclose(text: str) -> str:
    if not settings.disclose or text.lower().startswith("auto-reply"):
        return text
    return f"Auto-reply: {text}"
