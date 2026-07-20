# Market Map V1 — Specification

Date: 2026-07-19
Status: **Specification only. No Pine code exists yet.** This document defines what Market Map V1 must do before a single line of Pine is written. It follows the controlled retirement of the legacy NOVA EXECUTION V1 indicator (`indicators/nova_execution_v1.pine`, archived, not deleted) and the UI retirement documented in `TRADING_SUBSYSTEM_UI_RETIREMENT.md`. This is the first artifact of the clean rebuild track — nothing here authorizes implementation. Pedro must explicitly approve this specification, and separately approve each phase of implementation, before any Pine file is created or edited.

---

## 1. Exact purpose and non-purpose

**Purpose:** Market Map V1 is a *visual reference layer*. It draws session boxes and key historical/current price levels on the chart so a discretionary trader can see where price has been and where the current session's range sits, at a glance. It answers "where are the levels that matter" — nothing more.

**Non-purpose — Market Map V1 is not:**

- Not a strategy. It contains no entry/exit logic of any kind.
- Not a signal generator. It never tells the user to buy or sell.
- Not a scoring or grading system. No confidence, no A–D grades, no bias score.
- Not connected to NOVA. No bridge, no backend call, no webhook, no dependency on Harvey, Market Reality, or any NOVA data file.
- Not a strategy-family implementation. No PROS, ICT, IB, FVG, MACD, or any other named methodology.
- Not an alerting tool. No `alertcondition()`, no TradingView alert triggers.
- Not an execution or broker-adjacent tool in any way.

It must run as a completely standalone `//@version=6 indicator(...)` script that a user could delete NOVA entirely and still find useful on any TradingView chart.

---

## 2. Exact session times and timezone behavior

All session boundaries are anchored to **America/New_York (Eastern Time)**, regardless of the chart's symbol exchange timezone or the user's personal TradingView timezone display setting. This matches the session model already used elsewhere in NOVA (`core/config.py::session_label()`), so "Asia," "London," and "ORB" mean the same wall-clock windows here as everywhere else in the product.

| Session | Window (ET) | Notes |
|---|---|---|
| Asia | 19:00 – 03:00 | Spans midnight; opens the prior calendar evening, closes the next calendar morning. |
| London | 03:00 – 09:30 | Immediately follows Asia. |
| ORB | 08:30 – 09:30 | Explicitly specified by Pedro. Overlaps the tail end of London — this is intentional and matches how the pre-NY-open ramp is already understood elsewhere in NOVA. |
| Hourly | Every ET clock hour, `:00`–`:00` | Independent of the three sessions above; see §8. |

Implementation must use Pine's timezone-aware time functions (`time(timeframe, session, "America/New_York")` or equivalent `hour()`/`minute()` calls against a `"America/New_York"`-adjusted timestamp) — never a fixed UTC offset. This is what makes DST handling automatic (§16).

**Decision requiring approval:** confirming ET-anchoring (not exchange-local, not viewer-local) is correct for all four windows above. This is the recommended default and matches the rest of NOVA, but it is stated here explicitly because it silently changes where every box/level lands for anyone whose TradingView timezone display is set to something other than ET.

---

## 3. How every high and low is calculated

Every level is a running max/min of `high`/`low` accumulated only over bars whose ET timestamp falls inside that level's defining window, using the standard Pine accumulator pattern:

```
var float rangeHigh = na
var float rangeLow  = na
if inWindow and not inWindow[1]        // window just opened
    rangeHigh := high
    rangeLow  := low
else if inWindow
    rangeHigh := math.max(rangeHigh, high)
    rangeLow  := math.min(rangeLow, low)
```

| Level | Source window |
|---|---|
| Asia High / Low | Asia window (§2) |
| London High / Low | London window (§2) |
| ORB High / Low | ORB window (§2) |
| Hourly High / Low | Current ET clock hour (§8) |
| Previous Day High / Low | The prior completed trading day, via `request.security(syminfo.tickerid, "1D", high[1])` / `low[1]` |

**Decision requiring approval — "day" boundary for PDH/PDL:** futures trade nearly 24 hours, so "day" is ambiguous. Two reasonable definitions:
- (a) Plain ET calendar day (midnight–midnight ET) — simplest, matches how a discretionary trader reading a daily chart usually thinks about "yesterday."
- (b) CME futures trading-day convention (roughly 18:00 ET prior evening – 17:00 ET), which is what a daily futures bar on TradingView actually represents.

**Recommendation: (a), plain ET calendar day**, for simplicity and because Market Map is a manual visual aid, not a futures-settlement tool — but this is explicitly Pedro's call, since it changes the literal PDH/PDL values shown, and (b) is the more "technically correct" futures convention.

---

## 4. When each level begins displaying

Session/ORB/Hourly levels **display live, growing in real time**, from the first bar of their window onward — the box and its High/Low lines appear as soon as the window opens and update every bar until the window closes. This is the standard, expected ORB-box behavior and is recommended for all four windowed levels (Asia, London, ORB, Hourly) for consistency.

PDH/PDL display from the first bar of the current trading day (they don't "grow" — they're already-known fixed values pulled from the completed prior day via `request.security`).

**Decision requiring approval:** live-growing vs. "hidden until the window closes, then appears fully formed." Live-growing is recommended (it's the standard ORB pattern and lets a trader watch the range build), but a hidden-until-closed mode is a legitimate, quieter alternative some traders prefer.

---

## 5. When each level stops extending or resets

- **Asia / London / ORB:** the box stops growing at its window's close (e.g., ORB box locks at 09:30 ET). After close, the High/Low become static lines that extend forward (right) through the rest of that trading day as reference levels, until the same session's *next* occurrence begins — at which point the old box/lines are removed and a new one starts (see §6, retention model).
- **Hourly:** locks at the top of the next ET hour; see §8 for how many hourly ranges stay visible.
- **PDH/PDL:** re-anchors once per day at the ET day rollover (§3), replacing yesterday's values with the newly-completed day's values.

Reset trigger for every level is strictly time-based (ET clock), never price-based (no "level resets if broken" logic — that would be trading logic, which is explicitly excluded).

---

## 6. Historical versus current-session behavior

**Recommended default: single most-recent instance per level type.** When a new Asia session begins, the previous Asia box/lines are deleted and replaced — the chart never accumulates more than one Asia box, one London box, one ORB box at a time (plus the live-forming current one, which *is* that one instance while its window is open). This keeps the chart clean and keeps object counts low and predictable (§13).

**Decision requiring approval — retention depth:** should Market Map V1 optionally keep more than one prior session visible (e.g., last 2–3 days, faded/dimmed), or strictly single-most-recent? Recommendation: **strictly single-most-recent for V1**, with a `sessionsToKeep` input (default 1, capped at 3) as a documented but not-yet-built extension point if Pedro wants depth later. Building configurable multi-session depth now would add real complexity for a "V1, keep it simple" tool.

---

## 7. ORB construction and optional midpoint behavior

- Box drawn from 08:30–09:30 ET, top = ORB High, bottom = ORB Low, live-growing per §4.
- At 09:30 ET the box locks; ORB High and ORB Low become two solid horizontal lines extending right for the remainder of the trading day.
- **Optional ORB midpoint** (`(ORB High + ORB Low) / 2`): user-toggleable input, default **off** (keeps the chart minimal by default). When enabled, drawn as a distinct dotted/thin line between the High and Low lines, clearly less visually dominant than the two boundary lines.

---

## 8. Hourly High/Low behavior

Rolling per-ET-hour high/low: window = `[HH:00, HH+1:00)` ET, resets at the top of every hour, live-growing per §4, locks at hour-close and becomes a static reference line pair like the session levels.

**Decision requiring approval — scope:** drawing all 24 hourly ranges per day would clutter the chart badly and blow past reasonable object limits on a busy day. Recommendation: **keep only the most recent N completed hours visible, default N = 3 (configurable, capped at 6)**, plus the live-forming current hour. Older hourly boxes are deleted as new ones form (rolling window, same retention pattern as §6).

---

## 9. Session-box construction

Each session (Asia, London, ORB) is drawn with `box.new(left=<window-open bar>, right=<current or window-close bar>, top=rangeHigh, bottom=rangeLow, ...)`, one box per active/most-recent instance, updated in place (`box.set_*`) while the window is live rather than deleted-and-recreated every bar (performance: avoids unnecessary object churn). Hourly levels use the same construction pattern at smaller scale. See §10 for the exact styling of each box.

---

## 10. Labels, colors, line styles, widths, and transparency

**This entire section is a proposal pending Pedro's visual sign-off** — NOVA's established pattern (per `nova_ui_vision/` mockup review) is that color/visual decisions get explicit approval before being built, and this is no different for a chart indicator.

Proposed default style table:

| Level | Color family | Box fill | Line style | Width | Label |
|---|---|---|---|---|---|
| Asia High/Low + box | Purple | 85–90% transparent | Solid | 1px | `ASIA H` / `ASIA L`, right-aligned at line end |
| London High/Low + box | Blue | 85–90% transparent | Solid | 1px | `LDN H` / `LDN L` |
| ORB High/Low + box | Orange/amber | 80–85% transparent | Solid | 2px (slightly heavier — most-referenced level) | `ORB H` / `ORB L` |
| ORB Midpoint (optional) | Same amber, dimmer | n/a (line only) | Dotted | 1px | `ORB MID` |
| Previous Day High/Low | Gray/white, neutral | n/a (line only, no box) | Dashed | 1px | `PDH` / `PDL` |
| Hourly High/Low | Teal, dim | n/a (line only, no box) | Dotted | 1px | `H1 H` / `H1 L` (or omitted — see mobile note §11) |

All labels use a small, fixed-size font (not scaling with zoom) positioned at the right edge of each line, with a short abbreviation rather than a full word, to minimize clutter. Full color hex values, exact transparency percentages, and final label text are **not locked** — this table is a starting proposal for Pedro to react to, adjust, or reject before implementation, ideally against a rendered mock (§17 acceptance criteria includes a visual-mock review step before Phase 1 coding begins).

---

## 11. Mobile readability requirements

- No label may overlap another by default at typical zoom levels — if two levels converge (e.g., ORB Low ≈ PDL), the implementation must offset labels vertically rather than let them collide illegibly.
- Every label is individually toggleable (not just every box) so a user on a small screen can strip down to just the lines they care about.
- Minimum line width of 1px must remain visible at TradingView's mobile app default line rendering — no sub-pixel or "hairline" styles.
- Hourly labels (§10) default to **off** on top of the line-drawing default being on, since six simultaneous hourly labels plus three session labels plus PDH/PDL is likely to be unreadable on a phone-sized chart; lines still render, just unlabeled, unless the user explicitly enables hourly labels.
- No dashboard/table overlay (`table.new`) is part of V1 — that's exactly the kind of dense panel that reads badly on mobile and isn't needed for a pure levels map.

---

## 12. User-configurable settings

Grouped, matching the existing project's input-grouping convention (`group=` parameter, as used in `nova_execution_v1.pine`):

**Group: Session Visibility**
- Show Asia session (bool, default true)
- Show London session (bool, default true)
- Show ORB session (bool, default true)
- Show Hourly levels (bool, default true)
- Show Previous Day H/L (bool, default true)

**Group: ORB**
- Show ORB midpoint (bool, default false)

**Group: Hourly**
- Number of recent hourly ranges to keep (int, default 3, min 1, max 6)

**Group: History Depth**
- Sessions to keep per type (int, default 1, min 1, max 3) — see §6

**Group: Labels**
- Show session labels (bool, default true)
- Show hourly labels (bool, default false) — see §11
- Label size (string: Small/Normal/Large)

**Group: Style**
- Per-level color pickers (Asia, London, ORB, ORB Midpoint, PDH/PDL, Hourly) — one `input.color` each, defaults per §10
- Line width for session levels (int, default 1)
- Line width for ORB levels (int, default 2)
- Box fill transparency (int 0–100, default per §10)

No input controls anything about trading behavior, alerts, or strategy — every input listed above is purely visual/display scope, consistent with §1's non-purpose list.

---

## 13. Object-limit and performance safeguards

Pine enforces hard per-indicator limits on drawn objects. `nova_execution_v1.pine` declares `max_lines_count=500, max_labels_count=500, max_boxes_count=200, max_bars_back=2000` for a much heavier, multi-feature dashboard indicator. Market Map V1 draws a small, bounded number of objects by design (§6, §8 retention limits), so it should declare much lower, tighter limits as a defensive measure — if the object count ever unexpectedly exceeds the declared cap, Pine throws a runtime error rather than silently misrendering, which is the correct failure mode for a "keep it simple" tool.

Proposed declaration:

```
//@version=6
indicator("Market Map V1", overlay=true, max_lines_count=60, max_labels_count=60, max_boxes_count=20, max_bars_back=2000)
```

Object lifecycle rule: every level type owns a small, fixed set of object-ID variables (`var box asiaBox`, `var line orbHighLine`, etc.) that are updated in place or explicitly deleted (`box.delete()`, `line.delete()`) and recreated on rollover — never accumulated without bound. No level type may create a new object every bar without deleting the previous one.

---

## 14. Behavior across NQ and MNQ

Market Map V1 must be **symbol-agnostic** — it reads only OHLC price action from whatever chart it is applied to (`high`, `low`, `open`, `close`, `time`) and contains no hardcoded ticker, tick size, contract multiplier, or point-value logic. NQ and MNQ (and, incidentally, ES/MES or any other instrument) render structurally identically — same boxes, same lines, same behavior — with values simply reflecting whatever price series is on screen. No special-casing by symbol is required or permitted.

---

## 15. Behavior across chart timeframes

- **PDH/PDL:** meaningful and correctly rendered on any timeframe from 1-minute up to (and including) the daily chart itself is borderline — on a daily chart, "previous day" becomes "previous bar," which is trivially correct but visually redundant. No special handling needed below 1D.
- **Session boxes (Asia/London/ORB) and Hourly levels:** lose meaning once a single bar can span an entire session or more (e.g., a 4H or Daily bar comprises multiple sessions, making a "session box" nonsensical).

**Decision requiring approval — the disable cutoff:** recommendation is to auto-suppress session-box and hourly-level drawing (not the whole indicator — PDH/PDL should keep working) on any chart timeframe of **4 hours or higher**, since a 4H bar already spans roughly half of one of the defined sessions. On timeframes at or below 1H, all levels render normally. This threshold is a judgment call Pedro should confirm or adjust.

---

## 16. Daylight-saving-time handling

Because every session boundary is computed using Pine's timezone-aware time functions against the `"America/New_York"` timezone string (§2) rather than a fixed UTC offset, DST transitions are handled automatically by the TradingView platform — the same Pine code produces boxes at the correct 08:30–09:30 ET ORB window on both sides of a DST changeover with zero special-case code. This is standard, well-documented Pine behavior, not new logic being introduced by this spec; it's called out explicitly so it's a known, verified property rather than an untested assumption. Acceptance testing (§17) includes an explicit check across a DST transition weekend.

---

## 17. Acceptance criteria and visual test cases

Before Phase 1 coding begins, Pedro reviews a static visual mock of the proposed style table (§10) — colors, line styles, label placement — against a real chart screenshot, the same way UI mockups are reviewed elsewhere in this project. No Pine is written until that mock is approved.

Once implementation begins, each phase (§19) ends with a manual visual check against these cases:

1. **Live ORB formation** — apply to an NQ (or MNQ) 5-minute chart during the 08:30–09:30 ET window; confirm the ORB box visibly grows bar-by-bar and locks correctly at 09:30.
2. **PDH/PDL accuracy** — confirm the drawn Previous Day High/Low lines match the actual prior day's high/low read directly off the daily chart.
3. **Asia/London box placement** — confirm both boxes appear at the correct ET wall-clock windows regardless of the chart's displayed timezone setting.
4. **DST boundary** — load historical data spanning a DST transition weekend; confirm session boxes stay aligned to correct ET wall-clock times before and after.
5. **All-off state** — disable every input toggle; confirm the indicator draws nothing and leaves zero orphaned objects on the chart.
6. **Symbol swap** — apply the same settings to NQ, then MNQ (then ES/MES as a bonus check); confirm structurally identical rendering.
7. **Timeframe cutoff** — confirm session/hourly levels render on a 15m chart and auto-suppress (while PDH/PDL keeps rendering) on a 4H or Daily chart, per §15.
8. **Mobile viewport** — open the chart in the TradingView mobile app; confirm no label overlap and that lines remain visible at default rendering.
9. **Object-count stability** — leave the indicator running across a full multi-day session (Asia → London → ORB → NY → next Asia) and confirm no accumulation of stale/duplicate objects and no runtime object-limit errors.

---

## 18. Explicit exclusions preventing scope creep

Market Map V1 must never contain, at any point in its lifetime as "V1":

- [ ] No strategies of any kind
- [ ] No BUY or SELL signals or markers
- [ ] No trade recommendations, in labels, tooltips, or comments
- [ ] No `alertcondition()` or any TradingView alert wiring
- [ ] No scoring, grading, or confidence system
- [ ] No PROS, ICT, IB, or FVG logic or terminology
- [ ] No MACD or any other momentum/oscillator indicator
- [ ] No execution logic of any kind
- [ ] No broker integration
- [ ] No canonical-signal system or NOVA Bridge dependency
- [ ] No Harvey or Market Reality dependency
- [ ] No NOVA backend dependency — no `request.security` calls to anything other than the chart's own symbol, no webhook, no network call of any kind (Pine cannot make arbitrary network calls, but this rules out any future temptation to bolt one on via a workaround)
- [ ] No dashboard/table overlay (kept out per §11, mobile readability)

If a future version needs any of the above, that is a new, separately-scoped, separately-approved specification — not a silent addition to Market Map V1.

---

## 19. Phased implementation plan with visual verification

Each phase is small, produces something Pedro can look at on a real chart, and requires his go-ahead before the next phase starts. No phase begins without approval of the previous one's visual check.

| Phase | Scope | Visual check |
|---|---|---|
| 0 | Style mock review (§17) — no code | Pedro approves color/line/label proposal or sends back changes |
| 1 | Skeleton indicator: `//@version=6 indicator(...)` declaration, object-limit safeguards (§13), Previous Day High/Low only (simplest level, no session-window logic) | PDH/PDL lines appear correctly on a live NQ chart |
| 2 | ORB box + High/Low lines, live-growing and locking per §4/§7 | ORB box forms correctly during a live or replayed 08:30–09:30 ET window |
| 3 | ORB optional midpoint toggle | Midpoint line appears only when enabled, styled distinctly from boundary lines |
| 4 | Asia session box + High/Low | Asia box forms across the correct overnight ET window |
| 5 | London session box + High/Low | London box forms correctly, including the transition boundary into ORB |
| 6 | Hourly High/Low, rolling retention (§8) | Hourly boxes roll off correctly, only the configured N most recent remain |
| 7 | Full settings/inputs panel (§12), retention-depth config (§6) | Every toggle/color/width input works as documented, no orphaned objects when toggled off |
| 8 | Timeframe cutoff (§15) + DST verification (§16) + full acceptance pass (§17, all 9 cases) | All nine acceptance cases pass; Pedro signs off on V1 as complete |

No phase after 0 begins implementation without this specification being approved first, and no phase after its own number begins without that phase's visual check being explicitly approved by Pedro.

---

## Summary of decisions requiring Pedro's explicit approval

1. **§2** — ET-anchoring for all session windows, regardless of viewer timezone.
2. **§3** — PDH/PDL day-boundary definition: plain ET calendar day (recommended) vs. CME futures trading-day convention.
3. **§4** — Live-growing boxes/levels (recommended) vs. hidden-until-window-closes.
4. **§6** — Retention depth: strictly single-most-recent per session type (recommended) vs. configurable multi-session fade.
5. **§8** — Hourly scope: most-recent N hours only, default N=3 (recommended) vs. all 24 hours.
6. **§10** — The entire proposed color/line-style/label table is a starting point, not a locked design — needs visual sign-off, ideally against a rendered mock per §17 Phase 0.
7. **§15** — Timeframe auto-suppress cutoff: 4H and above (recommended) — confirm or adjust.

Nothing in this document authorizes Pine implementation. Phase 0 (style mock review) is the very next step, and only after Pedro approves this specification as a whole.
