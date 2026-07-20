# Market Map V1 — Specification

Date: 2026-07-19
Status: **Specification only. No Pine code exists yet.** This document defines what Market Map V1 must do before a single line of Pine is written. It follows the controlled retirement of the legacy NOVA EXECUTION V1 indicator (`indicators/nova_execution_v1.pine`, archived, not deleted) and the UI retirement documented in `TRADING_SUBSYSTEM_UI_RETIREMENT.md`. This is the first artifact of the clean rebuild track — nothing here authorizes implementation. Pedro must explicitly approve this specification, and separately approve a Phase 0 visual mock, before any Pine file is created or edited.

**Revision history:**
- **2026-07-19, draft 1** (commit `8c88781`): initial specification.
- **2026-07-19, draft 2** (commit `df13725`): seven corrections — PDH/PDL as exchange daily candle, 3-session retention, hourly-as-lines, category label toggles, 1m–15m timeframe range, 16:00 ET line-lifetime rule.
- **2026-07-19, draft 3** (commit `40575c2`): Pedro finalized a fuller scope after reviewing a reference image and draft 2 — added the New York session box, redefined Hourly High/Low to the single most-recently-completed candle, locked exact label text, restored per-level/per-box independent visibility toggles, reopened session-time/retention/line-lifetime defaults as proposals, named NQ/MNQ primary validation.
- **2026-07-19, draft 4** (commit `fc632a2`): Pedro approved draft 3 in full, including every item draft 3 had listed as "proposed, awaiting approval" — Asia/London/New York default times, the `input.session()` + `America/New_York` mechanism, the current-session-default 1–3 retention range, the extend-through-NY-close default line-lifetime behavior, the filename/title, and the small-commit sequence. All of those moved from PROPOSED to FINAL. Two new requirements were added: (1) **customizable colors** — every level family and every session box gets a user-configurable color input from TradingView's settings, coordinated by family; (2) **compact level presentation** — thin lines, short labels positioned directly beside/below the line, price candles remaining the visual focus, and the "AS.L"-style abbreviation clarified as a neatness reference only.
- **2026-07-19, draft 5:** two rounds of correction after reviewing the Phase 0 mock. First, Pedro approved the broad color direction (purple Asia, blue London, amber/prominent ORB, muted green New York, neutral PDH/PDL, teal Hourly) and the family-coordination behavior, but required the mock itself be corrected before final Phase 0 sign-off: remove the legend/dashboard entirely (session identity comes from box color + settings, not an on-chart legend); make session-box fills more transparent so candles stay primary; stop using any mock-only label-decluttering — labels must sit at their level's real price, with natural overlap between genuinely close levels accepted as a documented V1 limitation, never faked or hidden; make labels smaller/plainer with no background block; and regenerate the synthetic price path so PDH/PDL sit within a reasonable visible distance of current price (a mock-only data change, not a hint to compress real levels in the eventual indicator). Second, and more significantly, **Pedro issued a final ORB scope correction: ORB becomes box-only**, matching New York's treatment exactly. `ORH`, `ORL`, and `ORM` — their lines, labels, toggles, and dedicated color settings — were removed entirely from every part of this specification. This dropped the key-level count from eleven to eight.
- **2026-07-19, draft 6** (commit `2da1c22`): **Phase 0 is complete — Pedro approved the revised mock and the full visual direction**, with one final default-style adjustment: the amber ORB box is confirmed to render **slightly more visible** than the Asia/London/New York boxes (still transparent, still subordinate to price) — everything else in the approved direction (compact aligned labels, thin lines, no label backgrounds, purple Asia, blue London, muted green New York, neutral dashed PDH/PDL, dim teal Hourly, candles dominant, all colors/transparency user-configurable) is unchanged from draft 5. This revision's edits were a verification pass confirming `ORH`/`ORL`/`ORM` are fully absent from every section, plus updating every remaining "pending Phase 0" hedge now that Phase 0 had actually concluded. **Phase 0 approval does not itself authorize Pine implementation** — Phase 1 still requires Pedro's separate, explicit go-ahead.
- **2026-07-19, draft 7 (this revision):** **Technical correction to the non-repainting HTF pattern for PDH/PDL and Hourly High/Low**, caught before Phase 1. Every prior draft paired the `[1]` offset with `lookahead = barmerge.lookahead_off`; TradingView's officially documented non-repainting higher-timeframe idiom instead pairs the `[1]` offset with `lookahead = barmerge.lookahead_on`. Both requests are corrected to:

    ```
    [previousDayHigh, previousDayLow] = request.security(syminfo.tickerid, "1D", [high[1], low[1]], lookahead = barmerge.lookahead_on)
    [previousHourHigh, previousHourLow] = request.security(syminfo.tickerid, "60", [high[1], low[1]], lookahead = barmerge.lookahead_on)
    ```

  Behavioral requirements are unchanged from every prior draft — PDH/PDL and 1H H/1H L still always represent the previous *completed* candle at their resolution, still behave identically on historical and realtime bars, and no future data leaks into historical bars. The `[1]` offset must never be removed, and `lookahead_on` must never be used without it — removing the offset while keeping `lookahead_on` would leak the developing current HTF candle. **This draft supersedes drafts 1–6 wherever they conflict.** Commits `8c88781`, `df13725`, `40575c2`, `fc632a2`, and `2da1c22` remain in git history unamended — superseded, not erased.

---

## 0. Requirements status key

Every requirement below is tagged so approval status is unambiguous:

- **FINAL** — Pedro has explicitly locked this; it does not need re-approval.
- **PROPOSED** — a default this document recommends; requires Pedro's explicit approval before Phase 0/implementation.
- **DEFERRED** — intentionally out of scope for V1, documented so it isn't silently dropped or silently built.
- **LIMITATION** — a constraint imposed by Pine or by chart timeframe, not a design choice.

---

## 1. Purpose and non-purpose

**FINAL.** Market Map V1 is a *visual reference layer* for NQ/MNQ (primary) that draws session boxes and key liquidity levels so Pedro can instantly see where price has been, where the current session's range sits, and where current price sits relative to those areas — "make the chart easier to read," never "tell me to buy or sell."

**Non-purpose — Market Map V1 contains none of the following, ever, in V1 or any future version without a separate, explicitly-approved specification:**

BUY/SELL signals, entries, exits, trade setups, scoring, grades, confidence scores, alerts (`alertcondition()` or any TradingView alert wiring), execution logic, broker logic, bot integration, AI logic, ICT logic, IB logic, PROS logic, Fibonacci logic, FVG logic, Order Block logic, MACD logic, canonical-signal logic, reaction automation, NOVA backend/bridge/webhook dependency, Harvey or Market Reality dependency.

It runs as a completely standalone `//@version=6 indicator(...)` script with zero dependency on any NOVA file, endpoint, or the retired trading subsystem — a user could delete NOVA entirely and still find it useful on any TradingView chart.

**Reference image note (FINAL):** Pedro shared reference images for style direction. They govern **visual neatness only** — general layout impression, cleanliness, and how minimal/professional a good market-map indicator looks. They do **not** authorize copying branding, watermarks, exact colors, unrelated content, or any strategy/signal element that might appear in them. The color/style direction was decided and approved at Phase 0 (§8) — see the mock at `nova_knowledge_core/mockups/`.

---

## 2. Pine file name

**FINAL (approved 2026-07-19):** `indicators/nova_market_map_v1.pine`, matching the existing convention (`indicators/nova_execution_v1.pine`). Declared indicator title inside the file: `"NOVA Market Map V1"` (overlay indicator, not a strategy — `indicator(...)`, never `strategy(...)`).

This file does not exist yet. This specification is approved and the Phase 0 visual mock is approved (§13) — both gates are now cleared. The file will not be created until Pedro gives a separate, explicit go-ahead to begin Phase 1 implementation.

---

## 3. Key levels

| Level | Label (FINAL, exact text) | Optional toggle |
|---|---|---|
| Previous Day High | `PDH` | Show/hide PDH |
| Previous Day Low | `PDL` | Show/hide PDL |
| Asia High | `ASH` | Show/hide Asia High |
| Asia Low | `ASL` | Show/hide Asia Low |
| London High | `LH` | Show/hide London High |
| London Low | `LL` | Show/hide London Low |
| Hourly High | `1H H` | Show/hide Hourly High |
| Hourly Low | `1H L` | Show/hide Hourly Low |

No other level exists in V1 — **eight key levels total.** In particular:

- **There is no separate New York High/Low level** — New York is a session **box** only (§4); Pedro's key-level list does not include NY High/Low, and none is added here.
- **ORB is box-only, corrected this revision.** Earlier drafts included `ORH`/`ORL`/`ORM` as separate lines and labels. Pedro's final ORB scope correction removes all three: no ORB High line, no ORB Low line, no ORB Midpoint, and no toggles or color settings for any of them. The completed ORB range remains visible **through the fixed session box itself** — its top and bottom edges visually represent the range, exactly like New York's box-only treatment. See §4, §7, §8, §9 for the full correction.

**Compact level presentation (FINAL, added this revision):** a second reference image Pedro shared clarifies the desired label style, used for visual neatness only — never for branding, watermark, promotional content, or unrelated chart elements. Each level is presented as a thin, clean horizontal line with a short label positioned **directly beside or just below the line** — never far away from it. Specifically:

- No large label background block.
- No large text block or verbose description.
- No label positioned far from its level.
- No repeated labels along the same line (one label per level instance, not one per bar).
- Price candles remain the visual focus at all times — levels are reference lines, not the foreground.

**Label text clarification:** the reference image's small `"AS.L"`-style abbreviation is a **style reference only**, illustrating compactness. It does not change the locked label text from §3's table above — the actual label stays exactly `ASL` (and likewise every other label stays exactly as specified: `PDH`, `PDL`, `ASH`, `LH`, `LL`, `1H H`, `1H L`). Compact does not mean abbreviated further or reformatted — it means small, close to the line, and free of clutter.

---

## 4. Session boxes

**FINAL:** four session boxes — Asia, London, New York, ORB — each lightly shaded, visually subtle, each with its own independent show/hide toggle. Boxes must not dominate the chart.

**FINAL — ORB is box-only (corrected this revision).** ORB gets exactly one session box, 08:30–09:30 AM Eastern, with a light transparent fill, a thin configurable border, a configurable box color, and its own show/hide toggle — the same treatment New York already had. There is no separate ORB High line, ORB Low line, or ORB Midpoint; the completed range is represented entirely by the box's top and bottom edges. Historical retention follows the same approved session-box setting as every other family (§10). This removes ORB's previous line/label/midpoint treatment from every part of this document — see §3, §7, §8, §9 for the rest of the correction.

**FINAL — ORB window:** 08:30–09:30 AM Eastern, fixed as the default. This is explicitly restated as final per Pedro's direct instruction, not merely proposed.

**FINAL — Asia, London, New York windows (approved 2026-07-19).** Draft 3 presented these as a proposal rather than silently carrying old NOVA session definitions into this new, independent indicator; Pedro has now explicitly reviewed and approved all three as final defaults:

| Session | Default window (ET) | Basis |
|---|---|---|
| Asia | 19:00 – 03:00 | Matches `core/config.py::session_label()`'s existing `ASIA` window. |
| London | 03:00 – 09:30 | Matches `core/config.py::session_label()`'s existing `LONDON` window. |
| New York | 09:30 – 16:00 | Matches `core/config.py::session_label()`'s `NEW_YORK_CASH` window (regular futures/equity trading hours). |
| ORB | 08:30 – 09:30 | Fixed, see above. |

All four windows remain **user-configurable inputs** (§9) — the table above is the approved shipped default, not a hardcoded constant. Pedro can still change any of them later via the indicator's own settings without needing a new specification.

---

## 5. Timezone behavior

**FINAL (approved 2026-07-19):** session windows use Pine's native `input.session()` type (TradingView's built-in session-picker widget, producing a `"HHMM-HHMM"` string) paired with `time(timeframe, session, timezone)`, alongside a single timezone setting defaulting to `"America/New_York"`, applied to every session/level calculation. This is idiomatic, safe Pine — it gives Pedro a real UI picker rather than separate hour/minute number inputs per session, and inherits DST handling automatically from the platform (§11) with zero custom offset math.

Regardless of which input mechanism is used, the timezone is never hardcoded to a fixed UTC offset — always resolved through Pine's timezone-aware time functions against the configured timezone string, which is what makes daylight-saving handling automatic (§11).

---

## 6. Exact definition of Hourly High and Hourly Low

**FINAL, redefined from both prior drafts.** `1H H` / `1H L` represent the **High and Low of the most recently completed hourly candle** — not the live-growing current hour (draft 1's model), and not a multi-instance retention list of several completed hours (draft 2's model). There is exactly one `1H H` value and one `1H L` value visible at any time, and they update once, at the top of each new hour, to reflect the hour that just closed.

**Implementation (corrected 2026-07-19 — official Pine v6 non-repainting HTF pattern):**

```
[previousHourHigh, previousHourLow] = request.security(
    syminfo.tickerid,
    "60",
    [high[1], low[1]],
    lookahead = barmerge.lookahead_on
)
```

The `[1]` offset reads the prior, already-completed hourly bar; pairing that offset with `lookahead = barmerge.lookahead_on` is TradingView's documented correct combination for a non-repainting higher-timeframe value — offset-without-lookahead-on is not the officially recommended idiom and is superseded by this pattern everywhere in this specification. This is the same corrected pattern as PDH/PDL (§7), applied at 60-minute resolution instead of daily.

Because this is a single completed value (not an accumulator growing bar-by-bar within the current hour), `1H H`/`1H L` do not "grow live" the way Asia's and London's High/Low levels (and ORB's box top/bottom, internally) do — they are static between hourly updates, then jump to the new completed hour's values at the top of each hour. This is intentional and matches "avoid repainting": the displayed value never changes after it's first shown for that hour.

If Pedro would prefer a different non-repainting definition (e.g., a rolling N-hour window, or the live-current-hour-plus-history model from draft 2), that must be separately documented and approved before implementation — this specification does not silently reintroduce either alternative.

---

## 7. Level calculation method

| Level | Method |
|---|---|
| PDH / PDL | Previous **completed** exchange-defined daily futures candle — see the corrected `request.security` pattern below. This is the prior daily candle as TradingView's own "1D" resolution already defines it for the chart's futures symbol — not a custom ET-midnight-to-midnight aggregation. Values remain stable and unchanged throughout the trading day once read. |
| ASH / ASL, LH / LL | Running max/min of `high`/`low` accumulated only over bars whose (configurable-timezone) timestamp falls inside that level's configured window, using the standard Pine accumulator pattern (reset when the window opens, `math.max`/`math.min` while the window is active). These **live-grow** during their window and lock at window close, and are exposed as their own lines and labels. |
| 1H H / 1H L | Per §6 — single most-recently-completed hourly candle via `request.security`, not an accumulator. |

**PDH/PDL implementation (corrected 2026-07-19 — official Pine v6 non-repainting HTF pattern):**

```
[previousDayHigh, previousDayLow] = request.security(
    syminfo.tickerid,
    "1D",
    [high[1], low[1]],
    lookahead = barmerge.lookahead_on
)
```

This replaces the earlier drafts' `high[1]/low[1]` paired with `lookahead = barmerge.lookahead_off` — that pairing is not TradingView's officially recommended non-repainting idiom. The corrected requirement, unchanged in spirit from every prior draft:

- The `[1]` offset must never be removed — it is what guarantees a fully completed daily candle is read, never the still-forming one.
- `lookahead = barmerge.lookahead_on` must never be used *without* that `[1]` offset — doing so would leak the developing current daily candle's values into historical bars, which is exactly the repainting behavior this pattern exists to prevent.
- PDH/PDL always represent the previous completed daily candle, behave identically on historical and realtime bars, and never shift once shown for the day.

**ORB (box-only, corrected this revision):** ORB's box top/bottom uses the identical running max/min accumulator pattern as Asia/London — it still needs a live high/low internally to size the box correctly — but that high/low is **never exposed as a separate line, label, or midpoint value**. No `ORH`, `ORL`, or `ORM` exist anywhere in V1. The box itself, drawn from the accumulated high/low, is the only visible representation of the completed ORB range.

---

## 8. Box creation method, and customizable colors

**PROPOSED implementation:** each of the four session boxes (Asia, London, New York, ORB) uses one persistent `box.new(...)` object per box type, updated in place via `box.set_top` / `box.set_bottom` / `box.set_right` while its window is live, rather than deleted-and-recreated every bar (avoids unnecessary object churn and flicker). Box fill is light and transparent by default; border is thin and subtle, with border visibility and thickness independently configurable (§9). Boxes are never filled solid and never visually dominate price action.

### Customizable colors (FINAL requirement, added this revision)

Every major level family and every session box must have a user-configurable color, changeable from TradingView's indicator settings without editing Pine code. Colors are **coordinated by family**, not assigned one-by-one to every individual line — this is a deliberate simplification Pedro requested after reviewing draft 3's per-level color list:

| Family | Single color input controls | Rationale |
|---|---|---|
| **Asia** | Asia box + `ASH` line + `ASL` line + `ASH` label + `ASL` label | Asia High and Asia Low belong to one session's visual family — no separate ASH-vs-ASL color. |
| **London** | London box + `LH` line + `LL` line + `LH` label + `LL` label | Same reasoning — no separate LH-vs-LL color. |
| **ORB** | ORB box fill hue + ORB box border **only** | **Corrected this revision:** ORB is now box-only, matching New York's pattern — there are no `ORH`/`ORL`/`ORM` lines or labels left to coordinate. |
| **New York** | New York box only | Box-only family — no NY High/Low level exists (§3), so there's nothing else to coordinate. |
| **PDH** | `PDH` line + label | Independent — no box to coordinate with. |
| **PDL** | `PDL` line + label | Independent — no box to coordinate with. |
| **Hourly High** | `1H H` line + label | Independent — no box to coordinate with. |
| **Hourly Low** | `1H L` line + label | Independent — no box to coordinate with. |

This yields **8 color inputs total** (Asia, London, ORB, New York, PDH, PDL, Hourly High, Hourly Low) — unchanged in count from before the ORB correction, since ORB still gets one color input, it now simply controls a box only (like New York) rather than a box plus three lines and labels. Simpler settings menu, same practical control, and it guarantees a session's box and its levels (where any exist) always visually match without Pedro having to manually keep them in sync.

**If Pedro changes a family color** (e.g., Asia) in TradingView's settings, every associated element (box, both lines, both labels) updates automatically to match — this is a single shared color variable feeding every draw call for that family, not four independently-set colors that happen to start equal.

**Labels normally inherit their level's color** (FINAL, confirmed at Phase 0): a label is drawn in the same color as its line by default — the Phase 0 mock rendered labels this way and Pedro approved it, with no request to switch to a neutral single-color scheme.

**Transparency is independently configurable**, separate from color/hue (FINAL): each box has its own transparency input, so selecting a bold color for a family doesn't force the box to overpower the chart — the color controls hue, transparency controls how lightly shaded the box appears. Line color has no separate transparency control (lines are drawn at full opacity, thin and clean, per §12); only boxes need the fill-transparency knob.

**No per-historical-instance colors** (FINAL): retained historical instances of a family (§10) always use that family's one selected color — there is no separate color picker per retained instance. Older instances are simply rendered at lower opacity/faded automatically, exactly as already specified — color choice and "how faded" are two different, non-overlapping controls.

**Default color direction — FINAL, approved 2026-07-19 (Phase 0 complete).** Pedro reviewed the revised mock (`nova_knowledge_core/mockups/`) and approved this direction in full, including one final adjustment locking ORB's relative prominence:

| Family | Color direction | Elements it covers |
|---|---|---|
| Asia | Purple | Box + `ASH`/`ASL` lines and labels |
| London | Blue | Box + `LH`/`LL` lines and labels |
| New York | Muted green | Box only |
| ORB | Orange/amber, **approved to render slightly more visible than the other three boxes** — still transparent, still subordinate to price | Box only — no lines or labels of any kind |
| PDH | Neutral gray/white, dashed | Line + label, no box |
| PDL | Neutral gray/white, dashed (a shade distinguishable from PDH — precise implementation detail, not separately gated) | Line + label, no box |
| Hourly High | Dim teal, dotted, thin — visually subordinate to every other level | Line + label, no box |
| Hourly Low | Dim teal, dotted, thin (a shade distinguishable from Hourly High — precise implementation detail, not separately gated) | Line + label, no box |

Historical retained instances (§10), if any beyond the current one, render in a dimmer/lower-opacity variant of their family's selected color, consistent with the general "recede with age" visual hierarchy from draft 2 — unchanged by the customizable-color addition.

---

## 9. Settings structure

**FINAL.** Every item Pedro listed is included; grouped using the existing project's `group=` input convention (as used in `nova_execution_v1.pine`):

**Group: Level Visibility** (one independent toggle each, FINAL requirement)
Show/hide PDH · PDL · Asia High · Asia Low · London High · London Low · Hourly High · Hourly Low. **No ORB High, ORB Low, or ORB Midpoint toggles exist (corrected this revision)** — ORB has no separate levels to toggle; its box visibility is controlled entirely by the Session Boxes group below.

**Group: Session Boxes** (one independent toggle each, FINAL requirement)
Show/hide Asia box · London box · New York box · ORB box.

**Group: Labels**
- Show/hide all labels (master switch, labels only — does not hide the underlying lines).
- Individual per-label toggles beyond the per-level toggles above: **DEFERRED** — see §14. The per-level toggles (which already gate line + label together) plus this master label switch (hide all labels while keeping all lines) already give full practical control without doubling the settings-menu size; Pedro's own instruction permits treating this as optional ("if this can be done cleanly") and asks the spec not to overwhelm the settings menu.
- Label size (Small/Normal/Large).
- Label position preference where Pine allows it (right-edge of the line is the default and, practically, closest to Pine's native label-anchoring options).

**Group: Colors** (FINAL, added this revision — see §8 for the full family-coordination model)
- Asia color (box + `ASH`/`ASL` lines and labels)
- London color (box + `LH`/`LL` lines and labels)
- New York color (box fill hue + box border only)
- ORB color (box fill hue + box border only — **corrected this revision**: no lines or labels remain to coordinate)
- PDH color
- PDL color
- Hourly High color
- Hourly Low color

**Group: Lines** (applies to Asia, London, PDH, PDL, Hourly High, Hourly Low — the six families that still have lines; ORB and New York are box-only and have no entries here)
- Line thickness.
- Line style (solid/dashed/dotted per family, §8 defaults).
- Line-lifetime behavior — **FINAL (approved 2026-07-19):** default is "Extend through end of NY trading day" (matching draft 2's original 16:00 ET behavior); "Stop at session end" (line freezes at the right edge of its own box, does not extend further) is available as the alternate configurable mode. Both are simple, purely time-based visual behaviors.
- "Continuation until touched" — **DEFERRED**, see §14.

**Group: Boxes**
Box transparency (independently configurable from color, §8), border visibility, border thickness, historical box limit (§10) — applies to all four boxes, including ORB. Box *color* now lives in the Colors group above, shared with that family's lines/labels where any exist rather than set separately per box.

**Group: Session Times** (FINAL — approved 2026-07-19)
Timezone (default `America/New_York`), Asia session time (default 19:00–03:00 ET), London session time (default 03:00–09:30 ET), New York session time (default 09:30–16:00 ET) — all via `input.session()` per §5 — plus ORB time (input exists for configurability, but defaults fixed to 08:30–09:30 ET per the FINAL requirement, §4).

No input in any group controls trading behavior, alerts, or strategy — every input is purely visual/display scope, consistent with §1.

---

## 10. Historical lookback behavior

**FINAL (approved 2026-07-19).** Draft 2 had locked a default of "3 completed sessions per type, 1–5 configurable"; draft 3 reopened it as a proposal favoring a cleaner default. Pedro has now approved that tighter proposal as final:

**Default: current session only** — i.e., retention depth of **1** (the live-forming instance, plus the most recently completed instance replacing the prior one on rollover, per session type: Asia, London, New York, ORB independently).

**Configurable range: 1–3** via a `sessionsToKeep` input per the "Previous 1–3 sessions" option Pedro listed; older retained instances (when the setting is raised above 1) render faded per §8, using their family's selected color.

**Hourly (`1H H`/`1H L`) has no lookback list at all** — per the redefined §6, it is always exactly one completed hour's value, with no retention concept to configure.

This default must remain useful for TradingView Replay (§11) without accumulating unlimited clutter — bounded by the same 1–3 retention cap during replay as during live/historical viewing.

---

## 11. Non-repainting safeguards

**FINAL requirement.** Two distinct concepts must not be confused, and the spec is explicit about which applies where:

- **Live-growing is expected, not repainting.** Asia's and London's High/Low accumulators (and ORB's internal box-sizing accumulator, §7) are *meant* to update every bar while their window is open — that is the whole point of a live session range. This is not repainting: nothing already-displayed silently changes after the fact; the displayed value (or box edge) is always "the correct running high/low as of the current bar," which is exactly what it claims to be.
- **True repainting — a displayed value silently changing after being shown as final — must never happen**, and is the specific risk for `PDH`/`PDL` and `1H H`/`1H L`, both of which read from an already-completed higher-timeframe candle via `request.security`. Both use the corrected pattern (§6, §7): the `[1]`-offset (prior, completed) bar of their respective resolution **combined with** `lookahead = barmerge.lookahead_on` — TradingView's officially documented non-repainting HTF idiom, not the offset-with-`lookahead_off` pairing earlier drafts incorrectly specified. The offset guarantees no future data leaks into historical bars; `lookahead_on` combined with that offset guarantees the value behaves identically on historical and realtime bars, with the value shown always final for that period and never silently revised.

**Daylight-saving time:** handled automatically because every session boundary is computed via Pine's timezone-aware time functions against the configured timezone string (§5), never a fixed UTC offset — the same code produces correctly-placed boxes/levels on both sides of a DST changeover with zero special-case logic. Included as an explicit case in the validation checklist (§13).

**Replay behavior:** TradingView's Bar Replay feature re-runs historical bars through the same live logic path — since every level's calculation (§7) is a pure function of bar time and price with no `barstate.isrealtime`-only branching, replay produces the same results as live or historical viewing. Explicitly checked in §13.

---

## 12. Mobile-readability plan

**FINAL requirements, adapted from draft 2's corrections (still valid) plus draft 3's per-level toggle requirement plus this revision's compact-presentation clarification (§3):**

- Labels are compact, exact-text (§3), positioned **directly beside or just below** their line — not at an arbitrary distance, and never with a large background block behind them.
- **Compact does not mean illegible.** Labels must stay small and close to the line while remaining readable at normal mobile zoom — the requirement is "small and near," not "as small/faint as possible." If a compact size renders illegibly on a real phone-sized chart during validation (§13), that's a defect to fix, not an acceptable tradeoff.
- Visibility is layered: per-level/per-box toggles (§9, FINAL) give coarse control; the master "show all labels" switch (§9) gives a labels-only override; true per-object label toggles beyond that remain deferred (§14) to avoid a bloated settings menu, per Pedro's own "if this can be done cleanly" framing.
- **No automatic label-collision engine is built in V1** (carried over from draft 2, reaffirmed by draft 3, and explicitly reconfirmed this revision: labels must stay directly aligned with their actual level's real price — never nudged to a different value to avoid a collision). Tightly clustered levels (e.g., `ASL` landing very close to `PDL`) may still visually converge — documented as an accepted V1 limitation, not a bug, and the Phase 0 mock deliberately does not paper over this with mock-only decluttering.
- No labels are created repeatedly on every bar and none repeat along the same line (§3) — every label is a persistent object, created once per level/instance and updated (`label.set_xy`, `label.set_text`, etc.) rather than recreated, which is also what keeps mobile chart performance smooth (§14).
- No dashboard/table overlay (`table.new`) — a dense panel reads badly on mobile and isn't needed for a pure levels map.
- Minimum 1px line width, visible at TradingView mobile's default rendering — no sub-pixel/hairline styles. Price candles remain the visual focus at every zoom level (§3).

---

## 13. Validation checklist

**Phase 0 complete:** Pedro reviewed a static visual mock (colors, line styles, box shading, label placement, per §8's approved direction) — synthetic candlestick data, never a real TradingView screenshot, informed by neatness cues from Pedro's reference images (§1) without copying their exact colors/branding — and approved it. No Pine has been written; that still requires Pedro's separate, explicit go-ahead for Phase 1.

Once implementation begins, validation covers:

1. **Live formation** — Asia, London, New York, and ORB boxes all form and grow correctly on NQ and MNQ, on 1m/5m/15m charts.
2. **Hourly correctness** — `1H H`/`1H L` update exactly once per hour, to the just-completed hour's values, with zero mid-hour changes (non-repainting per §6/§11).
3. **PDH/PDL accuracy** — matches the previous completed daily futures candle exactly; no repaint on historical bars.
4. **Exact labels** — every visible label reads exactly `PDH`, `PDL`, `ASH`, `ASL`, `LH`, `LL`, `1H H`, or `1H L` — no variants, and no `ORH`/`ORL`/`ORM` labels exist anywhere (ORB is box-only, corrected this revision).
5. **Independent toggles** — every level and every box can be hidden/shown independently of every other; the master label switch hides labels without hiding lines; no toggle has a side effect on an unrelated element.
6. **Session-time configurability** — changing the Asia/London/New York/ORB session-time inputs correctly moves the corresponding box (and, for Asia/London, their High/Low levels); the ORB default remains 08:30–09:30 ET until explicitly changed.
7. **Historical lookback default** — confirms the approved default (current session only, §10) renders cleanly with no old-session clutter, and that raising the retention input to 2 or 3 fades older instances correctly and never exceeds the configured cap.
8. **Line-lifetime behavior** — both configurable modes (extend-through-NY-close vs. stop-at-session-end, §9) behave as documented; "continuation until touched" is confirmed absent (deferred, §14).
9. **No stale objects** — toggling any input off/on, and letting retention rollover happen naturally, leaves no orphaned or duplicate objects and triggers no runtime object-limit errors.
10. **DST alignment** — historical data spanning a DST transition weekend shows every level type staying aligned to correct wall-clock times before and after.
11. **Replay accuracy** — TradingView Bar Replay through a full session cycle produces identical results to live/historical viewing.
12. **NQ/MNQ primary validation** — full checklist run on both NQ and MNQ; ES/MES checked only as a bonus, not blocking sign-off (§15).
13. **Mobile readability** — labels legible, lines visible, no dashboard/table overlay, on a real mobile device or TradingView's mobile emulation.
14. **Family color coordination** — changing the Asia color input updates the Asia box, `ASH`, `ASL`, and both their labels together; same for London; ORB and New York (both box-only) each update their single box alone; PDH, PDL, Hourly High, and Hourly Low each change independently without affecting any other element; no color input has an unintended side effect.
15. **Compact presentation and exact label text** — every visible label reads exactly the locked text (§3, checklist item 4) with no "AS.L"-style reformatting anywhere; labels sit directly beside/below their line with no large background block and no repetition along the line; candles remain visually dominant over the levels at typical zoom.

---

## 14. Optional features — explicitly deferred, not silently built or silently dropped

- **Continuation-until-touched line behavior.** Pedro explicitly allowed this to be deferred if it adds excessive complexity. It does: correctly tracking "has price touched this level since it locked" without drifting into reaction-detection/signal territory requires careful scoping that has not been done here. **Recommendation: defer to a future, separately-specified revision.** V1 ships with the two simpler, purely time-based line-lifetime modes from §9 only.
- **Fully independent per-label toggles** beyond the per-level/per-box toggles and the master label switch (§9, §12). Recommendation: defer; revisit only if Pedro finds the two-layer model insufficient in practice.
- **Session retention depth above 3**, or any "current day" / "user-defined lookback" mode beyond the 1–3 range proposed in §10. Recommendation: ship the tighter 1–3 range; revisit if Pedro wants deeper history after using V1.

None of the above is present in the shipped V1 settings menu unless Pedro explicitly asks for it to be un-deferred before Phase 0.

---

## 15. Limitations imposed by Pine or chart timeframe

- **Session-window precision is only accurate on lower timeframes.** An 08:30 ET ORB boundary (or any session boundary) cannot be reliably reconstructed from coarse bars without lower-timeframe aggregation, which V1 does not build. **FINAL, resolved in draft 2 and unchanged since:** full session-box and hourly precision on **1m, 3m, 5m, and 15m** charts; auto-suppressed (drawing nothing, never an approximation) above 15m. PDH/PDL is unaffected (reads a single daily candle regardless of chart timeframe) and works on any intraday timeframe.
- **Pine's per-indicator object limits** (`max_lines_count`, `max_labels_count`, `max_boxes_count`) are hard platform caps. V1's design (persistent, updated-not-recreated objects; bounded 1–3 retention; no per-bar object creation) keeps real usage far below reasonable declared limits, but the exact declared numbers are an implementation detail to finalize during Phase 1, not this specification.
- **NQ/MNQ are the primary validation target (FINAL).** ES/MES compatibility may remain possible since the implementation is symbol-agnostic by construction (no hardcoded ticker/tick-size/contract-multiplier logic), but ES/MES is not part of the V1 acceptance bar and any symbol-specific issue there does not block sign-off.
- **No automatic label-collision avoidance** (§12) — a Pine/complexity limitation accepted by design, not a bug to fix later within V1's scope.

---

## Exact files that will be created

**Only one new file, and only after Pedro's separate, explicit go-ahead for Phase 1** (this specification and the Phase 0 mock are both already approved — that alone does not authorize implementation, see "Development safety boundaries" below):

```
indicators/nova_market_map_v1.pine
```

No other file is created or modified as part of Market Map V1 — not `ui/html.py`, not any `main.py` route, not any file under `services/`, `engines/`, `delivery/`, `core/`, `tests/`, or `data/`. This specification document (`nova_knowledge_core/MARKET_MAP_V1_SPECIFICATION.md`) is the only file this revision touches.

---

## Small commit sequence (FINAL — approved 2026-07-19; implementation still gated on Pedro's separate Phase 1 go-ahead)

Each commit is one small, independently visible layer, per "we are developing one clean visual layer at a time." Pedro has approved this sequence itself; none of these commits happen until Pedro explicitly authorizes starting Phase 1.

| # | Commit | Adds |
|---|---|---|
| 0 | *(not a code commit)* Phase 0 visual mock reviewed and approved | **Done** — see `nova_knowledge_core/mockups/` |
| 1 | `Add Market Map V1 skeleton (PDH/PDL only)` | File creation, input scaffold, object-limit declaration, PDH/PDL only |
| 2 | `Add ORB session box` | ORB box only (no levels, no midpoint — corrected this revision), fixed 08:30–09:30 ET default |
| 3 | `Add Asia session box and levels` | ASH/ASL, Asia box |
| 4 | `Add London session box and levels` | LH/LL, London box |
| 5 | `Add New York session box` | NY box only (no NY H/L level, §3) |
| 6 | `Add Hourly High/Low (most recent completed hour)` | 1H H/1H L per the §6 definition |
| 7 | `Add full settings/toggle surface` | Per-level/per-box toggles, label master switch, line/box style groups, session-time configurability |
| 8 | `Add historical retention and line-lifetime behavior` | §10 default + 1–3 config, §9 line-lifetime modes |
| 9 | `Validation pass` | Full §13 checklist executed on NQ and MNQ; DST and replay checks; Pedro signs off on V1 as complete |

---

## Summary: Phase 0 is complete — nothing remains awaiting visual approval

**Final, no further approval needed (as of this revision, 2026-07-19):**
- ORB window (08:30–09:30 ET default) and Asia/London/New York default windows (§4).
- The eight key levels and their exact label text, plus the compact-presentation rules and the "AS.L" clarification (§3).
- **ORB is box-only** (added this revision) — no `ORH`, `ORL`, or `ORM` line, label, midpoint, toggle, or color setting exists anywhere in V1; the box's top/bottom edges are the only visible representation of the completed range (§3, §4, §7, §8, §9).
- Four session boxes including the New York box (§4).
- Hourly High/Low = single most-recently-completed hourly candle, non-repainting (§6).
- Per-level and per-box independent visibility toggles (§9).
- `input.session()` + `America/New_York`-default timezone as the session-input mechanism (§5).
- Historical retention default — current-session-only (depth 1), configurable 1–3 (§10).
- Line-lifetime default — extend-through-NY-close, with stop-at-session-end available (§9).
- Pine filename (`indicators/nova_market_map_v1.pine`) and indicator title (`"NOVA Market Map V1"`) (§2).
- The small-commit sequence (above).
- **Customizable colors, structurally** (added this revision): every level family and session box has a user-configurable color; Asia and London are single coordinated families (box + lines + labels together); ORB and New York are box-only coordinated families (box color only, corrected this revision for ORB); PDH, PDL, Hourly High, and Hourly Low each get their own independent color; transparency is independently configurable from color; no per-historical-instance colors (§8, §9).
- NQ/MNQ as the primary validation instruments (§15).
- The exclusion list (§1) and all development-safety boundaries (below).
- **Color direction, approved at Phase 0** (§8): purple Asia, blue London, muted green New York (box-only), amber ORB (box-only, approved slightly more visible than the other three boxes), neutral dashed PDH/PDL, dim teal Hourly High/Low; labels color-matched to their line; all boxes transparent and subordinate to candles; no legend or dashboard.

**Nothing remains in the "proposed, awaiting approval" category.** Phase 0 (style mock review) is done. The only things left before Pine exists are (a) Pedro's separate, explicit go-ahead to begin Phase 1, and (b) ordinary implementation-time choices too fine-grained to gate here (e.g., the precise shade distinguishing PDH from PDL within the neutral family) — noted inline in §8 as not separately gated.

**Deferred, not built in V1 unless Pedro un-defers it (§14):**
- Continuation-until-touched line behavior.
- Fully independent per-label toggles beyond the per-level/master-switch model.
- Retention depth beyond 3, or any non-bounded lookback mode.

---

## Development safety boundaries (unchanged, restated)

This is a fresh, standalone visual indicator. It does not reuse or copy logic from the archived ORB signal engine, PROS, ICT, IB, the legacy execution indicator, the canonical BUY/SELL state, the old scoring system, old webhook logic, or old bridge logic — and it is never connected to NOVA execution.

This specification revision touches **only** `nova_knowledge_core/MARKET_MAP_V1_SPECIFICATION.md`. It does not modify, and no future Market Map V1 work will modify without a separate explicit request: Journal, Market/News, NOVA Assistant, broker code, execution code, risk logic, existing historical data, Alerts, the retired trading subsystem, the live TradingView cloud script, the existing archived Pine indicator (`indicators/nova_execution_v1.pine`), the pre-existing Phase 8 `main.py` diff, or the `mcp/tradingview` submodule pointer. No live TradingView automation is used. All work stays local until Pedro manually reviews and approves deployment; nothing is pushed.

Nothing in this document authorizes Pine implementation. This specification is approved and Phase 0 (style mock review) is complete and approved — but that is still not authorization to begin Phase 1. Pine implementation begins only after Pedro gives a separate, explicit go-ahead.
