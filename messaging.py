"""Outbound messaging — SMS via AgentPhone, email via AgentMail.

Shared by the root shell (replies to the buyer) and verticals (notifies the
recipient). Centralized here so we have one place to swap providers or add
retries later.
"""

import os
import requests

AGENTPHONE_API_KEY = os.environ["AGENTPHONE_API_KEY"]
AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
AGENTMAIL_INBOX = os.environ["AGENTMAIL_INBOX_ADDRESS"]

AGENTPHONE_BASE = "https://api.agentphone.ai"
AGENTMAIL_BASE = "https://api.agentmail.to"


def send_sms(agent_id: str, to_number: str, body: str, number_id: str | None = None) -> None:
    """Send via AgentPhone. If number_id is given, the message is routed via that line
    (e.g. an iMessage-capable line stays on iMessage). Otherwise it defaults to the
    agent's primary line."""
    payload = {"agent_id": agent_id, "to_number": to_number, "body": body}
    if number_id:
        payload["number_id"] = number_id
    resp = requests.post(
        f"{AGENTPHONE_BASE}/v1/messages",
        headers={"Authorization": f"Bearer {AGENTPHONE_API_KEY}"},
        json=payload,
        timeout=15,
    )
    print(f"[SMS/iMessage] {resp.status_code}: {resp.text[:200]}", flush=True)


def send_email_new(to_addr: str, subject: str, text: str) -> None:
    """Start a new email thread to `to_addr`."""
    resp = requests.post(
        f"{AGENTMAIL_BASE}/v0/inboxes/{AGENTMAIL_INBOX}/messages/send",
        headers={
            "Authorization": f"Bearer {AGENTMAIL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"to": [to_addr], "subject": subject, "text": text},
        timeout=15,
    )
    print(f"[Email new] {resp.status_code}: {resp.text[:200]}", flush=True)


def send_email_reply(message_id: str, text: str) -> None:
    """Reply to an existing message thread. Recipients are inferred from the original message."""
    resp = requests.post(
        f"{AGENTMAIL_BASE}/v0/inboxes/{AGENTMAIL_INBOX}/messages/{message_id}/reply",
        headers={
            "Authorization": f"Bearer {AGENTMAIL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"text": text},
        timeout=15,
    )
    print(f"[Email reply] {resp.status_code}: {resp.text[:200]}", flush=True)
