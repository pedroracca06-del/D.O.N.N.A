# WATCHLIST — System Overview

**Last updated:** 2026-05-30

---

## Purpose

The watchlist layer provides the pre-session and session-context intelligence needed before any trade can be evaluated. It is the morning preparation framework that answers:

1. What is the macro environment today?
2. What are the key levels on the primary instruments?
3. What is the directional draw for this session?
4. What is the session quality — are conditions favorable or degraded?

---

## Files in This Directory

| File | Contents |
|---|---|
| `morning_checklist.md` | Step-by-step pre-market preparation flow (08:00–09:30 ET) |
| `instruments.md` | What to assess per instrument — ES, NQ, Gold, Oil, DXY, VIX |
| `session_quality.md` | Conditions that automatically downgrade session quality |

---

## Primary vs Context Instruments

| Role | Instruments |
|---|---|
| **Primary execution** | ES / MES — all entries taken here |
| **Secondary correlation** | NQ / MNQ — alignment context |
| **Macro context** | DXY, Gold, Oil, VIX — regime and risk environment [INFERRED layer] |

The INFERRED label on macro context instruments means their correlation logic is not sourced from transcripts — it is general market knowledge applied to this system. These are contextual reads, not entry signals.

---

## Source Integrity

- Instrument strategy coverage: `TRANSCRIPTS_RAW/orb_rp_*.txt` · `TRANSCRIPTS_RAW/pros_*.txt`
- Session timing: `nova_strategy_core.json`
- Risk environment context: [INFERRED] where not transcript-sourced
