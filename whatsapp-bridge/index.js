import express from "express";
import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import pino from "pino";
import qrcode from "qrcode-terminal";

const token = process.env.BRIDGE_TOKEN || "change-me-bridge";
const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const port = Number(process.env.BRIDGE_PORT || 3001);
let sock = null;

async function startSocket() {
  const { state, saveCreds } = await useMultiFileAuthState("./auth");
  sock = makeWASocket({
    auth: state,
    logger: pino({ level: "silent" }),
    printQRInTerminal: false,
  });
  sock.ev.on("creds.update", saveCreds);
  sock.ev.on("connection.update", (update) => {
    if (update.qr) {
      console.log("Scan this QR in WhatsApp > Linked devices");
      qrcode.generate(update.qr, { small: true });
    }
    if (update.connection === "open") console.log("WhatsApp linked");
    if (update.connection === "close") {
      const code = update.lastDisconnect?.error?.output?.statusCode;
      if (code !== DisconnectReason.loggedOut) startSocket();
    }
  });
  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;
    for (const message of messages) {
      const body = message.message?.conversation
        || message.message?.extendedTextMessage?.text
        || "";
      if (!body) continue;
      const payload = {
        chat_id: message.key.remoteJid,
        name: message.pushName || "",
        body,
        from_me: Boolean(message.key.fromMe),
        is_group: String(message.key.remoteJid).endsWith("@g.us"),
      };
      await fetch(`${backend}/webhook`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Bridge-Token": token,
        },
        body: JSON.stringify(payload),
      }).catch((error) => console.error("backend unreachable", error.message));
    }
  });
}

const api = express();
api.use(express.json());
api.post("/send", async (req, res) => {
  if (req.header("x-bridge-token") !== token) return res.status(401).json({ error: "bad token" });
  if (!sock) return res.status(503).json({ error: "not linked" });
  const jid = req.body.chat_id.includes("@")
    ? req.body.chat_id
    : `${req.body.chat_id}@s.whatsapp.net`;
  await sock.sendMessage(jid, { text: req.body.text });
  res.json({ ok: true });
});
api.listen(port, "127.0.0.1", () => console.log(`bridge send API on 127.0.0.1:${port}`));
startSocket();
