#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Edit .env before going live."
fi
cd whatsapp-bridge
npm install
cd ..
echo
echo "Next, in two Termux sessions:"
echo "  source .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000"
echo "  cd whatsapp-bridge && npm start"
echo "Then open http://127.0.0.1:8000 in the phone browser."
