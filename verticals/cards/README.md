# Cards vertical

Voice/SMS/email-driven greeting card sending. **In scope for the 2026-05-17 Call My Agent Hackathon.**

## Credit

The birthday card designs and the recipient-facing card concept were contributed by teammates **Maria Reiling** and **Lara Hoyem**. The shared agentic shell at the project root wraps their work into a phone-callable, textable, and emailable service.

## What this vertical does

1. The shared shell hands us a parsed buyer request (occasion, recipient, vibe, custom message) from any channel (voice, SMS, iMessage, email).
2. If the buyer didn't supply the recipient's contact, we ask Browser Use Cloud to look it up on the live web.
3. We quote a flat $1 per card and generate a Stripe Checkout session.
4. After Stripe confirms payment, Claude (Sonnet 4.5 on Bedrock) picks one of the five hand-designed birthday cards based on vibe + writes a personalized message in the requested tone.
5. The recipient gets a link (via iMessage or email) to a browser page that renders the chosen design plus their personal message.

## Files

```
designs/                       # 5 hand-designed HTML birthday cards (by Maria + Lara)
  design-1-balloons.html
  design-2-cupcake.html
  design-3-stacked-bold.html
  design-4-confetti.html
  design-5-sunshine.html
templates/cards/card_view.html # recipient-facing wrapper (Jinja2 + iframe of design)
__init__.py                    # parse → lookup → quote → fulfill — the vertical's logic
```

Each design is pure HTML + CSS (no JS, no build step), so it can be served as a static asset or embedded via iframe directly. The wrapper template is the only piece that knows about the personalized message — designs themselves are untouched.

## What this vertical does NOT handle

- **Intake** (voice/SMS/email reception, transcript parsing) — handled by the shared shell.
- **Payment processing** — Stripe lives in the shared shell. The vertical never sees card data.
- **Whitelist enforcement** — handled by the shared shell.

## Adding more occasions later

The current 5 designs are birthday-specific. To support other occasions:

1. Add new HTML designs to `designs/`.
2. Extend the design picker prompt in `__init__.py` so Claude knows when to pick them.
3. Loosen the parser's "birthday cards only" rule in the system prompt.

The shell doesn't need to change.
