# YC-Concierge

> An agentic concierge that listens, finds, pays, and ships.
> Built for the **Call My Agent Hackathon** at Y Combinator, May 2026.

## Team

- **Reza Jamei** ([poly-graph.ai](https://poly-graph.ai)) — shared shell, multi-channel intake, parser, lookup, payment integration
- **Maria Reiling** — birthday-card vertical: design library, card concept, recipient-facing card view
- **Lara Hoyem** — birthday-card vertical: design library, card concept, recipient-facing card view

The birthday-card vertical exists because Maria and Lara brought a beautiful card-design library to the project. The shared agentic shell is what wraps it into a phone-callable / textable / emailable service.

## The pitch (60 seconds)

You call a phone number. You ask for a chore. The agent quotes you a price, you pay,
and it's done — all from one phone call, text, or email. The agent has its own phone
number, its own email inbox, and an autonomous backend that finds people on the live
web when you don't have their contact details.

Today YC-Concierge ships **birthday cards**. Tomorrow it ships anything that fits the
same `request → quote → pay → execute → deliver` shell.

## What's actually in the demo

A buyer initiates a request through any of three channels:

| Channel | Provider | What it does |
|---------|----------|--------------|
| Voice call | AgentPhone | Caller talks to the agent in natural language |
| SMS / iMessage | AgentPhone | Same agent answers text messages |
| Email | AgentMail | Same agent answers email |

The agent parses the request via **Claude on AWS Bedrock**. If the buyer doesn't know
the recipient's email or phone, the agent kicks off a **Browser Use Cloud** task that
searches LinkedIn / company websites / general web for the contact. The system is
robust to STT errors — "Reza Giammi" → "Reza Jamei" recovers automatically.

Pricing is a flat $1 per card via **Stripe Checkout** in test mode. On payment success,
the system selects one of five hand-designed birthday card templates, has Claude write
a personalized message in the buyer's requested tone, stores it, and notifies the
recipient with a shareable link to view the card in their browser.

## Architecture

```
                       ┌──────────────────────────────┐
  buyer ─── call ────► │                              │
  buyer ─── iMessage ► │   shared shell (Flask)       │ ◄─── Stripe webhook
  buyer ─── email ───► │   • intake (whitelisted)     │
                       │   • triage  (Claude/Bedrock) │
                       │   • lookup  (Browser Use)    │
                       │   • quote   ($1 flat)        │
                       │   • payment (Stripe)         │
                       │   • dispatch to verticals    │
                       └──────────────┬───────────────┘
                                      │
                            ┌─────────┴─────────┐
                            │ verticals/cards/  │
                            │ • 5 HTML designs  │
                            │ • Claude copy gen │
                            │ • shareable link  │
                            └───────────────────┘
                                      │
                  ┌───────────────────┴────────────────────┐
                  │                                        │
                  ▼                                        ▼
            recipient gets                       recipient opens link →
            iMessage / email                     rendered birthday card
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the "one agentic shell, many verticals"
extension pattern.

## Sponsors used

- **AgentPhone** — voice + SMS + iMessage intake, hosted-mode voice agent, webhook delivery
- **AgentMail** — agent-owned email inbox (`friendly-concierge@agentmail.to`), webhook delivery, threaded replies
- **Browser Use Cloud** — autonomous web lookup for recipient contacts (sponsor-aligned: this gave us the magic moment)
- **Stripe** — Checkout session for buyer payment (test mode for the demo)
- **AWS Bedrock** — Claude Sonnet 4.5 for triage + Claude for copy generation
- **Gemini** — backup model, used for audio transcription during video build

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Fill .env with your provider keys — see .env.example for the schema
cp .env.example .env
$EDITOR .env

python app.py
```

The Flask server runs on port 5050. For a real test, you'll need to expose it
publicly with a tunneling tool (we used **cloudflared** during development) and
register the public URL as the webhook for both AgentPhone and AgentMail.

## Repo layout

```
app.py                    # shared shell (Flask) — routes inbound, dispatches verticals
messaging.py              # outbound SMS / iMessage / email helpers
verticals/
  README.md               # the vertical extension pattern
  cards/
    __init__.py           # parse → quote → lookup → fulfill — the cards vertical
    designs/              # 5 hand-designed HTML birthday cards by Maria Reiling and Lara Hoyem
    templates/
      cards/
        card_view.html    # recipient-facing card page (Jinja2 over a design partial)
video/
  build.py                # ffmpeg pipeline that built the demo video
  out/yc_concierge_demo.mp4   # the submission demo
ARCHITECTURE.md           # extended design notes
.env.example              # schema for required credentials
requirements.txt
```

## Demo video

The submission video lives in [`video/out/yc_concierge_demo.mp4`](video/out/yc_concierge_demo.mp4)
(~2:51, 1080p). It walks through a voice call, the STT-recovery moment, payment,
and the final rendered card — narrated by the founder.

## Built in one Saturday

Total elapsed time from `git init` to working demo: approximately 8 hours,
including all credentialing across the six sponsor providers and the cards
vertical implementation on top of Maria and Lara's design library.
