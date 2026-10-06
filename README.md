# WhatsApp automatic reply agent

Personal auto-reply for your own WhatsApp, with a phone-friendly approval dashboard.

This is an original project inspired by the shape of [Shahd132/Whatsapp-Assistant-Agent](https://github.com/Shahd132/Whatsapp-Assistant-Agent): a thin WhatsApp bridge, a Python decision service, and a local queue for anything the agent should not send alone. It is not a fork and does not copy that repo's prompts, dashboard, or style files.

Unofficial WhatsApp Web clients can get a personal number limited or banned. Use a spare number, keep the allowlist tight, and prefer the official WhatsApp Cloud API path for anything commercial.

## What the source project is

Shahd132/Whatsapp-Assistant-Agent is a single-owner assistant that answers in the owner's voice and holds uncertain replies.

| Piece | Built with | Job |
|---|---|---|
| Bridge | Node.js, whatsapp-web.js | Receive chats, resolve privacy IDs, send replies on localhost |
| Agent | Python, FastAPI, LangGraph, OpenAI | Transcribe, caption, draft a JSON reply, fail closed |
| Memory | SQLite | Holds, history, audit, 30-day retention |
| Speech / photos | faster-whisper, BLIP, edge-tts | Local voice notes, photo captions, spoken dashboard |
| Dashboard | One HTML file | Approve holds, pause, per-contact mode, Mika assistant |
| Safety | Allowlist, shared secret, eval set | Do not guess facts, do not send commitments |

A send happens only when the draft is non-empty, marked grounded, and not marked as needing the owner. Empty allowlist in that project means everyone, which this repo deliberately does not copy.

## What this version adds

- Rules that work with no API key: keywords, quiet hours, away text.
- Hindi, Hinglish, and English matching.
- Hard holds before the model: money, OTP, meetings, address, health.
- Default-off allowlist. Nobody is answered until you list their number.
- Starts paused.
- Human takeover: if you reply in a chat, auto-reply stays quiet there.
- Cooldown and hourly cap.
- Per-contact auto / ask / ignore.
- Scheduled follow-ups.
- Simulator, so you can test decisions without WhatsApp.
- OpenAI-compatible model slot: OpenAI, Groq, OpenRouter, or local Ollama.
- Official Cloud API webhook beside the personal bridge.
- Mobile dashboard you can pin on an Android home screen.
- Termux script for running the bridge on the phone.

## Android

Two ways. The first is the reliable one.

1. Run the agent on a computer or a small VPS. On the phone, open `http://YOUR-LAN-IP:8000`, log in, and use Add to Home screen. Approve or dismiss holds from the phone. The computer keeps the WhatsApp session alive.
2. Run on the phone with Termux. See [android/ANDROID.md](android/ANDROID.md). Android will kill background apps, so this is for testing, not for a number you cannot lose.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp contacts.example.json contacts.json
```

Edit `.env`. Set `DASHBOARD_PASSWORD`, `BRIDGE_TOKEN`, and `ALLOWED_CONTACTS` to real values. Put facts in `data/kb/about_me.md` and keyword replies in `data/kb/rules.json`.

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
cd whatsapp-bridge && npm install && npm start
```

Scan the QR from WhatsApp on the phone: Linked devices. Open `http://127.0.0.1:8000`, sign in, then unpause.

Cloud API instead of the bridge: set `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, and `WHATSAPP_VERIFY_TOKEN`, then point the Meta webhook at `https://YOUR-HOST/cloud/webhook`.

## Decision

```text
send = allowlisted AND not paused AND mode is auto
       AND draft exists AND grounded AND not needs_owner
       AND under cooldown AND under hourly cap
       AND you have not just replied in that chat
```

Everything else is held or ignored.

## Layout

```text
app/                 FastAPI, policy, agent, SQLite, dashboard
whatsapp-bridge/     Baileys session and localhost send API
android/             Termux setup
data/kb/             Facts, style, keyword rules
tests/               Policy checks
```

Do not commit `.env`, `data/agent.db`, `contacts.json`, or `whatsapp-bridge/auth/`. Those can send messages as you.
