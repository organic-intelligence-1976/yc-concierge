# YC-Concierge — Anonymous Request-Quote-Pay-Deliver Agent

## Project Overview

Hackathon entry for the **Call My Agent Hackathon** at Y Combinator on **May 17, 2026** (T-2 days at project creation).

YC-Concierge is **one product with multiple verticals plugged in**. The core loop is the same regardless of what the user is asking for: anonymous requester texts or emails the service → agent quotes a price → user pays via Stripe → agent does the thing → agent delivers the result. The vertical is what determines what "the thing" is.

For Saturday's hackathon, **only the `cards` vertical is in scope** — voice/SMS-driven greeting-card sending, built on top of birthday-card designs and a card-rendering concept contributed by teammates **Maria Reiling** and **Lara Hoyem**. The architecture is deliberately designed to accept future verticals (`research`, `purchase`, etc.) without changes to the shared shell.

This project supersedes an earlier prototype that had a narrower per-vertical framing. The unified framing came after noticing that a general research-agent and a greeting-card agent are the same machine with different verticals plugged in.

## Read me first

| Doc | Purpose |
|-----|---------|
| `CLAUDE.md` | This file — project context |
| `ARCHITECTURE.md` | High-level system design — shared shell + vertical extension pattern |
| `message_board.md` | Communication channel with the workspace agent |
| `verticals/README.md` | Vertical extension pattern; list of current and planned verticals |
| `verticals/cards/README.md` | Cards vertical — design library + flow |

## Hackathon context

- **Event**: Call My Agent Hackathon, hosted at Y Combinator
- **Date**: May 17, 2026
- **Sponsors (per user)**: AgentMail, Stripe, Moss, Google, AWS, Sponge. Exact list and which services are free for the event to be confirmed at project-session start. (Strategy doc mentioned additional possible providers — AgentPhone, Browser Use, Supermemory, Google DeepMind — worth verifying alongside.)
- **Sponsor-first preference**: Where two providers would do the same job, prefer the sponsor's service. The free-for-the-event credit is the practical reason; brand alignment is the bonus.

## Conventions

- **Project agent** (sessions opened with `cd YC-Concierge && claude`) owns all implementation work.
- **Workspace agent** writes to `message_board.md` for directives or strategic context.
- **Hackathon-scoped**: anything beyond the cards-vertical MVP is post-hackathon. The bar is *demoable Saturday*.
- **Standard libraries only**: verticals use widely-adopted, well-maintained dependencies (Flask, Pydantic, the Stripe SDK, the Anthropic SDK, etc.). No proprietary platform SDKs.

## What is intentionally undecided

The design docs deliberately avoid committing to specific frameworks, models, or providers. Stack decisions — which agent framework (Claude Agent SDK / OpenAI Agents SDK / PydanticAI / raw API), which model, which email/SMS/memory/hosting providers — depend on which sponsor services are free for the event and on the user's preferences. The project agent receives this information from the user when the project session opens and commits the stack decisions then.
