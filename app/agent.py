"""Reply decision. Rules first, model second, hold when unsure."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.config import settings
from app.policy import detect_script, disclose, hold_reason, in_quiet_hours, keyword_reply, load_rules

ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    path = ROOT / "data" / "kb" / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def decide(text: str, history: list[dict[str, str]]) -> dict:
    rules = load_rules()
    reason = hold_reason(text)
    if in_quiet_hours():
        draft = rules.get("away") or "I will reply after quiet hours."
        return {"reply": disclose(draft), "grounded": True, "needs_owner": True, "reason": "quiet hours"}
    if reason:
        return {
            "reply": disclose("I need to check this myself before answering."),
            "grounded": True,
            "needs_owner": True,
            "reason": reason,
        }
    canned = keyword_reply(text, rules)
    if canned:
        return {"reply": disclose(canned), "grounded": True, "needs_owner": False, "reason": "keyword rule"}
    if not settings.llm_api_key and "localhost" not in settings.llm_base_url and "127.0.0.1" not in settings.llm_base_url:
        script = detect_script(text)
        fallback = {
            "hi": "Message mil gaya. Main thodi der mein reply karta hoon.",
            "hinglish": "Message dekh liya. Main check karke reply karta hoon.",
            "en": "Got your message. I will reply once I have checked.",
        }[script]
        return {"reply": disclose(fallback), "grounded": True, "needs_owner": True, "reason": "no model configured"}
    return _ask_model(text, history)


def _ask_model(text: str, history: list[dict[str, str]]) -> dict:
    facts = _read("about_me.md")
    style = _read("style.md")
    transcript = "\n".join(f"{item['direction']}: {item['body']}" for item in history[-6:])
    system = f"""You write short WhatsApp replies as {settings.owner_name}.
Match the sender language: Hindi, Hinglish, or English.
Use only facts from NOTES. If a fact is missing, set grounded=false and needs_owner=true.
Hold for money, meetings, medical, secrets, or anything only the owner can promise.
Return JSON only: {{"reply":"","grounded":true,"needs_owner":false}}

NOTES:
{facts}

STYLE:
{style}
"""
    payload = {
        "model": settings.llm_model,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"History:\n{transcript}\n\nNew message:\n{text}"},
        ],
    }
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key or 'local'}"},
            json=payload,
            timeout=40,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content[content.find("{") : content.rfind("}") + 1])
        reply = disclose(str(parsed.get("reply") or "").strip())
        grounded = bool(parsed.get("grounded"))
        needs_owner = bool(parsed.get("needs_owner"))
        if not reply:
            return {"reply": "", "grounded": False, "needs_owner": True, "reason": "empty model reply"}
        return {
            "reply": reply,
            "grounded": grounded,
            "needs_owner": needs_owner,
            "reason": "model",
        }
    except Exception:
        return {"reply": "", "grounded": False, "needs_owner": True, "reason": "model failed closed"}
