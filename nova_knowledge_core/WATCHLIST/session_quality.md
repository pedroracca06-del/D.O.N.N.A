# Session Quality — Downgrade Conditions

**Last updated:** 2026-05-30

---

## Overview

Session quality is assessed before the trading window opens. It determines the ceiling for setup grades on any given day. A degraded session means even a technically clean setup should be treated with more caution — size down, be more selective, or stand aside.

Session quality is not a binary. It is a composite read that accumulates from multiple conditions.

---

## Automatic Hard Blocks — Session Does Not Open

| Condition | Source |
|---|---|
| Major macro event within 30 minutes of 09:30 ET | `nova_strategy_core.json` |
| Daily loss already at or beyond 2% | User rule |

---

## Session Quality Grades

| Grade | Meaning |
|---|---|
| **A** | All conditions favorable — clean environment, defined levels, aligned context |
| **B** | One degradation condition present — proceed with normal discipline |
| **C** | Two or more degradation conditions — reduced position, higher bar for entry |
| **Standby** | Three or more, or a combination that makes the session hostile — observe only |

---

## Degradation Conditions

Each condition met drops session quality by one tier.

### Structure / Level Quality

| # | Condition | Effect | Source |
|---|---|---|---|
| L1 | **ORB range > 15pts MES** | Grade –1 | `nova_strategy_core.json` |
| L2 | **IB range too tight / choppy to define a clear draw** | Grade –1 | `initial_balance_draw.md` |
| L3 | **Pre-market is choppy — no directional sweep formed** | Grade –1 | `manipulation_leg.md` · `session_logic.md` |
| L4 | **No clean untested levels visible on either side** | Grade –1 | `reaction_setups.md` |

### Market Participation / Execution Environment

| # | Condition | Effect | Source |
|---|---|---|---|
| E1 | **Volume under 1,000 on 1m at 09:30 ET open** | Grade –1 | `orb_break_retest.md` |
| E2 | **Spread > 2pts on MES at open** | Grade –1 | `nova_strategy_core.json` |
| E3 | **Price inside ORB zone at 09:30 with no clear breakout direction** | Grade –1 | `orb_break_retest.md` |

### Macro and News Environment

| # | Condition | Effect | Source |
|---|---|---|---|
| M1 | **High-impact macro event scheduled same day but outside trading window** | Grade –1 | `nova_strategy_core.json` |
| M2 | **VIX elevated (> 20)** | Grade –1 | [INFERRED] |
| M3 | **VIX spiking intraday without clear catalyst** | Grade –1 | [INFERRED] |

### Signal Clarity

| # | Condition | Effect | Source |
|---|---|---|---|
| C1 | **PROS and ORB signals in conflict without resolution** | Grade –1 | `nova_strategy_core.json` |
| C2 | **NQ and ES diverging significantly at the open** | Grade –1 | [INFERRED] |
| C3 | **Pre-market bias does not align with ORB break direction at 09:30** | Grade –1 | [INFERRED — consistent with bias alignment logic] |

---

## Session Quality Summary Template

Fill this in as part of the morning checklist before 09:30:

```
Macro flag:          [Green / Yellow / Red]
ORB width:           [X pts — pass / flag if >15]
IB environment:      [Clean draw expected / Tight / Unclear]
Pre-market structure:[Clear sweep / Choppy]
Volume expectation:  [Normal / Thin day]
VIX:                 [X — Normal / Elevated / Spiking]

Degradation count:   [0 / 1 / 2 / 3+]
Session grade:       [A / B / C / Standby]

Decision:            [Trade with full discipline / Size down / Observe only]
```

---

## What Session Grade Does NOT Mean

- A **Standby** day is not a failed day. No trade taken on a degraded session is a correct execution.
- A **Grade A** session does not guarantee a setup will appear — it only means conditions are favorable if one does.
- Session grade is independent of setup grade. A Grade A session with a weak setup (C/D grade) is still a no-trade.

> "We don't trade because we have to. We trade because we can." — Pedro
