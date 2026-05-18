"""Cards vertical — birthday-card sending via SMS/email.

Single-shot flow:
  1. Buyer sends one message with all details
  2. Claude parses → structured fields
  3. We create a card record + Stripe Checkout link
  4. Buyer pays via Stripe
  5. Stripe redirects to /payment-success → we mark the card paid + notify the recipient
  6. Recipient gets a link to a rendered card page

Birthday-only until we add designs for other occasions.
"""

import json
import os
import random
import re
import secrets

import requests
import stripe
from flask import Blueprint, abort, render_template, send_from_directory
from pydantic import BaseModel

import messaging

# ─── module config ─────────────────────────────────────────────────────────
DESIGNS = [
    "design-1-balloons",
    "design-2-cupcake",
    "design-3-stacked-bold",
    "design-4-confetti",
    "design-5-sunshine",
]

CARD_PRICE_CENTS = 100  # $1 to keep test-mode demos cheap and obvious
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

# iMessage shared line — we route phone-number recipient deliveries through here
# to bypass the 10DLC restriction on our SMS line. Recipient must be iPhone +
# whitelisted in AgentPhone's Shared Lines settings.
AGENTPHONE_IMESSAGE_NUMBER_ID = os.environ.get("AGENTPHONE_IMESSAGE_NUMBER_ID", "")

# Where the card design HTML files live (designs by Maria Reiling & Lara Hoyem)
_DESIGNS_DIR = os.path.join(os.path.dirname(__file__), "designs")

# Browser Use Cloud — used when the buyer asks us to find a recipient's contact
BROWSER_USE_API_KEY = os.environ.get("BROWSER_USE_API_KEY", "")

# ─── storage ───────────────────────────────────────────────────────────────
# In-memory store keyed by share_token. Server restart wipes state — fine for demo.
CARDS: dict[str, dict] = {}

# ─── Bedrock Claude ────────────────────────────────────────────────────────
BEDROCK_KEY = os.environ["AWS_BEARER_TOKEN_BEDROCK"]
BEDROCK_REGION = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_MODEL = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)


def _claude(system: str, user: str, max_tokens: int = 800) -> str:
    resp = requests.post(
        f"https://bedrock-runtime.{BEDROCK_REGION}.amazonaws.com/model/{BEDROCK_MODEL}/invoke",
        headers={
            "Authorization": f"Bearer {BEDROCK_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "anthropic_version": "bedrock-2023-05-31",
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


# ─── parse buyer's request ─────────────────────────────────────────────────
_TRIAGE_SYSTEM = """You are the parser for YC-Concierge's birthday-card service.
A buyer has sent a single message (or voice transcript) describing the card they want to send.
Extract structured fields and decide whether we have enough to proceed.

WE ONLY SUPPORT BIRTHDAY CARDS RIGHT NOW. If the buyer asks for any other occasion, set valid=false and explain.

CONTACT vs LOOKUP — two paths:
- If the buyer GAVE the recipient's email or phone explicitly → set recipient_contact to it, and lookup_hint to null.
- If the buyer asked us to FIND the email (e.g., "send a card to Sarah Chen at Acme Corp", "look up my friend Alex who works at Stripe", "find their email"), set recipient_contact=null and lookup_hint=a tight one-line description we can hand to a web-search agent. The hint should include name + any disambiguating context (company, role, city, mutual relationship). Example: "Sarah Chen, engineering manager at Acme Corp (San Francisco)".

Required when valid=true:
- recipient_name: who the card is for. Infer from buyer's hints, email local-part, or default to "Friend".
- recipient_channel: "sms" if recipient_contact is a phone number, "email" if it's an email address, or null if we're looking up.
- recipient_contact: phone (E.164) OR email — only if the buyer provided it. Otherwise null.
- lookup_hint: one-line description for the lookup agent, only if recipient_contact is null because we need to find it. Otherwise null.
- card_message: warm personal greeting (50-250 chars). Use the buyer's hints (jokes, references, tone). End with sender signoff if a "from" name was given.
- design_id: one of "design-1-balloons", "design-2-cupcake", "design-3-stacked-bold", "design-4-confetti", "design-5-sunshine" based on vibe.
- buyer_summary: one sentence the buyer will read as confirmation. If looking up, say something like "Birthday card for Sarah Chen — finding her email and sending it."

Invalid cases (set valid=false with a friendly reason):
- Non-birthday occasion
- No name AND no contact AND no lookup_hint — there's nothing to act on
- Anything else that makes the request impossible

Respond with ONLY a single JSON object, no markdown:
{"valid": bool, "reason": string|null, "recipient_name": string|null, "recipient_channel": string|null, "recipient_contact": string|null, "lookup_hint": string|null, "card_message": string|null, "design_id": string|null, "buyer_summary": string|null}"""


def _parse_request(text: str) -> dict:
    raw = _claude(system=_TRIAGE_SYSTEM, user=text, max_tokens=700).strip()
    # Strip code fences if Claude wrapped the JSON
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


# ─── Browser Use: find recipient contact when buyer doesn't have it ────────
class _ContactLookup(BaseModel):
    found: bool
    email: str | None = None
    notes: str | None = None


def _lookup_contact(hint: str, source_channel: str = "text") -> _ContactLookup:
    """Find a recipient's email address via Browser Use Cloud.

    source_channel: where the hint came from. When "voice", we tell the
    Browser Use agent to be tolerant of phonetic spelling errors in names and
    companies (since the hint came from a noisy phone transcript)."""
    if not BROWSER_USE_API_KEY:
        return _ContactLookup(found=False, notes="Lookup not configured (no Browser Use key).")
    try:
        from browser_use_sdk.v3 import BrowserUse
        client = BrowserUse(api_key=BROWSER_USE_API_KEY)

        stt_hint = ""
        if source_channel == "voice":
            stt_hint = (
                "\n\nIMPORTANT: this hint came from a phone-call transcript with imperfect "
                "speech-to-text. Names and company names may be PHONETICALLY WRONG. "
                "If your first searches for the exact name/company return nothing, try "
                "phonetic variants. Examples: 'Rega' may be 'Reza' or 'Raja'; 'Omnicraft' "
                "may be 'Omnigraph' or 'Polygraph'; rhyming or one-vowel-off variants are "
                "fair game. If a variant returns a clearly real person matching the other "
                "details (role, city, mutual context), prefer that over the literal spelling. "
                "Note in the 'notes' field which spelling you ended up using and why."
            )

        task = (
            f"Find a current work email address for this person: {hint}.{stt_hint}\n\n"
            f"Search LinkedIn, the company website, and general web search if needed. "
            f"Return found=false if you cannot confirm an email from a real page. "
            f"Do NOT guess common patterns (firstname.lastname@company.com etc) — only return "
            f"an email that you actually saw written somewhere reputable."
        )
        result = client.run(task, output_schema=_ContactLookup)
        print(
            f"[cards] lookup result: found={result.output.found} email={result.output.email} "
            f"notes={(result.output.notes or '')[:120]!r}",
            flush=True,
        )
        return result.output
    except Exception as e:
        print(f"[cards] lookup failed: {e}", flush=True)
        return _ContactLookup(found=False, notes=f"Lookup error: {e}")


# ─── Stripe checkout ───────────────────────────────────────────────────────
def _create_checkout_session(card_token: str, summary: str) -> str:
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": "Birthday card via YC-Concierge",
                    "description": summary[:200],
                },
                "unit_amount": CARD_PRICE_CENTS,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{PUBLIC_BASE_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{PUBLIC_BASE_URL}/payment-cancelled",
        metadata={"card_token": card_token},
    )
    return session.url


# ─── public API used by the root shell ─────────────────────────────────────
def handle_inbound(text: str, sender_contact: str, sender_channel: str, interstitial_func=None) -> str:
    """Process an inbound buyer message. Returns the reply text to send back.

    If ``interstitial_func`` is provided, it's called with a short status update
    when we're about to do a slow operation (e.g. a Browser Use lookup) so the
    buyer doesn't sit in silence. Pass None for synchronous testing.
    """
    try:
        parsed = _parse_request(text)
    except Exception as e:
        print(f"[cards] parse failed: {e}", flush=True)
        return (
            "Sorry, I had trouble understanding that. Try sending one message like: "
            "'Send a birthday card to Alex at +15551234567, from Reza, "
            "with a joke about her socks.'"
        )

    if not parsed.get("valid"):
        reason = parsed.get("reason") or "I need a few more details."
        return (
            f"{reason}\n\n"
            "Try: 'Send a birthday card to [name] at [phone or email], "
            "from [your name], with [any personal touch].'"
        )

    # If buyer didn't provide a contact but asked us to find one, look it up.
    if not parsed.get("recipient_contact") and parsed.get("lookup_hint"):
        print(f"[cards] lookup needed for: {parsed['lookup_hint']!r}", flush=True)
        if interstitial_func:
            try:
                interstitial_func(
                    f"On it — looking up {parsed.get('recipient_name') or 'them'} "
                    f"now. I'll text the payment link in a minute."
                )
            except Exception as e:
                print(f"[cards] interstitial send failed: {e}", flush=True)
        lookup = _lookup_contact(parsed["lookup_hint"], source_channel=sender_channel)
        if lookup.found and lookup.email:
            parsed["recipient_contact"] = lookup.email
            parsed["recipient_channel"] = "email"
            # Rewrite the summary now that we actually have the email
            parsed["buyer_summary"] = (
                f"Found {parsed.get('recipient_name') or 'them'} at {lookup.email} — "
                f"sending a birthday card there."
            )
            print(f"[cards] lookup succeeded: {lookup.email}", flush=True)
        else:
            note = f" ({lookup.notes})" if lookup.notes else ""
            return (
                f"I couldn't find a confident email for "
                f"{parsed.get('recipient_name') or 'that person'}{note}. "
                "Reply with their email or phone and I'll send the card."
            )

    # Belt-and-suspenders: contact is the only thing we truly can't fabricate.
    if not parsed.get("recipient_contact"):
        return (
            "I need either a phone number, email address, or enough context to find "
            "the recipient (e.g., their name + company). Could you reply with that?"
        )

    # Fill plausible defaults for anything else Claude left null
    if not parsed.get("recipient_name"):
        contact = parsed["recipient_contact"]
        local = contact.split("@")[0] if "@" in contact else "Friend"
        parsed["recipient_name"] = local.split(".")[0].split("+")[0].capitalize() or "Friend"
    if not parsed.get("recipient_channel"):
        parsed["recipient_channel"] = "email" if "@" in parsed["recipient_contact"] else "sms"
    if not parsed.get("card_message"):
        parsed["card_message"] = f"Happy Birthday, {parsed['recipient_name']}! Wishing you a wonderful year ahead."
    if not parsed.get("buyer_summary"):
        parsed["buyer_summary"] = f"Birthday card for {parsed['recipient_name']}, delivered via {parsed['recipient_channel']}."

    token = secrets.token_urlsafe(16)
    design_id = parsed.get("design_id") if parsed.get("design_id") in DESIGNS else random.choice(DESIGNS)
    CARDS[token] = {
        "token": token,
        "recipient_name": parsed["recipient_name"],
        "recipient_channel": parsed["recipient_channel"],
        "recipient_contact": parsed["recipient_contact"],
        "card_message": parsed["card_message"],
        "design_id": design_id,
        "buyer_summary": parsed["buyer_summary"],
        "buyer_contact": sender_contact,
        "buyer_channel": sender_channel,
        "paid": False,
        "delivered": False,
    }

    checkout_url = _create_checkout_session(token, parsed["buyer_summary"])
    CARDS[token]["checkout_url"] = checkout_url
    print(f"[cards] created card {token} for {parsed['recipient_name']} → {checkout_url}", flush=True)

    return f"{parsed['buyer_summary']}\n\nPay $1 to send it: {checkout_url}"


def fulfill(card_token: str, agentphone_agent_id: str) -> None:
    """Mark card paid and notify the recipient with their viewing link."""
    card = CARDS.get(card_token)
    if not card:
        print(f"[cards] fulfill: unknown token {card_token}", flush=True)
        return
    if card["delivered"]:
        print(f"[cards] fulfill: token {card_token} already delivered, skipping", flush=True)
        return

    card["paid"] = True
    card_url = f"{PUBLIC_BASE_URL}/card/{card_token}"
    body = (
        f"{card['recipient_name']}, you've got a birthday card waiting! "
        f"Open it here: {card_url}"
    )

    if card["recipient_channel"] in ("sms", "imessage"):
        # Route through the iMessage shared line — works around 10DLC for SMS and
        # delivers as iMessage when the recipient is on iPhone.
        messaging.send_sms(
            agent_id=agentphone_agent_id,
            to_number=card["recipient_contact"],
            body=body,
            number_id=AGENTPHONE_IMESSAGE_NUMBER_ID or None,
        )
    else:
        messaging.send_email_new(
            to_addr=card["recipient_contact"],
            subject=f"A birthday card for {card['recipient_name']}",
            text=body,
        )

    card["delivered"] = True
    print(f"[cards] delivered token {card_token} via {card['recipient_channel']}", flush=True)


# ─── Blueprint: recipient-facing routes ────────────────────────────────────
bp = Blueprint("cards", __name__, template_folder="templates")


@bp.route("/card/<token>")
def view_card(token):
    card = CARDS.get(token)
    if not card:
        abort(404)
    if not card.get("paid"):
        # For demo, allow viewing even pre-payment so you can preview. In real life
        # this should 402 or redirect to checkout.
        pass
    return render_template("cards/card_view.html", card=card)


@bp.route("/cards/designs/<design_id>")
def serve_design(design_id):
    """Serve the raw design HTML so the card_view iframe can load it."""
    if design_id not in DESIGNS:
        abort(404)
    return send_from_directory(_DESIGNS_DIR, f"{design_id}.html")
