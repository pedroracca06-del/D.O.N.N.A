# NOVA Design Philosophy
**Status:** Load-bearing | **Version:** 1.0 | **Last updated:** 2026-05-30

The visual and experiential principles that define NOVA as a platform.
Every design decision should be traceable back to one of these principles.

---

## What NOVA Is

NOVA is an **intelligence terminal for independent traders** operating at an
institutional standard. It is not a retail dashboard. It is not a charting tool.
It is not a signal alert app.

NOVA is the operational center from which a trader:
- reads the current market environment
- receives contextual intelligence (PROS, ORB, IB, macro)
- interacts with an AI that understands their system
- reviews and improves their execution quality
- manages their trading bot and risk state

The design must reflect this. Every screen asks: **does this help the trader make
a better decision in the next 60 seconds?**

---

## The Bloomberg Reference

Bloomberg Terminal is the reference point — not because NOVA copies it, but
because Bloomberg solved the same core tension: **how do you display dense,
high-stakes operational information without overwhelming the user?**

Bloomberg's answer: strict hierarchy, consistent typography, color as signal
(not decoration), and information density that rewards attention without
demanding it.

**What NOVA takes from Bloomberg:**
- Color encodes meaning, not aesthetics (red = risk/stop, green = go/confirm, amber = caution)
- Typography is functional — size and weight communicate priority
- Information density is earned — every field visible on screen serves a purpose
- The interface feels serious because the work is serious

**What NOVA does NOT take from Bloomberg:**
- The terminal aesthetic (NOVA is premium, not retro)
- The 1990s grid layout
- Pure text density without visual hierarchy
- The assumption that only professionals can use it

---

## Visual Identity

### Tone
Premium. Institutional. Calm under pressure. Not flashy. Not consumer-grade.

### Mode
Dark mode is primary. It is the default operational environment.
Light mode exists as a variant — it must feel equally premium, not washed out.

### Density
Medium density. Not sparse (this is an operational tool, not a landing page).
Not maximal (this is not a Bloomberg terminal clone).

**The right density:** A trader can read the full session state in under 10 seconds
without scrolling. Everything critical is above the fold. Everything else is one tap away.

---

## Color System

Color encodes operational state. It is never decorative.

| Color | Meaning | Use |
|---|---|---|
| **Green** `#00C851` | Active, forming, bullish signal | HEADS_UP, bullish bias, PASS state |
| **Blue** `#0080FF` | Confirmed, ready, actionable | EXECUTION_READY, confirmed setup |
| **Red** `#FF4444` | Invalidation, risk, stop | INVALIDATION, FAIL state, stop loss |
| **Amber** `#FFBB33` | Caution, degraded, no-trade | NO_TRADE, WARNING state, macro risk |
| **Purple** `#9B59B6` | Intelligence, brief, AI | SESSION_BRIEF, NOVA AI surface |
| **Bright Red** `#FF0000` | Critical emergency | CRITICAL macro events, circuit breakers |

**Background (dark mode):**
- Primary surface: `#0D0F14` — near-black, not pure black
- Secondary surface: `#161920` — card/panel backgrounds
- Border: `#1E2330` — subtle, not harsh
- Text primary: `#E8EAF0` — off-white, easier on eyes than pure white
- Text secondary: `#6B7280` — muted labels, metadata

**Background (light mode):**
- Primary surface: `#F4F6FA`
- Secondary surface: `#FFFFFF`
- Border: `#E2E6EF`
- Text primary: `#0D0F14`
- Text secondary: `#6B7280`

---

## Typography

One typeface family throughout. Clean, geometric, legible at small sizes.
**Recommendation:** Inter (or equivalent — DM Sans, Geist).

| Role | Size | Weight | Use |
|---|---|---|---|
| Screen title | 20–24px | 600 | Page/section headers |
| Panel label | 13–14px | 500 | Card headers, section labels |
| Data value | 16–20px | 600–700 | Prices, scores, key metrics |
| Body text | 14px | 400 | Descriptions, notes, AI output |
| Caption | 12px | 400 | Timestamps, metadata, footnotes |
| NOVA output | 14px | 400 | AI text — readable, not cramped |

**Rule:** Never use more than 3 type sizes on a single screen. Hierarchy comes
from weight and color, not font size proliferation.

---

## Component Philosophy

### Cards
The primary container unit. Each card owns one piece of operational state.
Cards have:
- A clear label (what it shows)
- A status indicator (color dot or badge)
- A primary value (the answer)
- Optional secondary context (one line)

Cards do not contain paragraphs. If a card needs more than 4 lines, it is two cards.

### Panels
Groups of related cards. A panel covers one domain:
- Market panel (VIX, NQ, ES, regime)
- Session panel (quality, IB, ORB status)
- PROS panel (phase, direction, OTE)
- Macro panel (next event, countdown, risk)

Panels do not contain unrelated information.

### NOVA AI Surface
NOVA AI is not a chatbot bubble in the corner. It is a contextual intelligence
layer that surfaces throughout the app. It appears:
- As the primary screen in the AI tab
- As contextual interpretation below state panels
- As the author of NOVA assessment fields in alerts

NOVA AI text follows the tactical language standard:
concise, operational, glanceable. See `ARCHITECTURE_CORE.md` §4.

### Feed
The alert/intelligence feed resembles a curated institutional feed — not a
social media timeline. Items have:
- A clear severity indicator (color + icon)
- A timestamp
- A one-line summary (the signal)
- Expandable detail (optional)

Feed items do not have like buttons, share buttons, or engagement mechanics.

---

## Two Form Factors, One System

NOVA is one operational intelligence system with two optimized form factors.
It is not a mobile-first product with a secondary desktop app.
Both are core operational environments — neither is subordinate.

### Desktop — The Flagship Experience

The approved desktop/web interface is the flagship NOVA experience.

This is where:
- Deepest intelligence workflows live
- Full journaling depth and replay live
- Extended AI interaction and analysis live
- Macro monitoring across multiple time horizons lives
- Multi-surface operational oversight lives
- Execution management depth lives

The desktop should feel like an **institutional AI-powered trading intelligence desk.**
Premium. Operational. Calm under pressure. Intelligence-first. Not fragmented.
Not a developer dashboard. Not a fintech SaaS template.

The approved desktop mockup direction already achieves this. It should remain
the primary visual direction into Phase 2I. The problem in prior iterations
was not desktop itself — it was desktop drifting toward fragmented
engineering-dashboard UX. The approved direction does not have this problem.

### Mobile — The Operational Companion

Mobile is the operational companion layer. Its role is fast interaction,
not deep workflows.

Mobile strengths:
- Fast operational awareness (session state, setup phase, macro risk)
- Alert consumption and acknowledgment
- Lightweight AI access (quick questions, contextual answers)
- Journal updates (quick post-trade notes)
- Governance checks (daily limits, trade count)
- Quick market context (VIX, regime, next event)
- Execution monitoring

### What Mobile Taught Desktop

The mobile layouts naturally enforced the correct hierarchy — not because
mobile is the authority, but because limited screen space forced the right
prioritization. That lesson applies to desktop:

**Desktop should preserve mobile's hierarchy while expanding its depth.**

Mobile defines: clarity and prioritization.
Desktop defines: depth and operational surface area.

The hierarchy does not change between form factors. The depth does.

## Layout Principles

### Desktop
- Sidebar navigation (persistent)
- 5–6 major operational surfaces on main dashboard
- Alert feed as a persistent sidebar column
- AI panel with full interaction depth
- Multi-panel workflows that mobile cannot support

### Mobile
- Bottom tab navigation, 5 tabs
- Every screen fully usable on 375px width
- No horizontal scrolling (data tables excepted)
- Touch targets minimum 44px
- Critical information in top 60% of viewport
- NOVA AI in one tap from any screen
- Card-based vertical scroll as primary content pattern

---

## Shared Hierarchy, Different Depth

Both form factors share the same information hierarchy. Desktop expands each
level with more depth and surface area. Mobile compresses each level to its
essential signal.

```
Hierarchy level:              Mobile:              Desktop:
1. Session state              Header badge         Persistent top bar + full panel
2. Setup status (PROS/ORB)    Summary card         Full phase panel with levels
3. NOVA AI                    Quick insight line   Full interaction panel
4. Market context             One-line summary     Compact metrics bar
5. Macro + events             Next event card      Full event timeline
6. Alert feed                 Below fold           Persistent sidebar column
```

Desktop adds depth to each level — it does not add new categories.

## What NOVA Is NOT (Design Anti-Patterns)

| Anti-pattern | Why it fails |
|---|---|
| Terminal/CLI aesthetic | Alienates non-technical users; NOVA should feel premium not raw |
| Indicator overload | Cluttered charts produce cluttered intelligence and screenshots |
| Notification badges everywhere | Governance is contextual, not alarming |
| Generic fintech dashboard | NOVA has a specific operational purpose — generic UI loses it |
| Social tabs | NOVA is not a social platform at any phase |
| Retail portfolio hero metrics | Account value is not the operational center; session state is |
| Marketing copy inside the app | Feature lists belong on landing pages, not operational screens |
| Generic asset movers | NOVA watches MES/MNQ for specific setups — not a general scanner |
| Dark mode as gimmick | Dark mode is primary because it is operationally superior, not trendy |
| Fragmented panel overload | More panels ≠ more intelligence; hierarchy matters |
| 9+ equal-weight dashboard panels | Forces the user to prioritize — the UI should do that for them |
| Decorative data visualization | Every chart and visualization earns its place through operational value |
| AI as chatbot widget | NOVA AI is a primary tab and intelligence layer — not support chat |
| Desktop as separate hierarchy | Desktop expands mobile's hierarchy — it does not invent a different one |
| Mobile as the "real" product | Both form factors are equally core. Desktop is the flagship experience. |

---

## Screenshot-Ready Standards

Because NOVA captures chart screenshots that are attached to Discord alerts
and (eventually) displayed in the app, the TradingView chart must meet
visual standards:

- One clean layout — no indicator clutter
- Key levels visible (ORB, IB, OTE zones, session highs/lows)
- No overlapping labels
- Consistent color coding matching NOVA's color system
- Clean at Discord embed dimensions (~800×450px)

The chart is part of the NOVA visual system. Its cleanliness reflects
directly on intelligence quality.
