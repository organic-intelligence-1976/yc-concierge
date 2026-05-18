"""YC-Concierge — shared shell.

Receives inbound messages via AgentPhone (SMS/iMessage/voice) and AgentMail (email).
Whitelisted senders are routed to the appropriate vertical for triage; the
vertical decides what to do and returns a reply we send back through the
original channel.

For the 2026-05-17 hackathon, only the `cards` vertical is registered.
"""

import json
import os
import re
import sys
import threading

import stripe
from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

# Force-unbuffer stdout so prints show up in logs immediately
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import messaging
from verticals import cards

# ─── whitelist (in-app, not platform-level) ────────────────────────────────
# Comma-separated env vars. Phones in E.164 (+1...), emails in standard form.
# We normalize gmail local-part dots so a.b@gmail.com == ab@gmail.com.
def normalize_gmail(email: str) -> str:
    if email.endswith("@gmail.com"):
        local, _, domain = email.partition("@")
        return local.replace(".", "") + "@" + domain
    return email


def _csv_env(name):
    raw = os.environ.get(name, "")
    return {v.strip() for v in raw.split(",") if v.strip()}


WHITELIST_PHONES = _csv_env("WHITELIST_PHONES")
WHITELIST_EMAILS = {normalize_gmail(e) for e in _csv_env("WHITELIST_EMAILS")}

AGENTPHONE_AGENT_ID = os.environ.get("AGENTPHONE_AGENT_ID", "")
STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
stripe.api_key = STRIPE_SECRET_KEY

app = Flask(__name__)
app.register_blueprint(cards.bp)


def normalize_phone(s: str) -> str:
    digits = re.sub(r"\D", "", s or "")
    if len(digits) == 10:
        digits = "1" + digits
    return "+" + digits if digits else ""


def extract_email(s: str) -> str:
    if not s:
        return ""
    m = re.search(r"<([^>]+)>", s)
    return normalize_gmail((m.group(1) if m else s).strip().lower())


# ─── health / root ─────────────────────────────────────────────────────────
@app.get("/")
def health():
    return "yc-concierge: ok\n"


# ─── inbound: AgentPhone (SMS/iMessage) ────────────────────────────────────
@app.post("/webhook/agentphone")
def agentphone_webhook():
    payload = request.get_json(silent=True) or {}
    print(
        f"[AgentPhone webhook] event={payload.get('event')} channel={payload.get('channel')}",
        flush=True,
    )
    with open("/tmp/last_agentphone_payload.json", "w") as f:
        json.dump(payload, f, indent=2)

    event = payload.get("event")
    channel = payload.get("channel")
    data = payload.get("data") or {}
    from_raw = data.get("from", "")
    from_number = normalize_phone(from_raw)
    agent_id = payload.get("agentId") or AGENTPHONE_AGENT_ID
    imessage_number_id = os.environ.get("AGENTPHONE_IMESSAGE_NUMBER_ID") or None

    # ── Text intake (SMS/iMessage) ──
    if event == "agent.message" and channel in ("sms", "mms", "imessage"):
        if from_number not in WHITELIST_PHONES:
            print(f"  → blocked text: from={from_raw} (normalized {from_number})", flush=True)
            return "", 200

        message_text = data.get("message") or ""
        number_id = data.get("numberId")  # reply on the same line we received from
        sender_channel = "imessage" if channel == "imessage" else "sms"
        threading.Thread(
            target=_process_text_inbound,
            args=(message_text, from_raw, sender_channel, agent_id, number_id),
            daemon=True,
        ).start()
        return "", 200

    # ── Voice intake (call ended → process full transcript) ──
    if event == "agent.call_ended":
        if from_number not in WHITELIST_PHONES:
            print(f"  → blocked call: from={from_raw} (normalized {from_number})", flush=True)
            return "", 200

        transcript = data.get("transcript") or []
        text = "\n".join(
            f"{turn.get('role', '?')}: {turn.get('content', '')}" for turn in transcript
        )
        print(f"[Voice] call ended, {len(transcript)} turns, queuing background processing", flush=True)
        threading.Thread(
            target=_process_voice_inbound,
            args=(text, from_raw, agent_id, imessage_number_id),
            daemon=True,
        ).start()
        return "", 200

    # Voice mid-call agent.message events: ignore (hosted mode handles the conversation)
    return "", 200


# ─── background processors ────────────────────────────────────────────────
def _process_text_inbound(message_text, from_raw, sender_channel, agent_id, number_id):
    """Background worker for SMS/iMessage. Sends interstitial + final reply on the same line."""
    def send(body):
        messaging.send_sms(agent_id=agent_id, to_number=from_raw, body=body, number_id=number_id)

    try:
        reply = cards.handle_inbound(
            text=message_text,
            sender_contact=from_raw,
            sender_channel=sender_channel,
            interstitial_func=send,
        )
        send(reply)
    except Exception as e:
        print(f"[bg text] error: {e}", flush=True)
        try:
            send("Sorry, I hit an error processing that. Try again in a moment.")
        except Exception:
            pass


def _process_voice_inbound(transcript_text, from_raw, agent_id, imessage_number_id):
    """Background worker for voice call_ended. Always replies via the iMessage line
    (10DLC blocks the SMS line) since the caller's iPhone is whitelisted there."""
    def send(body):
        messaging.send_sms(
            agent_id=agent_id, to_number=from_raw, body=body, number_id=imessage_number_id,
        )

    try:
        reply = cards.handle_inbound(
            text=transcript_text,
            sender_contact=from_raw,
            sender_channel="voice",
            interstitial_func=send,
        )
        send(reply)
    except Exception as e:
        print(f"[bg voice] error: {e}", flush=True)
        try:
            send("Sorry, I hit an error processing the call. Try again in a moment.")
        except Exception:
            pass


def _process_email_inbound(body_text, from_addr, message_id):
    """Background worker for AgentMail. Replies on the same thread as the inbound message."""
    def send(text):
        if message_id:
            messaging.send_email_reply(message_id=message_id, text=text)
        else:
            messaging.send_email_new(to_addr=from_addr, subject="Re: your request", text=text)

    try:
        reply = cards.handle_inbound(
            text=body_text,
            sender_contact=from_addr,
            sender_channel="email",
            interstitial_func=send,
        )
        send(reply)
    except Exception as e:
        print(f"[bg email] error: {e}", flush=True)
        try:
            send("Sorry, I hit an error processing your request. Try again in a moment.")
        except Exception:
            pass


# ─── inbound: AgentMail (email) ────────────────────────────────────────────
@app.post("/webhook/agentmail")
def agentmail_webhook():
    payload = request.get_json(silent=True) or {}
    event_type = payload.get("event_type") or ""
    print(f"[AgentMail webhook] event_type={event_type}", flush=True)
    with open("/tmp/last_agentmail_payload.json", "w") as f:
        json.dump(payload, f, indent=2)

    if "received" not in event_type:
        return "", 200

    msg = payload.get("message") or {}
    from_raw = msg.get("from", "")
    from_addr = extract_email(from_raw)
    if from_addr not in WHITELIST_EMAILS:
        print(f"  → blocked email: from={from_raw} (normalized {from_addr})", flush=True)
        return "", 200

    body = msg.get("text") or msg.get("extracted_text") or ""
    message_id = msg.get("message_id")
    threading.Thread(
        target=_process_email_inbound,
        args=(body, from_addr, message_id),
        daemon=True,
    ).start()
    return "", 200


# ─── Stripe payment success ────────────────────────────────────────────────
@app.get("/payment-success")
def payment_success():
    session_id = request.args.get("session_id")
    if not session_id:
        return "Missing session_id", 400
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        print(f"[stripe] retrieve failed: {e}", flush=True)
        return "Could not verify payment", 500

    if session.payment_status != "paid":
        return f"Payment not complete yet (status: {session.payment_status})", 402

    # Stripe's metadata is a StripeObject — neither dict() nor .get() work directly.
    # Bracket access does; wrap in try/except for safety.
    try:
        card_token = session.metadata["card_token"]
    except (KeyError, TypeError, AttributeError):
        card_token = None
    if not card_token:
        return "Missing card_token in session metadata", 500

    cards.fulfill(card_token=card_token, agentphone_agent_id=AGENTPHONE_AGENT_ID)
    return (
        "<!doctype html><meta charset=utf-8>"
        "<title>Card sent</title>"
        "<style>body{font-family:-apple-system,system-ui,sans-serif;display:flex;"
        "align-items:center;justify-content:center;height:100vh;margin:0;"
        "background:#f5f0eb;color:#2a2a2a;}"
        ".box{max-width:420px;text-align:center;padding:40px;background:white;"
        "border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.06);}"
        "h1{font-weight:600;margin-bottom:12px;}p{color:#666;line-height:1.5;}</style>"
        "<div class=box><h1>Thanks!</h1>"
        "<p>Your card is on its way to the recipient.</p></div>"
    )


@app.get("/payment-cancelled")
def payment_cancelled():
    return (
        "<!doctype html><meta charset=utf-8>"
        "<title>Cancelled</title>"
        "<style>body{font-family:-apple-system,system-ui,sans-serif;display:flex;"
        "align-items:center;justify-content:center;height:100vh;margin:0;"
        "background:#f5f0eb;color:#2a2a2a;}</style>"
        "<div><h1>No problem — payment cancelled.</h1></div>"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
