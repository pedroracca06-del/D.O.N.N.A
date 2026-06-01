# NOVA UI Vision
**Status:** Load-bearing | **Version:** 1.0 | **Last updated:** 2026-05-30

This folder is the permanent visual source-of-truth for NOVA.

All future UI/UX development must align to the approved design direction,
mockups, and architecture decisions documented here.

---

## Approved Design Direction

- Intelligence-first
- Institutional and premium
- Operational and glanceable
- Macro-aware at all times
- AI-centered (NOVA AI is the platform identity)
- Mobile-first readable
- Bloomberg-inspired information density
- Low clutter — hierarchy over decoration

---

## Documents

| File | Purpose |
|---|---|
| `README.md` | This file — orientation and rules |
| `DESIGN_PHILOSOPHY.md` | Visual identity, color, typography, component principles |
| `NAVIGATION_ARCHITECTURE.md` | Screen structure, tab hierarchy, state-to-UI mapping |
| `mockups/` | Approved reference mockups (PNG) |

---

## Approved Mockups

| File | Description |
|---|---|
| `mockups/nova_dark_mode_dashboard.png` | Primary desktop dashboard — dark mode |
| `mockups/nova_light_mode_dashboard.png` | Desktop dashboard — light mode variant |
| `mockups/nova_mobile_dashboard.png` | Mobile home / live session view |
| `mockups/nova_mobile_ai.png` | Mobile NOVA AI screen |
| `mockups/nova_mobile_journal.png` | Mobile trade journal |
| `mockups/nova_mobile_bot.png` | Mobile trading bot connection tab |

---

## UI Rules (Non-Negotiable)

1. **NOVA AI is a primary navigation tab** — not a panel, not a widget, not a sidebar feature
2. **Desktop is the flagship experience** — deepest intelligence workflows, AI depth, journaling, macro monitoring, execution management. Mobile is the operational companion. Both are equally core — neither is subordinate.
3. **Macro & News Intelligence is a primary pillar** — always visible, never buried
4. **Journal is a core intelligence system** — not a log, not an afterthought
5. **Trading Bot is execution management** — not the platform identity
6. **Governance is contextual** — surfaces when relevant, never visually dominant
7. **No terminal-style engineering density** — operational, not developer-facing
8. **Maximum 5–6 surfaces on the main dashboard** — hierarchy over information maximalism, no equal-weight panel overload
9. **UI consumes intelligence — it does not invent logic** — every panel maps to an existing compute_Xstate() object
10. **No generic fintech/SaaS drift** — no Social tabs, no retail portfolio hero metrics, no marketing copy inside operational screens
11. **Operational clarity first** — every element earns its place by aiding a decision in the next 60 seconds
12. **Future redesigns evolve this vision** — they do not drift from it without a deliberate decision

## Approved Navigation Structure (Final)

```
Dashboard  |  Macro  |  AI  |  Journal  |  Bot
```

No additional primary navigation items without explicit architectural justification.
NOVA AI is non-negotiable as a primary tab.

## Tab → State Object Mapping (Confirmed)

| Tab | State Object | Current file |
|---|---|---|
| Dashboard | `compute_session_quality_state()` + `compute_pros_state()` + `compute_orb_state()` | `donna_nova_reasoning.py` |
| Macro | `compute_macro_state()` | `donna_macro_discord.py` |
| AI | `evaluate_with_claude()` + full system context | `donna_nova_reasoning.py` |
| Journal | Journal layer | `donna_journal.json` |
| Bot | `compute_execution_state()` + `donna_health.py` | `donna_state_engine.py` |

## What NOVA Is and Is Not

**NOVA IS:** An intelligence-first operational trading environment.

**NOVA IS NOT:**
- A brokerage dashboard
- A social trading app
- A fintech SaaS template
- A TradingView clone
- A retail portfolio tracker

---

## Critical Architecture Note

**The current system is NOT obsolete.**

The existing infrastructure contains:
- Operational intelligence layer
- Governance architecture
- Macro systems (compute_macro_state)
- Execution systems
- Journaling systems
- AI systems
- Feed systems

Future UI work must **consume and reorganize** existing infrastructure.
It does not rebuild it.

This is a **UI/UX evolution phase** — not a backend reconstruction phase.
All state objects defined in `STATE_MODEL.md` already exist to power these screens.

---

## Relationship to Other Architecture Documents

| Document | Relationship |
|---|---|
| `STATE_MODEL.md` | Defines the data each UI panel consumes |
| `DELIVERY_ARCHITECTURE.md` | Defines how Discord and the app co-exist |
| `PHASE_ROADMAP.md` | Defines when Phase 2I (app) begins |
| `CROSS_FEED_INTEGRATION.md` | Defines the intelligence chain the dashboard visualizes |
