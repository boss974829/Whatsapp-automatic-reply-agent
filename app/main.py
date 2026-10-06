"""FastAPI control plane: webhook, dashboard, simulator, Cloud API."""

from __future__ import annotations

import secrets
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.agent import decide
from app.config import settings
from app import db

app = FastAPI(title="WhatsApp automatic reply agent")
sessions: set[str] = set()


class Incoming(BaseModel):
    chat_id: str
    name: str = ""
    body: str
    from_me: bool = False
    is_group: bool = False


class HoldAction(BaseModel):
    text: str | None = None


@app.on_event("startup")
def startup() -> None:
    db.init_db()


def _auth(token: str | None) -> None:
    if not token or token not in sessions:
        raise HTTPException(status_code=401, detail="login required")


def _bridge_ok(header: str | None) -> None:
    if not header or not secrets.compare_digest(header, settings.bridge_token):
        raise HTTPException(status_code=401, detail="bad bridge token")


def allowed(chat_id: str, is_group: bool) -> bool:
    if is_group and not settings.allow_groups:
        return False
    if not settings.allowlist:
        return False
    digits = "".join(ch for ch in chat_id if ch.isdigit())
    return digits in settings.allowlist or chat_id in settings.allowlist


async def send_whatsapp(chat_id: str, text: str) -> None:
    if settings.cloud_token and settings.cloud_phone_id and chat_id.isdigit():
        url = f"https://graph.facebook.com/v20.0/{settings.cloud_phone_id}/messages"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.cloud_token}"},
                json={"messaging_product": "whatsapp", "to": chat_id, "type": "text", "text": {"body": text}},
            )
            response.raise_for_status()
        return
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.bridge_url}/send",
            headers={"X-Bridge-Token": settings.bridge_token},
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()


def route(message: Incoming) -> dict[str, Any]:
    if message.from_me:
        db.save_message(message.chat_id, message.name, "owner", message.body)
        return {"action": "owner-noted"}
    if not allowed(message.chat_id, message.is_group):
        return {"action": "ignored", "reason": "not allowlisted"}
    db.save_message(message.chat_id, message.name, "in", message.body)
    mode = db.contact_mode(message.chat_id)
    if mode == "ignore":
        return {"action": "ignored", "reason": "contact ignore"}
    if db.owner_took_over(message.chat_id, settings.takeover_minutes):
        db.hold(message.chat_id, message.name, message.body, "", "you replied recently")
        return {"action": "held", "reason": "takeover"}
    choice = decide(message.body, db.recent_messages(message.chat_id))
    blocked = (
        db.is_paused()
        or mode == "ask"
        or choice["needs_owner"]
        or not choice["grounded"]
        or not choice["reply"]
        or db.sent_recently(message.chat_id, settings.cooldown_seconds)
        or db.sent_this_hour(message.chat_id) >= settings.hourly_cap
    )
    if blocked:
        reason = choice["reason"]
        if db.is_paused():
            reason = "paused"
        elif mode == "ask":
            reason = "contact asks first"
        db.hold(message.chat_id, message.name, message.body, choice["reply"], reason)
        return {"action": "held", "reason": reason, "draft": choice["reply"]}
    return {"action": "send", "text": choice["reply"], "reason": choice["reason"]}


@app.post("/webhook")
async def webhook(message: Incoming, x_bridge_token: str | None = Header(default=None)):
    _bridge_ok(x_bridge_token)
    result = route(message)
    if result["action"] == "send":
        await send_whatsapp(message.chat_id, result["text"])
        db.save_message(message.chat_id, message.name, "out", result["text"])
        db.log_event("sent", {"chat_id": message.chat_id, "reason": result["reason"]})
    return result


@app.post("/simulate")
async def simulate(message: Incoming, x_session: str | None = Header(default=None)):
    _auth(x_session)
    result = route(message)
    if result["action"] == "send":
        db.save_message(message.chat_id, message.name, "out", result["text"])
    return result


@app.post("/login")
async def login(request: Request):
    body = await request.json()
    if not secrets.compare_digest(str(body.get("password", "")), settings.dashboard_password):
        raise HTTPException(status_code=401, detail="wrong password")
    token = secrets.token_urlsafe(24)
    sessions.add(token)
    return {"token": token}


@app.get("/api/state")
def state(x_session: str | None = Header(default=None)):
    _auth(x_session)
    return {
        "paused": db.is_paused(),
        "holds": db.list_holds(),
        "contacts": db.list_contacts(),
        "allowlist_required": True,
    }


@app.post("/api/pause")
async def pause(request: Request, x_session: str | None = Header(default=None)):
    _auth(x_session)
    body = await request.json()
    db.set_paused(bool(body.get("paused")))
    return {"paused": db.is_paused()}


@app.post("/api/holds/{item_id}/send")
async def approve(item_id: int, action: HoldAction, x_session: str | None = Header(default=None)):
    _auth(x_session)
    item = db.claim_hold(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="not pending")
    text = action.text or item["draft"]
    if not text:
        db.mark_hold(item_id, "dismissed")
        return {"status": "dismissed"}
    await send_whatsapp(item["chat_id"], text)
    db.save_message(item["chat_id"], item["name"], "out", text)
    db.mark_hold(item_id, "sent")
    return {"status": "sent"}


@app.post("/api/holds/{item_id}/dismiss")
def dismiss(item_id: int, x_session: str | None = Header(default=None)):
    _auth(x_session)
    db.mark_hold(item_id, "dismissed")
    return {"status": "dismissed"}


@app.post("/api/contacts")
async def contacts(request: Request, x_session: str | None = Header(default=None)):
    _auth(x_session)
    body = await request.json()
    db.set_contact(body["chat_id"], body.get("name", ""), body.get("mode", "ask"))
    return {"ok": True}


@app.post("/api/schedule")
async def schedule(request: Request, x_session: str | None = Header(default=None)):
    _auth(x_session)
    body = await request.json()
    item_id = db.add_schedule(body["chat_id"], body["text"], int(body["send_at"]))
    return {"id": item_id}


@app.get("/cloud/webhook")
def cloud_verify(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == settings.cloud_verify:
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise HTTPException(status_code=403)


@app.post("/cloud/webhook")
async def cloud_inbound(request: Request):
    payload = await request.json()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            name = ""
            contacts = value.get("contacts") or []
            if contacts:
                name = contacts[0].get("profile", {}).get("name", "")
            for item in value.get("messages", []):
                if item.get("type") != "text":
                    continue
                message = Incoming(
                    chat_id=item.get("from", ""),
                    name=name,
                    body=item.get("text", {}).get("body", ""),
                )
                result = route(message)
                if result["action"] == "send":
                    await send_whatsapp(message.chat_id, result["text"])
                    db.save_message(message.chat_id, message.name, "out", result["text"])
    return {"ok": True}


@app.get("/health")
def health():
    return {"ok": True, "paused": db.is_paused()}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    page = (settings.data_dir.parent / "app" / "dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(page)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
