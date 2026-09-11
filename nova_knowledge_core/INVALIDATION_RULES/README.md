# INVALIDATION RULES — System Overview

**Last updated:** 2026-05-30

---

## Purpose

This layer defines the conditions under which a trade setup is invalidated or downgraded before, during, or after entry. Invalidation is not a judgment call — it is a system check. If a hard condition is met, the trade does not happen. If a soft condition is met, the setup grade drops.

---

## Two Tiers

| Tier | Definition | Action |
|---|---|---|
| **Hard Invalidation** | Condition that fully disqualifies the setup or the session | Do not trade. No exceptions. |
| **Soft Degradation** | Condition that weakens but does not eliminate the setup | Downgrade quality grade. Re-evaluate. |

---

## Files in This Directory

| File | Contents |
|---|---|
| `pros_invalidation.md` | Hard and soft invalidation conditions specific to PROS setups |
| `orb_invalidation.md` | Hard and soft invalidation conditions specific to ORB setups |
| `session_and_behavioral.md` | Session-level and behavioral blocks that invalidate the entire trading window |

---

## Source Integrity

All conditions in this directory are derived from:
- Evan Investing transcripts (`TRANSCRIPTS_RAW/pros_*`)
- RP transcripts (`TRANSCRIPTS_RAW/orb_rp_*`)
- `nova_strategy_core.json`
- User-defined rules (explicitly stated by Pedro)

Conditions derived from general trading logic not present in the above sources are labeled **[INFERRED]**.
