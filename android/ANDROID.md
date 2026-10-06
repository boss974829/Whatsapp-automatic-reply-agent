# Use this on Android with Termux

WhatsApp's official app cannot load this agent. The practical phone paths are below.

## Path A, recommended: control from Android

Run the agent on a computer that stays on.

1. On the computer, start `uvicorn` and the bridge, then scan the QR once.
2. Find the computer's LAN address, for example `192.168.1.20`.
3. On the phone, open Chrome at `http://192.168.1.20:8000`.
4. Sign in with `DASHBOARD_PASSWORD`.
5. Chrome menu, Add to Home screen. That icon opens the approval queue.
6. Leave auto-reply paused until a simulated message looks right.

The phone does not hold the WhatsApp session. Closing Chrome does not stop replies.

## Path B: run the bridge on the phone

Termux from F-Droid, not the old Play Store build.

```bash
pkg update -y
pkg install -y python nodejs git
git clone https://github.com/boss974829/Whatsapp-automatic-reply-agent.git
cd Whatsapp-automatic-reply-agent
bash android/termux-setup.sh
```

The script makes a virtualenv, installs Python packages, installs the bridge, and prints the next two commands. Scan the QR from WhatsApp, Linked devices. Use a spare number. Android can kill Termux when the screen locks. `termux-wake-lock` reduces that, it does not remove it.

## Path C: official Cloud API

Create a Meta WhatsApp app, set the webhook to `/cloud/webhook`, and put the token in `.env`. Then the Android dashboard is only the approval page. This is the path to use if the number matters.

## What not to do

Do not install an unofficial mod of WhatsApp. Do not paste session files into chat. Do not leave `ALLOWED_CONTACTS` empty: this build ignores everyone until you list numbers.
