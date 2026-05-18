# Verticals

Each vertical implements a single capability the YC-Concierge agent can fulfill. All verticals share the same `intake → triage → quote → pay → execute → deliver` shell at the project root; the vertical only provides the parts specific to its capability.

## Vertical interface (high-level)

Each vertical's folder is expected to provide:

- **`assess(request)`** — Given an incoming request, can this vertical handle it? What is it asking for, at what scope? What clarifying questions does the requester need to answer?
- **`quote(request)`** — Given an assessed request, what does it cost?
- **`execute(request, paid_context)`** — Run the actual work after payment confirms.
- **`deliver(result, channel)`** — Send the result to the right party (may not be the original requester — for cards, the recipient is the deliverable target, not the buyer).

Exact function signatures, types, and framework choices are decided by the project agent at session start. The shared shell knows nothing vertical-specific and calls into each vertical only through this interface.

Verticals own their own state: databases, asset libraries, model prompts, vendor-specific integrations. The shell does not reach into them.

## Current verticals

- **`cards/`** — Voice/SMS-driven greeting card sending. **In scope for the Saturday 2026-05-17 hackathon.** See [`cards/README.md`](cards/README.md).

## Future verticals (not in scope for the hackathon)

These are documented here as conceptual placeholders to make the extension pattern legible. No folders are pre-created for them.

- **`research/`** — Vendor-list verification, claim auditing, market intelligence. Aligned with subdivision A of [`../../strategy/income-paths-2026-05/09-autonomous-service-agents-path.md`](../../strategy/income-paths-2026-05/09-autonomous-service-agents-path.md).
- **`purchase/`** — Anonymous purchase-on-behalf agent. Aligned with the same lane document.
- **`refund/`** — Dispute and recovery agent (subdivision C in the lane document).
- Other archetypes from the same lane document can drop in as additional verticals later.
