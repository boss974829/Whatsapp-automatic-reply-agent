"""Shared settings. Secrets stay in the environment, never in git."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class Settings:
    owner_name: str = os.getenv("OWNER_NAME", "Boss")
    dashboard_password: str = os.getenv("DASHBOARD_PASSWORD", "change-me")
    bridge_token: str = os.getenv("BRIDGE_TOKEN", "change-me-bridge")
    bridge_url: str = os.getenv("BRIDGE_URL", "http://127.0.0.1:3001")
    backend_port: int = _int("BACKEND_PORT", 8000)
    data_dir: Path = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
    db_path: Path = data_dir / "agent.db"
    allowlist: set[str] = {
        item.strip()
        for item in os.getenv("ALLOWED_CONTACTS", "").split(",")
        if item.strip()
    }
    allow_groups: bool = _bool("ALLOW_GROUPS", False)
    paused: bool = _bool("START_PAUSED", True)
    takeover_minutes: int = _int("TAKEOVER_MINUTES", 20)
    cooldown_seconds: int = _int("COOLDOWN_SECONDS", 25)
    hourly_cap: int = _int("HOURLY_CAP", 12)
    quiet_start: str = os.getenv("QUIET_START", "23:00")
    quiet_end: str = os.getenv("QUIET_END", "07:30")
    timezone: str = os.getenv("TIMEZONE", "Asia/Kolkata")
    disclose: bool = _bool("DISCLOSE_AUTO_REPLY", True)
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    cloud_token: str = os.getenv("WHATSAPP_TOKEN", "")
    cloud_phone_id: str = os.getenv("WHATSAPP_PHONE_ID", "")
    cloud_verify: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "verify-me")


settings = Settings()
