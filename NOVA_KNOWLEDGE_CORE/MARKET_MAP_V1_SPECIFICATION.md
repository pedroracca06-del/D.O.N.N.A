# Market Map V1 — Specification

Date: 2026-07-19
Status: **Specification only. No Pine code exists yet.** This document defines what Market Map V1 must do before a single line of Pine is written. It follows the controlled retirement of the legacy NOVA EXECUTION V1 indicator (`indicators/nova_execution_v1.pine`, archived, not deleted) and the UI retirement documented in `TRADING_SUBSYSTEM_UI_RETIREMENT.md`. This is the first artifact of the clean rebuild track — nothing here authorizes implementation. Pedro must explicitly approve this specification, and separately approve a Phase 0 visual mock, before any Pine file is created or edited.

**Revision history:**
- **2026-07-19, draft 1** (commit `8c88781`): initial specification.
- **2026-07-19, draft 2** (commit `df13725`): seven corrections — PDH/PDL as exchange daily candle, 3-session retention, hourly-as-lines, category label toggles, 1m–15m timeframe range, 16:00 ET line-lifetime rule.
- **2026-07-19, draft 3 (this revision):** Pedro finalized a fuller scope after reviewing a reference image and draft 2. **This draft supersedes drafts 1 and 2 wherever they conflict.** Commits `8c88781` and `df13725` remain in git history unamended — they are superseded, not erased. Major changes in this draft: a fourth session box (New York) is added; Hourly High/Low is redefined a second time, now to the single most-recently-**completed** hourly candle (not live-growing, not a multi-instance retention list — draft 2's "lines only, current + N completed" model is replaced); Pedro's exact label text is now locked (`PDH`, `PDL`, `ASH`, `ASL`, `LH`, `LL`, `1H H`, `1H L`, `ORH`, `ORL`, `ORM`); every major level and every session box gets its own independent visibility toggle (this supersedes draft 2's "three category toggles only" label-simplification correction — that correction was about *labels specifically*, and still stands for labels, but level/box *visibility* now requires per-object toggles); session times (Asia/London/New York) become user-configurable inputs with proposed-but-not-yet-approved defaults, rather than silently inherited NOVA convention; session history retention depth (draft 2's "3 completed, faded") is reopened as a proposed-not-final default; line-lifetime (draft 2's fixed "always through 16:00 ET") becomes a configurable choice with a proposed default; NQ/MNQ are named the primary validation instruments (ES/MES compatibility may remain possible but is not the validation target); and a reference image Pedro shared governs visual neatness/layout impression only — never exact colors, branding, or any strategy element.

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

**Reference image note (FINAL):** Pedro shared a reference image for style direction. It governs **visual neatness only** — general layout impression, cleanliness, and how minimal/professional a good market-map indicator looks. It does **not** authorize copying its branding, watermarks, exact colors, unrelated content, or any strategy/signal element that might appear in it. Exact colors remain a Phase 0 decision (§8).

---

## 2. Proposed Pine file name

**PROPOSED:** `indicators/nova_market_map_v1.pine`, matching the existing convention (`indicators/nova_execution_v1.pine`). Declared indicator title inside the file: `"NOVA Market Map V1"` (overlay indicator, not a strategy — `indicator(...)`, never `strategy(...)`).

This file does not exist yet and will not be created until Pedro approves this specification and, separately, the Phase 0 visual mock (§13).

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
| ORB High | `ORH` | Show/hide ORB High |
| ORB Low | `ORL` | Show/hide ORB Low |
| ORB Midpoint | `ORM` | Show/hide ORB Midpoint (default off) |

No other level exists in V1. In particular, **there is no separate New York High/Low level** — New York is a session **box** only (§4); Pedro's key-level list does not include NY High/Low, and none is added here.

---

## 4. Session boxes

**FINAL:** four session boxes — Asia, London, New York, ORB — each lightly shaded, visually subtle, each with its own independent show/hide toggle. Boxes must not dominate the chart.

**FINAL — ORB window:** 08:30–09:30 AM Eastern, fixed as the default. This is explicitly restated as final per Pedro's direct instruction, not merely proposed.

**PROPOSED — Asia, London, New York windows.** Per Pedro's explicit instruction not to silently carry old NOVA session definitions into this new, independent indicator, the times below are presented as a starting proposal, most of them (Asia/London) drawn from the existing convention in `core/config.py::session_label()` for consistency with the rest of the product, but requiring Pedro's fresh, explicit approval here rather than being assumed:

| Session | Proposed default window (ET) | Basis for the proposal |
|---|---|---|
| Asia | 19:00 – 03:00 | Matches `core/config.py::session_label()`'s existing `ASIA` window — proposed for consistency, not silently assumed. |
| London | 03:00 – 09:30 | Matches `core/config.py::session_label()`'s existing `LONDON` window — proposed for consistency, not silently assumed. |
| New York | 09:30 – 16:00 | New box, not present in draft 1/2. Matches `core/config.py::session_label()`'s `NEW_YORK_CASH` window (regular futures/equity trading hours) — proposed as the standard, recognizable "NY session" definition. |
| ORB | 08:30 – 09:30 | **FINAL**, see above. |

All four windows are **user-configurable inputs** (§9) — the table above is only the shipped default. Pedro can change any of the three proposed windows at approval time, or leave them as proposed, or change them later via the indicator's own settings without needing a new specification.

---

## 5. Timezone behavior

**PROPOSED implementation approach:** a single `input.string` (or equivalent) timezone setting, default `"America/New_York"`, applied to every session/level calculation. Session windows themselves use Pine's native `input.session()` type (TradingView's built-in session-picker widget, producing a `"HHMM-HHMM"` string) paired with `time(timeframe, session, timezone)` — this is idiomatic, safe Pine, gives Pedro a real UI picker rather than four separate hour/minute number inputs, and inherits DST handling automatically from the platform (§11) with zero custom offset math. This is a build-approach proposal, not a locked requirement — an equivalent `input.int` hour/minute pair per session would also satisfy "configurable," but the session-picker approach is recommended as cleaner and less error-prone for Pedro to adjust from the settings menu.

Regardless of which input mechanism is used, the timezone is never hardcoded to a fixed UTC offset — always resolved through Pine's timezone-aware time functions against the configured timezone string, which is what makes daylight-saving handling automatic (§11).

---

## 6. Exact definition of Hourly High and Hourly Low

**FINAL, redefined from both prior drafts.** `1H H` / `1H L` represent the **High and Low of the most recently completed hourly candle** — not the live-growing current hour (draft 1's model), and not a multi-instance retention list of several completed hours (draft 2's model). There is exactly one `1H H` value and one `1H L` value visible at any time, and they update once, at the top of each new hour, to reflect the hour that just closed.

Implementation: `request.security(syminfo.tickerid, "60", high[1], lookahead=barmerge.lookahead_off)` / the equivalent for `low[1]` — reading the hourly-resolution series one bar back, so the value is always a **fully completed** hourly candle, never the still-forming one. This is the same non-repainting pattern as PDH/PDL (§7), applied at 60-minute resolution instead of daily.

Because this is a single completed value (not an accumulator growing bar-by-bar within the current hour), `1H H`/`1H L` do not "grow live" the way Asia/London/ORB do — they are static between hourly updates, then jump to the new completed hour's values at the top of each hour. This is intentional and matches "avoid repainting": the displayed value never changes after it's first shown for that hour.

If Pedro would prefer a different non-repainting definition (e.g., a rolling N-hour window, or the live-current-hour-plus-history model from draft 2), that must be separately documented and approved before implementation — this specification does not silently reintroduce either alternative.

---

## 7. Level calculation method

| Level | Method |
|---|---|
| PDH / PDL | Previous **completed** exchange-defined daily futures candle: `request.security(syminfo.tickerid, "1D", high[1]/low[1], lookahead=barmerge.lookahead_off)`. This is the prior daily candle as TradingView's own "1D" resolution already defines it for the chart's futures symbol — not a custom ET-midnight-to-midnight aggregation. Values remain stable and unchanged throughout the trading day once read. |
| ASH / ASL, LH / LL, ORH / ORL | Running max/min of `high`/`low` accumulated only over bars whose (configurable-timezone) timestamp falls inside that level's configured window, using the standard Pine accumulator pattern (reset when the window opens, `math.max`/`math.min` while the window is active). These **live-grow** during their window and lock at window close. |
| ORM | `(ORH + ORL) / 2`, computed only once ORB has at least one bar of data; optional toggle, default off. |
| 1H H / 1H L | Per §6 — single most-recently-completed hourly candle via `request.security`, not an accumulator. |

---

## 8. Box creation method

**PROPOSED:** each of the four session boxes (Asia, London, New York, ORB) uses one persistent `box.new(...)` object per box type, updated in place via `box.set_top` / `box.set_bottom` / `box.set_right` while its window is live, rather than deleted-and-recreated every bar (avoids unnecessary object churn and flicker). Box fill is light and transparent by default; border is thin and subtle. Boxes are never filled solid and never visually dominate price action.

**Default colors and transparency (PROPOSED — style-direction only, exact hex/percentages pending the Phase 0 mock, §13):**

| Session/level family | Color direction | Notes |
|---|---|---|
| Asia | Purple | Box + High/Low lines |
| London | Blue | Box + High/Low lines |
| New York | Muted green (working proposal — needs Pedro's confirmation; chosen to be clearly distinct from Asia/London/ORB without implying "bullish," but this is exactly the kind of choice the Phase 0 mock exists to validate) | Box only (no NY H/L level exists, §3) |
| ORB | Orange/amber, slightly more visually prominent than the other three (most-referenced level) | Box + High/Low lines + optional midpoint (dimmer amber, dotted) |
| PDH / PDL | Neutral gray/white, dashed | Line only, no box |
| 1H H / 1H L | Dim teal, dotted, thin — visually subordinate to every other level | Line only, no box |

Historical retained instances (§10), if any beyond the current one, render in a dimmer/lower-opacity variant of their base color, consistent with the general "recede with age" visual hierarchy from draft 2.

---

## 9. Settings structure

**FINAL requirement, PROPOSED exact layout.** Every item Pedro listed is included; grouped using the existing project's `group=` input convention (as used in `nova_execution_v1.pine`):

**Group: Level Visibility** (one independent toggle each, FINAL requirement)
Show/hide PDH · PDL · Asia High · Asia Low · London High · London Low · Hourly High · Hourly Low · ORB High · ORB Low · ORB Midpoint (default off).

**Group: Session Boxes** (one independent toggle each, FINAL requirement)
Show/hide Asia box · London box · New York box · ORB box.

**Group: Labels**
- Show/hide all labels (master switch, labels only — does not hide the underlying lines).
- Individual per-label toggles beyond the per-level toggles above: **DEFERRED** — see §14. The per-level toggles (which already gate line + label together) plus this master label switch (hide all labels while keeping all lines) already give full practical control without doubling the settings-menu size; Pedro's own instruction permits treating this as optional ("if this can be done cleanly") and asks the spec not to overwhelm the settings menu.
- Label size (Small/Normal/Large).
- Label position preference where Pine allows it (right-edge of the line is the default and, practically, closest to Pine's native label-anchoring options).

**Group: Lines**
- Line color, per level family (§8 defaults).
- Line thickness.
- Line style (solid/dashed/dotted per family, §8 defaults).
- Line-lifetime behavior — **PROPOSED, reopened from draft 2's hardcoded rule:** a choice between "Extend through end of NY trading day" (proposed default, matches draft 2's approved 16:00 ET behavior) and "Stop at session end" (line freezes at the right edge of its own box, does not extend further). Both are simple, purely time-based visual behaviors.
- "Continuation until touched" — **DEFERRED**, see §14.

**Group: Boxes**
Box color, box transparency, border visibility, border thickness, historical box limit (§10).

**Group: Session Times**
Timezone (default `America/New_York`), Asia session time, London session time, New York session time (all §4/§5), ORB time (input exists for configurability, but defaults fixed to 08:30–09:30 ET per the FINAL requirement).

No input in any group controls trading behavior, alerts, or strategy — every input is purely visual/display scope, consistent with §1.

---

## 10. Historical lookback behavior

**PROPOSED, reopened from draft 2.** Draft 2 had locked a default of "3 completed sessions per type, 1–5 configurable." Pedro's new instruction explicitly reopens this as a proposal requiring fresh approval, with a strong emphasis on keeping the default chart clean and not showing "weeks of old boxes and labels by default."

**Recommended default: current session only** — i.e., retention depth of **1** (the live-forming instance, plus the most recently completed instance replacing the prior one on rollover, per session type: Asia, London, New York, ORB independently). This is a tighter default than draft 2 proposed, in direct response to "the default chart should remain clean."

**Configurable range: 1–3** via a `sessionsToKeep` input per the "Previous 1–3 sessions" option Pedro listed — deliberately narrower than draft 2's 1–5, again favoring a clean default surface; older retained instances (when the setting is raised above 1) render faded per §8.

**Hourly (`1H H`/`1H L`) has no lookback list at all** — per the redefined §6, it is always exactly one completed hour's value, with no retention concept to configure.

This default must remain useful for TradingView Replay (§11) without accumulating unlimited clutter — bounded by the same 1–3 retention cap during replay as during live/historical viewing.

---

## 11. Non-repainting safeguards

**FINAL requirement.** Two distinct concepts must not be confused, and the spec is explicit about which applies where:

- **Live-growing is expected, not repainting.** Asia/London/ORB High/Low accumulators are *meant* to update every bar while their window is open — that is the whole point of a live session range. This is not repainting: nothing already-displayed silently changes after the fact; the displayed value is always "the correct running high/low as of the current bar," which is exactly what it claims to be.
- **True repainting — a displayed value silently changing after being shown as final — must never happen**, and is the specific risk for `PDH`/`PDL` and `1H H`/`1H L`, both of which read from an already-completed higher-timeframe candle via `request.security`. Both use `lookahead=barmerge.lookahead_off` and read the `[1]`-offset (prior, completed) bar of their respective resolution, guaranteeing the value shown is always final for that period and never silently revised.

**Daylight-saving time:** handled automatically because every session boundary is computed via Pine's timezone-aware time functions against the configured timezone string (§5), never a fixed UTC offset — the same code produces correctly-placed boxes/levels on both sides of a DST changeover with zero special-case logic. Included as an explicit case in the validation checklist (§13).

**Replay behavior:** TradingView's Bar Replay feature re-runs historical bars through the same live logic path — since every level's calculation (§7) is a pure function of bar time and price with no `barstate.isrealtime`-only branching, replay produces the same results as live or historical viewing. Explicitly checked in §13.

---

## 12. Mobile-readability plan

**FINAL requirements, adapted from draft 2's corrections (still valid) plus Pedro's new per-level toggle requirement:**

- Labels are compact, exact-text (§3), positioned at the right edge of their line by default.
- Visibility is layered: per-level/per-box toggles (§9, new, FINAL) give coarse control; the master "show all labels" switch (§9) gives a labels-only override; true per-object label toggles beyond that remain deferred (§14) to avoid a bloated settings menu, per Pedro's own "if this can be done cleanly" framing.
- **No automatic label-collision engine is built in V1** (carried over from draft 2 and reaffirmed by Pedro's new instruction: "Do not build a complex automatic label-collision engine unless separately approved"). Tightly clustered levels (e.g., ORB Low landing very close to PDL) may still visually converge — documented as an accepted V1 limitation, not a bug.
- No labels are created repeatedly on every bar — every label is a persistent object, created once per level/instance and updated (`label.set_xy`, `label.set_text`, etc.) rather than recreated, which is also what keeps mobile chart performance smooth (§14).
- No dashboard/table overlay (`table.new`) — a dense panel reads badly on mobile and isn't needed for a pure levels map.
- Minimum 1px line width, visible at TradingView mobile's default rendering — no sub-pixel/hairline styles.

---

## 13. Validation checklist

Before Phase 1 coding begins, Pedro reviews a static visual mock (colors, line styles, box shading, label placement, per §8's proposed direction) against a real NQ or MNQ chart screenshot — informed by neatness cues from Pedro's reference image (§1), never copying its exact colors/branding. No Pine is written until that mock is approved.

Once implementation begins, validation covers:

1. **Live formation** — Asia, London, New York, and ORB boxes all form and grow correctly on NQ and MNQ, on 1m/5m/15m charts.
2. **Hourly correctness** — `1H H`/`1H L` update exactly once per hour, to the just-completed hour's values, with zero mid-hour changes (non-repainting per §6/§11).
3. **PDH/PDL accuracy** — matches the previous completed daily futures candle exactly; no repaint on historical bars.
4. **Exact labels** — every visible label reads exactly `PDH`, `PDL`, `ASH`, `ASL`, `LH`, `LL`, `1H H`, `1H L`, `ORH`, `ORL`, or `ORM` — no variants.
5. **Independent toggles** — every level and every box can be hidden/shown independently of every other; the master label switch hides labels without hiding lines; no toggle has a side effect on an unrelated element.
6. **Session-time configurability** — changing the Asia/London/New York/ORB session-time inputs correctly moves the corresponding box/levels; the ORB default remains 08:30–09:30 ET until explicitly changed.
7. **Historical lookback default** — confirms the proposed default (current session only, §10) renders cleanly with no old-session clutter, and that raising the retention input to 2 or 3 fades older instances correctly and never exceeds the configured cap.
8. **Line-lifetime behavior** — both configurable modes (extend-through-NY-close vs. stop-at-session-end, §9) behave as documented; "continuation until touched" is confirmed absent (deferred, §14).
9. **No stale objects** — toggling any input off/on, and letting retention rollover happen naturally, leaves no orphaned or duplicate objects and triggers no runtime object-limit errors.
10. **DST alignment** — historical data spanning a DST transition weekend shows every level type staying aligned to correct wall-clock times before and after.
11. **Replay accuracy** — TradingView Bar Replay through a full session cycle produces identical results to live/historical viewing.
12. **NQ/MNQ primary validation** — full checklist run on both NQ and MNQ; ES/MES checked only as a bonus, not blocking sign-off (§15).
13. **Mobile readability** — labels legible, lines visible, no dashboard/table overlay, on a real mobile device or TradingView's mobile emulation.

---

## 14. Optional features — explicitly deferred, not silently built or silently dropped

- **Continuation-until-touched line behavior.** Pedro explicitly allowed this to be deferred if it adds excessive complexity. It does: correctly tracking "has price touched this level since it locked" without drifting into reaction-detection/signal territory requires careful scoping that has not been done here. **Recommendation: defer to a future, separately-specified revision.** V1 ships with the two simpler, purely time-based line-lifetime modes from §9 only.
- **Fully independent per-label toggles** beyond the per-level/per-box toggles and the master label switch (§9, §12). Recommendation: defer; revisit only if Pedro finds the two-layer model insufficient in practice.
- **Session retention depth above 3**, or any "current day" / "user-defined lookback" mode beyond the 1–3 range proposed in §10. Recommendation: ship the tighter 1–3 range; revisit if Pedro wants deeper history after using V1.

None of the above is present in the shipped V1 settings menu unless Pedro explicitly asks for it to be un-deferred before Phase 0.

---

## 15. Limitations imposed by Pine or chart timeframe

- **Session-window precision is only accurate on lower timeframes.** An 08:30 ET ORB boundary (or any session boundary) cannot be reliably reconstructed from coarse bars without lower-timeframe aggregation, which V1 does not build. **PROPOSED, carried over from draft 2:** full session-box and hourly precision on **1m, 3m, 5m, and 15m** charts; auto-suppressed (drawing nothing, never an approximation) above 15m. PDH/PDL is unaffected (reads a single daily candle regardless of chart timeframe) and works on any intraday timeframe.
- **Pine's per-indicator object limits** (`max_lines_count`, `max_labels_count`, `max_boxes_count`) are hard platform caps. V1's design (persistent, updated-not-recreated objects; bounded 1–3 retention; no per-bar object creation) keeps real usage far below reasonable declared limits, but the exact declared numbers are an implementation detail to finalize during Phase 1, not this specification.
- **NQ/MNQ are the primary validation target (FINAL).** ES/MES compatibility may remain possible since the implementation is symbol-agnostic by construction (no hardcoded ticker/tick-size/contract-multiplier logic), but ES/MES is not part of the V1 acceptance bar and any symbol-specific issue there does not block sign-off.
- **No automatic label-collision avoidance** (§12) — a Pine/complexity limitation accepted by design, not a bug to fix later within V1's scope.

---

## Exact files that will be created

**Only one new file, and only after Pedro approves this specification and the Phase 0 mock:**

```
indicators/nova_market_map_v1.pine
```

No other file is created or modified as part of Market Map V1 — not `ui/html.py`, not any `main.py` route, not any file under `services/`, `engines/`, `delivery/`, `core/`, `tests/`, or `data/`. This specification document (`nova_knowledge_core/MARKET_MAP_V1_SPECIFICATION.md`) is the only file this revision touches.

---

## Proposed small commit sequence (implementation, not yet authorized)

Each commit is one small, independently visible layer, per "we are developing one clean visual layer at a time." None of these commits happen until Pedro approves this specification and the Phase 0 mock.

| # | Commit | Adds |
|---|---|---|
| 0 | *(not a code commit)* Phase 0 visual mock reviewed and approved | — |
| 1 | `Add Market Map V1 skeleton (PDH/PDL only)` | File creation, input scaffold, object-limit declaration, PDH/PDL only |
| 2 | `Add ORB box, levels, and optional midpoint` | ORH/ORL/ORM, ORB box, fixed 08:30–09:30 ET default |
| 3 | `Add Asia session box and levels` | ASH/ASL, Asia box |
| 4 | `Add London session box and levels` | LH/LL, London box |
| 5 | `Add New York session box` | NY box only (no NY H/L level, §3) |
| 6 | `Add Hourly High/Low (most recent completed hour)` | 1H H/1H L per the §6 definition |
| 7 | `Add full settings/toggle surface` | Per-level/per-box toggles, label master switch, line/box style groups, session-time configurability |
| 8 | `Add historical retention and line-lifetime behavior` | §10 default + 1–3 config, §9 line-lifetime modes |
| 9 | `Validation pass` | Full §13 checklist executed on NQ and MNQ; DST and replay checks; Pedro signs off on V1 as complete |

---

## Summary: what still needs Pedro's decision

**Final, no further approval needed:**
- ORB window (08:30–09:30 ET default).
- The eleven key levels and their exact label text (§3).
- Four session boxes including the new New York box (§4).
- Hourly High/Low = single most-recently-completed hourly candle, non-repainting (§6).
- Per-level and per-box independent visibility toggles (§9).
- NQ/MNQ as the primary validation instruments (§15).
- The exclusion list (§1) and all development-safety boundaries (§16 below).

**Proposed, awaiting Pedro's approval:**
1. Asia, London, New York default session times (§4) — the table's values, or Pedro's preferred alternative.
2. Timezone/session-input mechanism — `input.session()` + timezone string vs. plain hour/minute inputs (§5).
3. Default colors and the New York color family specifically (§8) — locked at the Phase 0 mock, not here.
4. Historical retention default — current-session-only (depth 1), configurable 1–3 (§10).
5. Line-lifetime default — extend-through-NY-close vs. stop-at-session-end (§9).
6. Proposed Pine filename and indicator title (§2).
7. The proposed small-commit sequence itself (above) — order and grouping.

**Deferred, not built in V1 unless Pedro un-defers it (§14):**
- Continuation-until-touched line behavior.
- Fully independent per-label toggles beyond the per-level/master-switch model.
- Retention depth beyond 3, or any non-bounded lookback mode.

---

## Development safety boundaries (unchanged, restated)

This is a fresh, standalone visual indicator. It does not reuse or copy logic from the archived ORB signal engine, PROS, ICT, IB, the legacy execution indicator, the canonical BUY/SELL state, the old scoring system, old webhook logic, or old bridge logic — and it is never connected to NOVA execution.

This specification revision touches **only** `nova_knowledge_core/MARKET_MAP_V1_SPECIFICATION.md`. It does not modify, and no future Market Map V1 work will modify without a separate explicit request: Journal, Market/News, NOVA Assistant, broker code, execution code, risk logic, existing historical data, Alerts, the retired trading subsystem, the live TradingView cloud script, the existing archived Pine indicator (`indicators/nova_execution_v1.pine`), the pre-existing Phase 8 `main.py` diff, or the `mcp/tradingview` submodule pointer. No live TradingView automation is used. All work stays local until Pedro manually reviews and approves deployment; nothing is pushed.

Nothing in this document authorizes Pine implementation. Phase 0 (style mock review) is the next step, and only after Pedro approves this specification as a whole.
