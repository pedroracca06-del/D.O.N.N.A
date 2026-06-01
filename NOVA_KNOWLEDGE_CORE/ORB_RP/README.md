# ORB / RP Knowledge Base

Strategy knowledge extracted from RP source material.
Do not modify without a source transcript to back the change.

---

## Files

| File | Contents |
|---|---|
| `orb_break_retest.md` | Why 8-8:15 matters, range construction, volume filter, clean break definition, retest confirmation, stop/target parameters, invalidation |
| `reaction_setups.md` | Three setups — bounce, rejection, break and retest — rejection candle definition, LTF hierarchy, trend filter, level failure rule |
| `liquidity_levels.md` | Session highs/lows, PDH/PDL, untested vs tested levels, age of level = strength, multiple test persistence |
| `candle_closure_rules.md` | Candle closure vs. wick touch definition, how closure is applied per setup, multi-TF hierarchy |
| `level_strength.md` | Signs of strong vs. weak levels, age/desperation principle, multi-TF confluence, volume confirmation |

---

## Sources Ingested

| File | Topics |
|---|---|
| `orb_rp_001.txt` | Liquidity framework, session levels, 8-8:15 opening range, break and retest, bounces, rejections, untested levels, LTF confirmation, trend identification |
| `orb_rp_002.txt` | Why 8-8:15 matters (3 reasons), trapped trader psychology, level age = strength, volume filter, candle closure definition, clean break threshold, full entry confirmation detail, level failure/deletion rule, weekly levels as extra-strong |
| `orb_rp_003.txt` | Midpoint as invalidation vs confirmation zone, black dotted midline setting, if-price-in-middle-wait rule, 1:4 preferred R:R, ORB zone as TP when not used as entry, fallback to session highs/lows when ORB never retests, win rate ~62%, ES primary / NQ + Gold secondary |

---

## ORB Phase Structure — RESOLVED

| Phase | Window | Action |
|---|---|---|
| Range Construction | 08:00–08:15 ET | Lock ORB high, low, midpoint. No execution. |
| Execution Phase | 09:30 ET onward | Auction interpretation + entries valid. |
| Cutoff | 11:00 ET | No new ORB entries. Edge degraded. |

---

## Trading Hours (from RP source)

RP states multiple time references across the two transcripts:

| Reference | Value | Context |
|---|---|---|
| Primary trading window | 9:30–11:30 ET | Stated explicitly in Part 2 |
| When chop begins | "After 10:30" | Quoted: "after 10:30, the market often becomes choppy" |
| Typical session end | "Done trading at 10:30" | Stated in a trade example |

**NOVA cutoff is 11:00 ET** (set by user). This is within RP's stated range and consistent with his "after 10:30 it gets choppy" observation. No conflict.

---

## Gaps — Requires Additional Sources

| Concept | Status |
|---|---|
| E2 — external liquidity sweep rejection (NOVA framework) | Not explicitly covered in Parts 1 or 2 |
| Failed acceptance / ORB reclaim logic | Not covered |
| ORB range width thresholds (too wide / too narrow) | Not covered — NOVA has >15pts MES as a flag |

---

## Conventions

- **DISCRETIONARY** labels mark concepts that are judgment-based in the source material
- **⚠️** marks items requiring user decision before NOVA can apply the rule
- Nothing is invented — unclear concepts are listed as gaps
