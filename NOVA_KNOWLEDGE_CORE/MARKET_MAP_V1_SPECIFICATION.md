# Market Map V1 — Specification

Date: 2026-07-19
Status: **Specification only. No Pine code exists yet.** This document defines what Market Map V1 must do before a single line of Pine is written. It follows the controlled retirement of the legacy NOVA EXECUTION V1 indicator (`indicators/nova_execution_v1.pine`, archived, not deleted) and the UI retirement documented in `TRADING_SUBSYSTEM_UI_RETIREMENT.md`. This is the first artifact of the clean rebuild track — nothing here authorizes implementation. Pedro must explicitly approve this specification, and separately approve each phase of implementation, before any Pine file is created or edited.

**Revision note (2026-07-19):** the overall direction was approved, with seven corrections applied — PDH/PDL definition (exchange daily candle, not a custom ET-midnight aggregation), session history retention (3 completed instances, not 1), Hourly High/Low redefined as lines only (not boxes), simplified label toggles (three category toggles, not per-object), tighter supported-timeframe range (1m–15m, not "up to 1H"), an explicit 16:00 ET line-lifetime rule, and a settings table matching all of the above. This revision supersedes the original per-section text everywhere the two disagree; the seven approved foundational decisions (ET-anchoring, the three session windows, live-growing display, ORB midpoint default-off, and the full exclusion list) are unchanged from the first draft.

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
| ORB | 08:30 – 09:30 | Explicitly specified by Pedro. Overlaps the tail end of London — **approved as intentional**: the two windows measure different things (London's full session range vs. the tighter pre-open ORB range), and both lock at 09:30 ET, before Pedro's active NY trading window continues. |
| Hourly | Every ET clock hour, `:00`–`:00` | Independent of the three sessions above; see §8. |

Implementation must use Pine's timezone-aware time functions (`time(timeframe, session, "America/New_York")` or equivalent `hour()`/`minute()` calls against a `"America/New_York"`-adjusted timestamp) — never a fixed UTC offset. This is what makes DST handling automatic (§16).

**Approved (2026-07-19):** ET-anchoring for all four windows above, regardless of viewer timezone, is confirmed as final for V1 — not exchange-local, not viewer-local.

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
| Previous Day High / Low | The prior **completed exchange-defined daily futures candle** for the chart's symbol — see below. |

**Approved (2026-07-19) — PDH/PDL definition, corrected:** the original draft's `request.security(syminfo.tickerid, "1D", high[1])` / `low[1]` proposal is kept, but the framing around it was wrong and is corrected here: this is **not** a plain ET midnight-to-midnight aggregation, and the spec must not claim it is. It is simply the prior completed daily candle as TradingView's own "1D" resolution already defines it for the chart's futures symbol (NQ/MNQ), whatever exchange session convention that resolution already uses internally — Market Map V1 does not reimplement or second-guess that convention.

Requirements for this correction:

- PDH/PDL use the previous **completed** exchange-defined daily candle — never the still-forming current daily candle.
- The `request.security` call must be written without lookahead/repainting (`lookahead=barmerge.lookahead_off`, and the `[1]` offset applied to the *requested* series so a completed bar is always read, never the in-progress one).
- Once read for the day, PDH/PDL values must remain **stable and unchanged** throughout Pedro's NY trading window — they do not silently shift intraday.
- **No custom midnight-to-midnight ET daily aggregation is built in V1.** This was the original draft's error: proposing a plain-ET-day definition alongside 1D-candle code that doesn't actually produce one. V1 uses the exchange daily candle only.

---

## 4. When each level begins displaying

Session/ORB/Hourly levels **display live, growing in real time**, from the first bar of their window onward — the box and its High/Low lines appear as soon as the window opens and update every bar until the window closes. This is the standard, expected ORB-box behavior and is recommended for all four windowed levels (Asia, London, ORB, Hourly) for consistency.

PDH/PDL display from the first bar of the current trading day (they don't "grow" — they're already-known fixed values pulled from the completed prior day via `request.security`, per the corrected definition in §3).

**Approved (2026-07-19):** live-growing display is confirmed as final for V1 for all windowed levels (Asia, London, ORB, Hourly) — not the hidden-until-closed alternative.

---

## 5. When each level stops extending or resets

**Approved (2026-07-19), corrected — line lifetime:** the original draft's "extends forward until the same session's next occurrence begins" was too vague and risked old session levels visually bleeding into unrelated overnight periods. Final rule:

- **Asia / London / ORB:** the box stops growing at its window's close (e.g., ORB box locks at 09:30 ET). After close, the High/Low become static lines that extend forward (right) only **through 16:00 ET on the associated NY trading day** — not indefinitely, not until the next session begins. At 16:00 ET the line's extension stops (the line itself remains visible as history per the §6 retention depth; it simply stops drawing further right).
- **Session boxes themselves** (the shaded rectangle, as opposed to the extended H/L lines) stay fixed over their actual session window — they never stretch to 16:00, only the two boundary lines do.
- **Hourly:** locks at the top of the next ET hour and follows its own rolling retention rule (§8) — not the 16:00 rule, since hourly ranges are already short-lived by design.
- **PDH/PDL:** remain visible and stable throughout the entire applicable trading day (§3) — the 16:00 rule does not apply to PDH/PDL, since "yesterday's high/low" is meaningful for the full day, not just until the NY close.

Reset trigger for every level is strictly time-based (ET clock), never price-based (no "level resets if broken" logic — that would be trading logic, which is explicitly excluded).

---

## 6. Historical versus current-session behavior

**Approved (2026-07-19), corrected:** strictly single-most-recent was rejected as too weak for chart review and TradingView replay. Final V1 behavior:

- **Default completed-session history depth: 3** instances per session type (Asia, London, ORB each independently keep their own last 3 completed instances).
- **Configurable range: 1–5** via a `sessionsToKeep` input.
- The **live-forming current instance is additional to, not counted within,** that retained-history number — at the default setting of 3, the chart shows 3 completed sessions plus whichever session is currently forming, per type.
- Older retained instances are **visually faded** relative to the most recent completed one (lower opacity / dimmer color), so the eye is drawn to the most recent completed range first while older ones remain available for context.
- This is bounded and rolling: when a new session completes, the oldest retained instance for that type is deleted (`box.delete()` / `line.delete()`) so the count never exceeds the configured depth. **Unlimited historical sessions are never drawn.**

---

## 7. ORB construction and optional midpoint behavior

- Box drawn from 08:30–09:30 ET, top = ORB High, bottom = ORB Low, live-growing per §4.
- At 09:30 ET the box locks; ORB High and ORB Low become two solid horizontal lines extending right **through 16:00 ET** (§5), not indefinitely.
- **Optional ORB midpoint** (`(ORB High + ORB Low) / 2`): user-toggleable input, default **off** — **approved as final (2026-07-19)**. When enabled, drawn as a distinct dim amber dotted/thin line between the High and Low lines, clearly less visually dominant than the two boundary lines.

---

## 8. Hourly High/Low behavior

**Approved (2026-07-19), corrected — lines only, not boxes.** The original draft described Hourly High/Low using the same box-construction pattern as the sessions; that was wrong. Hourly High/Low is a **line-only** feature with no box, no fill, at any point in V1.

- Window = `[HH:00, HH+1:00)` ET, resets at the top of every hour.
- The **live current ET hour's developing High and Low** are shown as two thin lines that extend and update in real time as the hour progresses (live-growing per §4, applied to lines directly — no intermediate box object is ever created).
- At hour-close, the pair locks and becomes part of the completed-hour retention set below.
- **Completed-hour retention: default 2, configurable 1–3** (not the original draft's N=3/capped-at-6 box-based scope). At the maximum setting (3), the chart shows the current developing hour plus the 3 most recently completed hourly pairs — 4 pairs of lines total at most.
- Older completed-hour line pairs are **explicitly deleted** (`line.delete()`) as new ones roll in, so the retained count never exceeds the configured limit.
- Hourly lines are **thin and visually subordinate** to session/ORB/PDH-PDL lines (dim teal, dotted, 1px — see §10) — they are a secondary reference, not a headline level.
- **No hourly box fill exists at any point.** No hourly box construction, no hourly box retention — both were incorrect in the original draft and are removed here.
- Hourly labels default **off** (§11/§12) — with no boxes and no default labels, the current-hour-plus-two-completed default stays visually quiet even though it's four line pairs.

---

## 9. Session-box construction

Each session (Asia, London, ORB) is drawn with `box.new(left=<window-open bar>, right=<current or window-close bar>, top=rangeHigh, bottom=rangeLow, ...)`, updated in place (`box.set_*`) while the window is live rather than deleted-and-recreated every bar (performance: avoids unnecessary object churn), with up to the configured retention depth (§6) of completed instances kept simultaneously, oldest deleted on rollover. **Hourly High/Low is line-only (§8) and does not use `box.new` at all** — this is a correction from the original draft, which incorrectly implied a shared box-based construction pattern for hourly levels. See §10 for the exact styling of each box and line.

---

## 10. Labels, colors, line styles, widths, and transparency

**Approved general visual hierarchy (2026-07-19); exact hex values and transparency percentages remain pending Phase 0 visual mock approval.** The color family, relative prominence, and line-style choices below are confirmed as the direction to build the Phase 0 mock against — NOVA's established pattern (per `nova_ui_vision/` mockup review) is that exact color/visual decisions get explicit sign-off against a rendered mock before being built, and that final step has not happened yet.

Approved-direction style table:

| Level | Color family | Box fill | Line style | Width | Label |
|---|---|---|---|---|---|
| Asia High/Low + box | Purple | Transparent, subtle | Solid | 1px | `ASIA H` / `ASIA L`, right-aligned at line end |
| London High/Low + box | Blue | Transparent, subtle | Solid | 1px | `LDN H` / `LDN L` |
| ORB High/Low + box | Orange/amber | Transparent, subtle | Solid | 2px (slightly more prominent — most-referenced level) | `ORB H` / `ORB L` |
| ORB Midpoint (optional) | Dim amber | n/a (line only) | Dotted | 1px | `ORB MID` |
| Previous Day High/Low | Neutral gray/white | n/a (line only, no box) | Dashed | 1px | `PDH` / `PDL` |
| Hourly High/Low | Dim teal | n/a (line only, no box — see §8 correction) | Dotted | 1px | `H1 H` / `H1 L` for the live-forming hour; completed pairs unlabeled by default (hourly labels default off, §11/§12) |

Retained historical instances (§6) render in a dimmer/lower-opacity variant of their level's base color, so the most recent completed instance of each session type is always the most visually prominent, with older retained instances receding.

All labels use a small, fixed-size font (not scaling with zoom), positioned at the right edge of each line, using short abbreviations rather than full words, per the corrected label-complexity rules in §11. Exact color hex values, precise transparency percentages, and final label text are **not locked** — this table is the approved starting direction for Pedro to react to against a rendered Phase 0 mock (§17), not a final palette.

---

## 11. Mobile readability requirements

**Approved (2026-07-19), corrected — label complexity scaled back.** The original draft promised per-object label toggles and a label-collision-avoidance engine; both were rejected as overbuilt for V1. Corrected requirements:

- Labels are kept short (compact abbreviations, e.g. `ASIA H`, `PDH`, `ORB MID`), placed consistently at the **right edge** of their line, using reasonable fixed offsets between categories where practical (e.g., session labels and PDH/PDL labels nudged to avoid the most common collision cases).
- Label visibility is controlled by **three category toggles only** (§12): Show session labels, Show PDH/PDL labels, Show hourly labels — not a separate toggle per box or line. A user on a small screen strips down to fewer categories, not fewer individual objects.
- **No automatic label-collision engine is built in V1.** The spec does not promise labels can never overlap under every chart scale and price condition — it is explicitly documented that tightly clustered price levels (e.g., ORB Low landing very close to PDL) can still visually converge, and that is an accepted V1 limitation, not a bug.
- Minimum line width of 1px must remain visible at TradingView's mobile app default line rendering — no sub-pixel or "hairline" styles.
- Hourly labels default **off** (§8, §12) — with the category toggle off, the current-hour-plus-two-completed-hours default (§8) draws lines only, no labels, keeping it quiet on a phone-sized chart by default.
- No dashboard/table overlay (`table.new`) is part of V1 — that's exactly the kind of dense panel that reads badly on mobile and isn't needed for a pure levels map.

---

## 12. User-configurable settings

**Approved (2026-07-19), corrected to match §3/§6/§8/§11.** Grouped, matching the existing project's input-grouping convention (`group=` parameter, as used in `nova_execution_v1.pine`):

**Group: Session Visibility**
- Show Asia (bool, default true)
- Show London (bool, default true)
- Show ORB (bool, default true)
- Show Hourly High/Low (bool, default true)
- Show PDH/PDL (bool, default true)

**Group: ORB**
- Show ORB midpoint (bool, default false) — §7

**Group: History**
- Completed sessions to retain (int, default 3, min 1, max 5) — per session type, see §6
- Completed hourly ranges to retain (int, default 2, min 1, max 3) — see §8

**Group: Labels**
- Show session labels (bool, default true)
- Show PDH/PDL labels (bool, default true)
- Show hourly labels (bool, default false) — see §8, §11
- Label size (string: Small/Normal/Large)

**Group: Style**
- Reasonable color controls per level family: Asia, London, ORB, ORB Midpoint, PDH/PDL, Hourly — one `input.color` each, defaults per §10
- Line width control for session/ORB levels and for PDH/PDL and Hourly lines, per §10's defaults
- Box fill transparency control for the three session box types

V1 deliberately does **not** provide a separate setting for every individual drawn object (no per-instance color, no per-retained-history-slot toggle) — control is at the level-family/category granularity described above, consistent with the label-complexity correction in §11. No input controls anything about trading behavior, alerts, or strategy — every input listed above is purely visual/display scope, consistent with §1's non-purpose list.

---

## 13. Object-limit and performance safeguards

Pine enforces hard per-indicator limits on drawn objects. `nova_execution_v1.pine` declares `max_lines_count=500, max_labels_count=500, max_boxes_count=200, max_bars_back=2000` for a much heavier, multi-feature dashboard indicator. Market Map V1 draws a small, bounded number of objects by design (§6, §8 retention limits), so it should declare much lower, tighter limits as a defensive measure — if the object count ever unexpectedly exceeds the declared cap, Pine throws a runtime error rather than silently misrendering, which is the correct failure mode for a "keep it simple" tool.

**Recomputed for the corrected retention depths (2026-07-19):** worst case at maximum settings — 3 session types (Asia/London/ORB) × up to 6 instances each (5 retained completed + 1 live, at the max `sessionsToKeep` setting) = up to 18 boxes and up to 36 boundary lines, plus up to 4 hourly line pairs (8 lines) at the max hourly-retention setting, plus 2 PDH/PDL lines, plus 1 optional ORB midpoint line, plus a modest label budget per the three label categories (§11/§12). The declared limits below give comfortable headroom above the *default*-settings case (3 retained + 1 live = 12 boxes, 24 session lines) while still catching genuine runaway-object bugs at the configured maximums:

```
//@version=6
indicator("Market Map V1", overlay=true, max_lines_count=100, max_labels_count=60, max_boxes_count=30, max_bars_back=2000)
```

Object lifecycle rule: every level type owns a small, fixed set of object-ID variables (arrays of `box`/`line` IDs sized to the configured retention depth, e.g. `var box[] asiaBoxes`) that are updated in place or explicitly deleted (`box.delete()`, `line.delete()`) and recreated on rollover — never accumulated without bound. No level type may create a new object every bar without deleting the oldest one once its retention slot is full.

---

## 14. Behavior across NQ and MNQ

Market Map V1 must be **symbol-agnostic** — it reads only OHLC price action from whatever chart it is applied to (`high`, `low`, `open`, `close`, `time`) and contains no hardcoded ticker, tick size, contract multiplier, or point-value logic. NQ and MNQ (and, incidentally, ES/MES or any other instrument) render structurally identically — same boxes, same lines, same behavior — with values simply reflecting whatever price series is on screen. No special-casing by symbol is required or permitted.

---

## 15. Behavior across chart timeframes

**Approved (2026-07-19), corrected — tighter supported range.** The original draft's "session boxes render normally up to 1H" was not safe: an 08:30 ET ORB boundary cannot always be reconstructed accurately from coarse bars without lower-timeframe aggregation, which V1 explicitly does not build (see below). Market Map V1 is primarily designed for Pedro's intraday charting, not as a general-purpose any-timeframe tool.

**Accepted V1 support, final:**

- **Full session boxes (Asia/London/ORB) and Hourly High/Low lines** render on **1m, 3m, 5m, and 15m** charts only — this is the supported precision range for session-window calculations in V1.
- **PDH/PDL** render on all intraday timeframes (1m through, and including, 15m and beyond up to 1D — see §3, unaffected by the session-precision limit since it reads a single daily candle, not an intraday accumulation).
- **Automatic suppression:** session boxes and hourly levels auto-suppress above 15m (on 30m, 1H, 4H, Daily, etc. charts) — the indicator does not attempt to draw them at all on those timeframes, rather than drawing something inaccurate.
- **No fake or partially reconstructed session ranges are ever shown.** If a timeframe is too coarse to compute a session window accurately, V1 shows nothing for that level type rather than an approximation.
- **No lower-timeframe reconstruction (e.g., `request.security` calls to a finer resolution to rebuild an accurate session range on a coarse chart) is introduced in V1**, even though that is technically how such reconstruction would be done — it is explicitly out of scope, to keep V1 simple and matched to Pedro's actual intraday charting use.

This replaces the original draft's 4H-cutoff proposal entirely — 15m is the new, final cutoff, and it is treated as resolved rather than open.

---

## 16. Daylight-saving-time handling

Because every session boundary is computed using Pine's timezone-aware time functions against the `"America/New_York"` timezone string (§2) rather than a fixed UTC offset, DST transitions are handled automatically by the TradingView platform — the same Pine code produces correctly-placed boxes and lines at the 08:30–09:30 ET ORB window (and every other level's window) on both sides of a DST changeover, with zero special-case code. This is standard, well-documented Pine behavior, not new logic being introduced by this spec; it's called out explicitly so it's a known, verified property rather than an untested assumption. Acceptance testing (§17) includes an explicit check across a DST transition weekend.

---

## 17. Acceptance criteria and visual test cases

**Approved (2026-07-19), corrected to match §3, §6, §8, §11, §15.** Before Phase 1 coding begins, Pedro reviews a static visual mock of the approved-direction style table (§10) — colors, line styles, label placement — against a real chart screenshot, the same way UI mockups are reviewed elsewhere in this project. No Pine is written until that mock is approved.

Once implementation begins, each phase (§19) ends with a manual visual check against these cases:

1. **Live formation across supported timeframes** — apply to an NQ (or MNQ) chart on 1m, 5m, and 15m; confirm session/ORB/hourly levels form and grow correctly on all three.
2. **Suppression above 15m** — confirm session boxes and hourly levels auto-suppress (draw nothing, not an approximation) on 30m, 1H, 4H, and Daily charts, per §15.
3. **PDH/PDL accuracy** — confirm the drawn Previous Day High/Low lines exactly match the previous **completed exchange daily futures candle** read directly off the daily chart, per the corrected §3 definition.
4. **Retention depth** — confirm the default of **3 retained completed sessions per type** (plus the live-forming instance) displays correctly, with older instances visibly faded relative to the most recent completed one, per §6.
5. **Line termination at 16:00 ET** — confirm Asia/London/ORB boundary lines stop extending at 16:00 ET on their associated NY trading day rather than continuing indefinitely or into the next overnight session, per §5.
6. **Hourly lines, not boxes** — confirm Hourly High/Low renders as thin line pairs only, with no box or fill of any kind, per §8.
7. **Default hourly state** — confirm the out-of-the-box default shows the live current hour plus the 2 most recently completed hourly pairs (3 pairs total), per §8/§12.
8. **No repainting or lookahead in PDH/PDL** — confirm the `request.security` call for PDH/PDL never uses lookahead and the displayed values never shift after the fact on historical bars, per §3.
9. **No stale objects after toggles or retention rollover** — toggle every input off and on, and let retention rollover happen naturally (new session/hour completing); confirm no orphaned or duplicate objects remain and no runtime object-limit errors occur, per §13.
10. **DST alignment** — load historical data spanning a DST transition weekend; confirm every level type stays aligned to correct ET wall-clock times before and after, per §16.
11. **NQ/MNQ consistency** — apply identical settings to NQ, then MNQ (ES/MES as a bonus check); confirm structurally identical rendering, per §14.
12. **Mobile readability without over-promising** — open the chart in the TradingView mobile app; confirm labels are legible and lines remain visible at default rendering, while accepting (not treating as a failure) that tightly clustered levels may still visually converge, per the corrected §11.

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

**Approved (2026-07-19), corrected to match §5, §6, §8, §15, §17.** Each phase is small, produces something Pedro can look at on a real chart, and requires his go-ahead before the next phase starts. No phase begins without approval of the previous one's visual check.

| Phase | Scope | Visual check |
|---|---|---|
| 0 | Style mock review (§10, §17) — no code | Pedro approves the color/line/label direction or sends back changes |
| 1 | Skeleton indicator: `//@version=6 indicator(...)` declaration, object-limit safeguards (§13), Previous Day High/Low only (simplest level, no session-window logic; correct exchange-daily-candle definition per §3) | PDH/PDL lines appear correctly on a live NQ chart, on 1m/5m/15m |
| 2 | ORB box + High/Low lines, live-growing and locking at 09:30 ET, extending only through 16:00 ET per §5/§7 | ORB box forms correctly during a live or replayed 08:30–09:30 ET window; boundary lines stop at 16:00 ET |
| 3 | ORB optional midpoint toggle | Midpoint line appears only when enabled, styled distinctly from boundary lines |
| 4 | Asia session box + High/Low, 16:00 ET line termination | Asia box forms across the correct overnight ET window |
| 5 | London session box + High/Low | London box forms correctly, including the transition boundary into ORB |
| 6 | Hourly High/Low as **lines only** (no box), rolling retention default 2 completed + live current (§8) | Hourly line pairs roll off correctly; default state shows current + 2 completed, no box or fill anywhere |
| 7 | Session history retention (§6: default 3 completed per type, 1–5 configurable, older instances faded) + full settings/inputs panel (§12) | Retention depth and fading render correctly at default and at min/max settings; every toggle/color/width input works as documented; no orphaned objects when toggled off |
| 8 | Timeframe precision range 1m–15m + auto-suppression above 15m (§15) + DST verification (§16) + full acceptance pass (§17, all 12 cases) | All twelve acceptance cases pass; Pedro signs off on V1 as complete |

No phase after 0 begins implementation without this specification being approved first, and no phase after its own number begins without that phase's visual check being explicitly approved by Pedro.

---

## Final resolved decisions (2026-07-19)

All seven items originally listed as open in the first draft are now resolved:

1. **§2** — ET-anchoring for all session windows, regardless of viewer timezone. **Approved.**
2. **§3** — PDH/PDL definition: previous **completed exchange-defined daily futures candle**, not a custom ET-midnight aggregation. **Approved, corrected.**
3. **§4** — Live-growing boxes/levels for all windowed types. **Approved.**
4. **§6** — Retention depth: **3 completed instances per session type by default (1–5 configurable), older instances faded**, not single-most-recent. **Approved, corrected.**
5. **§8** — Hourly High/Low is **lines only, no boxes**; retention default **2 completed + live current (1–3 configurable)**, not a box-based N-up-to-6 scope. **Approved, corrected.**
6. **§15** — Timeframe support: **full session/hourly precision on 1m/3m/5m/15m only, auto-suppressed above 15m**; PDH/PDL works on all intraday timeframes. **Approved, corrected** (replaces the original 4H-cutoff proposal).
7. **§5** (added during correction) — Session boundary lines extend only **through 16:00 ET**, not indefinitely until the next occurrence. **Approved, corrected.**

## Still pending Pedro's visual approval

Only one item remains open, and it is a visual-design step, not a behavioral one:

- **§10** — The approved-direction color/line-style/label table (purple Asia, blue London, amber/orange ORB more prominent, neutral dashed PDH/PDL, dim teal dotted Hourly, dim amber dotted ORB midpoint, transparent subtle session fills, compact right-edge labels) sets the palette *direction* Pedro confirmed, but exact hex values, precise transparency percentages, and final label text are not yet locked. This is resolved at **Phase 0** (§19) — a rendered mock against a real chart screenshot, reviewed and approved before any Pine is written.

Nothing in this document authorizes Pine implementation. Phase 0 (style mock review) is the very next step, and only after Pedro separately approves that mock.
