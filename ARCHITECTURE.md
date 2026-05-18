# YC-Concierge — Architecture (high-level, tentative)

## The unified engine

YC-Concierge is one product with N verticals plugged in. The core insight: anonymous **request → quote → pay → deliver** is the same shell regardless of what the agent is being asked to do. The vertical is what determines how the "deliver" step actually executes.

## Shared shell (lives at the project root, built once)

1. **Intake.** Anonymous user sends a request via text (SMS or phone call) or email — no account required. The intake channel is a sponsor service (provider choice TBD at session start — AgentMail / AgentPhone / etc.).
2. **Triage.** Agent parses the request, identifies which vertical it belongs to (cards, research, purchase, …), assesses whether it is in-scope and well-formed, and asks clarifying questions through the original channel if needed.
3. **Quote.** Agent generates a price using the matched vertical's pricing function. Sends the quote back through the original channel.
4. **Payment.** If the user confirms, agent generates a Stripe Checkout link. Stripe handles the payment; we hold no card data. The requester's email is captured at checkout.
5. **Execute.** Vertical-specific code runs.
6. **Deliver.** Result is sent back through the original channel — or, for verticals where the deliverable goes to someone other than the requester (e.g., a greeting card goes to the recipient), through the vertical-specific delivery path.

Every step in the shell is provider-agnostic by design. The intake channel can be email or SMS; the model behind the agent can be Claude, GPT, or Gemini; the memory layer can be in-process, hosted, or stateless. Exact choices wait for the confirmed sponsor list.

## Vertical extension pattern

Each vertical lives under `verticals/<name>/` and exposes a standard interface (function signatures and types decided by the project agent):

- **`assess(request)`** — Can this vertical handle this request? At what scope? What clarifying questions does the requester need to answer before a quote can be generated?
- **`quote(request)`** — Given an assessed request, what does it cost?
- **`execute(request, paid_context)`** — Do the thing.
- **`deliver(result, channel)`** — Send the result to the right party. (May not be the original requester — see the cards vertical.)

The shared shell knows nothing vertical-specific. Adding a new vertical means dropping a new folder under `verticals/` that implements this interface plus any vertical-private state (databases, asset libraries, model prompts, etc.).

## Verticals planned

- **`cards/`** — In scope for the Saturday hackathon. Voice/SMS-driven greeting-card sending. AI picks an on-brand card design from the in-house library (designs by Maria Reiling and Lara Hoyem) and writes the message copy; card is delivered to the recipient via SMS/email link.
- **`research/`** — Future. Vendor-list verification, claim auditing, market intelligence. Aligned with subdivision A of `../strategy/income-paths-2026-05/09-autonomous-service-agents-path.md`.
- **`purchase/`** — Future. Anonymous user requests a purchase be made on their behalf.
- Other archetypes from the same lane document can drop in as additional verticals over time.

For the hackathon, only `verticals/cards/` is being implemented. The other folder names are placeholders in the documentation, not pre-created folders.

## What is intentionally undecided in this document

- **Specific agent framework** (Claude Agent SDK / OpenAI Agents SDK / PydanticAI / raw API)
- **Models to use** for the triage agent, the vertical execute agents, and any sub-agents
- **Email provider** (AgentMail vs SES vs SendGrid vs Resend)
- **SMS/voice provider** (AgentPhone vs Twilio vs Vonage vs Vapi vs Retell)
- **Memory/state store** (Supermemory vs Mongo vs SQLite vs Redis vs in-process)
- **Hosting** (Render vs AWS vs Modal vs Vercel vs Fly)
- **Agent orchestration pattern** (single agent vs orchestrator + sub-agents vs router + per-vertical agents)
- **Payment surface details** (Stripe Checkout link in the reply vs hosted page vs embedded element)

All of the above depend on which sponsor services are free for the event and on user preference. They are decided when the project agent has the confirmed sponsor list and any explicit stack preferences from the user.

## Architectural commitments that are NOT tentative

These hold regardless of stack choices:

1. **Anonymous flow.** No account required to submit a request. Email is captured at Stripe Checkout if needed for receipts.
2. **Sponsor-first.** Where two providers would do the same job, default to the sponsor's service for the cost savings on the event credit.
3. **Vertical isolation.** Vertical code never reaches around into the shared shell's payment or intake plumbing. The shell calls into the vertical through the standard interface and only through it.
4. **Stripe is the payment provider.** No alternatives in scope.
5. **Standard libraries only.** Verticals must use widely adopted, well-maintained dependencies (FastAPI / Flask, Pydantic, Stripe SDK, standard Anthropic / OpenAI SDKs, etc.). No proprietary platform SDKs.
