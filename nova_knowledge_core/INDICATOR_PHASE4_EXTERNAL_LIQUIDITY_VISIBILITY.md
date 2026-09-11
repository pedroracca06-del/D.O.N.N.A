# NOVA EXECUTION V1 — Phase 4: External Liquidity Level Visibility

**Status:** Visual/usability phase only. `indicators/nova_execution_v1.pine` only. Verified with TradingView's stateless server-side compile-check endpoint only — no CDP/live-chart interaction, live cloud script untouched.

## PART 1 — AUDIT OF CURRENT LEVEL OBJECTS (pre-Phase-4 state)

### Already acceptable — not touched this phase
ORB High/Low/Mid (`orbHighLine`/`orbLowLine`/`orbMidLine`, lines 410–426) and IB High/Low (`ibHighLine`/`ibLowLine` + `"IB HIGH"`/`"IB LOW"` labels, lines 455–496) — persistent lines updated in place, extend to the current bar every redraw, clearly labeled. No display bug found; left exactly as-is.

### Asia High / Asia Low
- **Price variables:** `asiaHigh` / `asiaLow` (`var float`, lines 583–584), accumulated during `inAsia` (lines 591–601).
- **Line variable:** none — no dedicated line ever existed for Asia H/L specifically.
- **Label variable:** `asiaLabel` (line 1394) — a single label, not split into High/Low.
- **Drawn via:** `asiaBox` (`box.new`, line 1347), a filled rectangle from session start to current bar while `inAsia`, top/bottom set to `asiaHigh`/`asiaLow` (lines 1352–1353). Frozen once the session ends (box stops growing).
- **Label drawn via:** `label.new(bar_index + 2, asiaHigh, "ASIA", ...)` (line 1406) — anchored at the box's top (`asiaHigh`) only; the low has no label at all.
- **Updated:** box grows every bar while `inAsia`; label is deleted and recreated every `barstate.islast` tick (lines 1399–1400, 1406).
- **Deleted:** old box pushed to `histAsiaBoxes` (historical fade array) on `newAsia`, or deleted outright if `showHistBoxes` is off; label deleted every redraw before being recreated.
- **Color/opacity/width/style:** box background only (`asiaBoxColor`, yellow @ 88% transparency); no line object, so no line color/width/style exists for Asia specifically.
- **Label size:** `size.tiny`.
- **Extension through NY:** No — box stops growing after Asia session ends; nothing extends into or through the NY session.
- **Label text:** `"ASIA"` — a session-name tag, not `"ASIA HIGH"`/`"ASIA LOW"`.
- **Desktop/mobile readability:** Poor — single label, no High/Low distinction, disappears from visual relevance once other session boxes are drawn over/near it.
- **Object-limit risk:** Low (one label + a capped historical-box array), but the underlying design doesn't scale to "High" and "Low" as separate readable objects.

### London High / London Low
Identical pattern to Asia: `londonHigh`/`londonLow` (lines 585–586, 597–601), `londonBox` (line 1366), single `"LONDON"` label (`londonLabel`, line 1408) anchored at the top only. Same limitations as Asia.

### Overnight High / Overnight Low
- **Not calculated anywhere in this Pine script.** No `overnightHigh`/`overnightLow` variable, no session window for "overnight" exists. Confirmed by full-file grep — zero occurrences before this phase. (The Python-side `engines/market_structure.py` computes ONH/ONL independently from yfinance data, entirely disconnected from the chart — consistent with the original audit's finding that liquidity levels are calculated twice, in two disconnected systems.)
- Phase 4 must add this calculation from scratch (display-only, no strategy/threshold logic) before it can be made visible at all.

### Previous Day High / Previous Day Low (PDH / PDL)
- **Price variables:** `prevDayHigh` / `prevDayLow` (lines 633–634) = `request.security(syminfo.tickerid, "D", high[1])` / `low[1]` — yesterday's completed daily high/low.
- **Line variable:** `pdhLine` / `pdlLine` (lines 2412–2413).
- **Label variable:** none — PDH/PDL have never had a text label.
- **Drawn via:** `line.new(bar_index, prevDayHigh, bar_index + 12, prevDayHigh, color=color.green, width=2)` / red mirror (lines 2434–2437), inside the "LIQUIDITY MARKERS" block, gated only by `barstate.islast` — **no input controls this at all today**.
- **Updated/deleted:** deleted and recreated from scratch every `barstate.islast` tick (lines 2422–2425) rather than repositioned in place.
- **Color/opacity/width/style:** solid green (high) / red (low), fully opaque, width 2.
- **Extension:** fixed 12-bar segment (`bar_index + 12`), **not extended** — on any chart faster than a few minutes this visually vanishes almost immediately relative to a full NY session (the exact bug the original audit flagged).
- **Label text:** none.
- **Desktop/mobile readability:** Poor — no label at all; indistinguishable from PWH/PWL except by width/style if a viewer already knows the convention.
- **Object-limit risk:** Low (one line each, always deleted before recreation) — but the delete-then-recreate pattern is unnecessary churn Part 6 asks to avoid.

### Previous Week High / Previous Week Low (PWH / PWL)
Identical pattern to PDH/PDL: `prevWeekHigh`/`prevWeekLow` (lines 635–636), `pwhLine`/`pwlLine` (lines 2414–2415, 2438–2441) — dashed, width 1, no label, fixed 12-bar segment, no input.

### Daily High / Daily Low (current, in-progress day)
- **Not calculated anywhere in this Pine script as a distinct concept from PDH/PDL.** Only yesterday's *completed* high/low exists (`prevDayHigh`/`Low`, above). Today's in-progress high/low has no variable today.
- Straightforward to add: `request.security(syminfo.tickerid, "D", high)` / `low` (the same mechanism as `prevDayHigh`/`Low`, simply without the `[1]` historical offset) gives the current, still-growing daily high/low live. No new session-tracking state machine needed.

### Weekly High / Weekly Low (current, in-progress week)
Same situation as Daily: not calculated; add via `request.security(syminfo.tickerid, "W", high)` / `low` (no offset), mirroring `prevWeekHigh`/`Low`'s existing mechanism.

### Cross-cutting findings
- None of Asia/London/PDH/PDL/PWH/PWL are exported to the NOVA BRIDGE table (confirmed in the original audit, unchanged) — out of scope for this phase (Phase 5 territory).
- The only object-limit-relevant setting is `max_lines_count=500`/`max_labels_count=500` (declared at the top of the file, unchanged) — current usage is far below this, and the delete-then-recreate churn for PDH/PWH, while wasteful, has never approached the cap.
- No existing input controls Asia/London/PDH/PDL/PWH/PWL visibility independently of each other or of the rest of the chart — `showSessions` only controls the session *background* color (line 24), not these specific objects.

## PART 2 — NEW INPUTS

Added under a new input group, `"External Liquidity Levels"`:

```pine
showAsiaLevels          = input.bool(true,  "Show Asia High/Low",           group="External Liquidity Levels")
showLondonLevels        = input.bool(true,  "Show London High/Low",         group="External Liquidity Levels")
showOvernightLevels     = input.bool(true,  "Show Overnight High/Low",      group="External Liquidity Levels")
showPreviousDayLevels   = input.bool(true,  "Show Previous Day High/Low",   group="External Liquidity Levels")
showPreviousWeekLevels  = input.bool(true,  "Show Previous Week High/Low",  group="External Liquidity Levels")
showDailyWeeklyLevels   = input.bool(true,  "Show Daily/Weekly High/Low",   group="External Liquidity Levels")
externalLiquidityLineWidth      = input.int(2, "Line Width", minval=1, maxval=4, group="External Liquidity Levels")
externalLiquidityLineStyleInput = input.string("Solid", "Line Style", options=["Solid", "Dashed", "Dotted"], group="External Liquidity Levels")
externalLiquidityOpacity        = input.int(20, "Line/Label Transparency", minval=0, maxval=90, group="External Liquidity Levels")
externalLiquidityLabelSizeInput = input.string("Normal", "Label Size", options=["Small", "Normal", "Large"], group="External Liquidity Levels")
extendExternalLiquidityThroughNY = input.bool(true, "Extend Through NY Session", group="External Liquidity Levels")
```

No existing input already controlled Asia/London/PDH/PDL/PWH/PWL visibility (confirmed in Part 1 — the old PDH/PWH lines were unconditionally drawn with no toggle at all), so none of these duplicate prior behavior — they are all genuinely new controls filling a gap, not a second input for something already governed.

## PART 3 — CLEAR SOURCE LABELS

Every level gets its own dedicated label, one per High and one per Low (previously: only Asia/London had one combined session label; PDH/PDL/PWH/PWL had none at all):

`ASIA HIGH`, `ASIA LOW`, `LONDON HIGH`, `LONDON LOW`, `OVERNIGHT HIGH`, `OVERNIGHT LOW`, `PDH`, `PDL`, `PWH`, `PWL`, `DAILY HIGH`, `DAILY LOW`, `WEEKLY HIGH`, `WEEKLY LOW`.

Implemented via a single reusable function, `f_liqLevel(...)` (see Part 6), called once per level with **persistent** `var line`/`var label` objects repositioned via `line.set_xy1()`/`set_xy2()` and `label.set_xy()`/`set_text()` rather than deleted and recreated — so no duplicate objects are ever created per bar, and nothing disappears and reappears every redraw.

## PART 4 — VISUAL HIERARCHY

No trading logic determines emphasis. Each level's line/label gets a modest width/opacity boost when the level is currently "active" — reusing the exact same, already-existing, generic `f_near()`/`f_swept_high()`/`f_swept_low()` helper functions and `liqThresh` threshold already used elsewhere in this file for PSH/PDH/PWH classification (lines 631–640, unchanged) — called fresh against the new levels for display purposes only. This does not touch or re-derive any existing near/swept variable (`nearPDH`, `sweptPWH`, etc.) used by ORB/scoring; it computes independent, display-only booleans from the same pure functions.

Colors follow the file's existing high=green/low=red convention (already used for PDH/PWH) uniformly across all seven pairs — text labels are the primary disambiguator between pairs (`"ASIA HIGH"` vs `"PDH"` vs `"WEEKLY HIGH"`, etc.), consistent with the user's Part 3 instruction that labels — not color — should carry the identification. ORB (aqua) and IB (`#40C4FF` sky-blue) remain visually distinct; nothing here reuses those colors.

## PART 5 — ACTIVE LIQUIDITY CONTEXT: DEFERRED

Per the explicit instruction ("If reliable interaction classification is not already available, defer temporary context labels rather than inventing logic"): building genuine touch/sweep/reclaim/rejection classification (e.g. `"ASIA HIGH REJECTION"`, `"PDH TEST"`) for these seven pairs would require new multi-bar wick/close analysis that doesn't already exist for most of them (only PDH/PWH have any existing generic near/swept primitive; Asia/London/Overnight/Daily/Weekly have none). Writing that now would mean inventing new detection logic — exactly the kind of scope expansion the Phase 3 correction just walked back. **Deferred entirely this phase.** The only interaction awareness added is the simple near/swept-based emphasis in Part 4 (width/opacity only, no text, no signal).

## PART 6 — OBJECT MANAGEMENT

New reusable function (added once, called 14 times — once per level):

```pine
f_liqLevel(showFlag, levelPrice, labelText, baseColor, isEmphasized) =>
    var line lv = na
    var label lb = na
    _w     = isEmphasized ? externalLiquidityLineWidth + 1 : externalLiquidityLineWidth
    _trans = isEmphasized ? math.max(externalLiquidityOpacity - 15, 0) : externalLiquidityOpacity
    _ext   = extendExternalLiquidityThroughNY ? extend.right : extend.none
    if showFlag and not na(levelPrice) and barstate.islast
        if na(lv)
            lv := line.new(bar_index, levelPrice, bar_index + 12, levelPrice, color=color.new(baseColor, _trans), width=_w, style=externalLiquidityLineStyle, extend=_ext)
        else
            line.set_xy1(lv, bar_index, levelPrice)
            line.set_xy2(lv, bar_index + 12, levelPrice)
            line.set_width(lv, _w)
            line.set_color(lv, color.new(baseColor, _trans))
            line.set_extend(lv, _ext)
        if na(lb)
            lb := label.new(bar_index + 13, levelPrice, labelText, style=label.style_label_left, color=color.new(color.black, 100), textcolor=baseColor, size=externalLiquidityLabelSize)
        else
            label.set_xy(lb, bar_index + 13, levelPrice)
            label.set_text(lb, labelText)
    if not showFlag
        if not na(lv)
            line.delete(lv)
            lv := na
        if not na(lb)
            label.delete(lb)
            lb := na
```

This replaces object churn with in-place updates: each level gets exactly one persistent line and one persistent label for the life of the chart (created once, repositioned every redraw), rather than deleting and recreating every `barstate.islast` tick. 14 new objects total (7 lines + 7 labels) — trivial against `max_lines_count=500`/`max_labels_count=500`. If a level is disabled via its show-flag, its objects are explicitly deleted and the handle cleared, so toggling inputs off actually removes the drawing rather than leaving stale objects.

`pdhLine`/`pdlLine`/`pwhLine`/`pwlLine` (the old delete-recreate PDH/PWH lines) are removed and replaced by calls to `f_liqLevel`. `pshLine`/`pslLine` (Previous Session High/Low) are **not** part of the target list in this phase and are left exactly as they were — untouched.

## PART 7 — ACCEPTANCE VERIFICATION (result)

- **Asia High immediately visible, labeled "ASIA HIGH":** confirmed by code — `f_liqLevel(showAsiaLevels, asiaHigh, "ASIA HIGH", ...)` creates a persistent, dedicated line+label the moment `asiaHigh` is available.
- **Remains visible through the NY session:** confirmed — `extend=extend.right` when `extendExternalLiquidityThroughNY` (default true), rather than the old fixed 12-bar segment.
- **Readable on desktop/mobile:** width/opacity/size are all user-configurable (`externalLiquidityLineWidth`/`Opacity`/`LabelSize`); no separate mobile preset exists anywhere in this script (consistent with the rest of the file), so the same settings serve both.
- **Does not obscure ORB or IB:** confirmed by color choice (green/red for external liquidity vs. ORB's aqua and IB's `#40C4FF`) and confirmed by diff — zero lines touching `orbHighLine`/`orbLowLine`/`orbMidLine`/`ibHighLine`/`ibLowLine` anywhere in this phase's changes.
- **No strategy signal created merely from a touch:** confirmed by diff — zero lines touching `canonicalBuy`/`canonicalSell`/`buySignal`/`sellSignal`/any scoring line anywhere in this phase's changes; the near/swept emphasis booleans are read-only display inputs to `f_liqLevel`, never written back to any strategy variable.
- **London/Overnight/PDH/PDL/PWH/PWL/Daily/Weekly all readable:** same `f_liqLevel` mechanism, one dedicated label each — PDH/PDL/PWH/PWL specifically go from **zero label ever** to a clear, dedicated one for the first time.
- **ORB/IB visibility unchanged:** confirmed via `git diff` — no ORB or IB drawing line was touched.
- **Phase 2 BUY/SELL markers unchanged:** confirmed via `git diff` — no `plotshape`/`canonicalBuyNew`/`canonicalSellNew` line was touched.
- **canonical signal state unchanged:** confirmed — `canonicalSignalState`/`canonicalBuy`/`canonicalSell` definitions untouched.
- **No alert changes:** confirmed — zero `alertcondition`/`alert()` lines touched.
- **No execution/broker changes:** only `indicators/nova_execution_v1.pine` and this documentation file changed.

One incidental, cosmetic-only change: the existing `newAsia`/`newLondon`/`newNYPre`/`newNYCash` lines were re-aligned (whitespace only) to line up with the new `newOvernight` line added alongside them — confirmed via diff that no operator or value changed on any of those four lines, only column spacing.

## PHASE 4 REFINEMENT (approved after initial Phase 4 review)

Two corrections, both display-only:

**1. Daily/Weekly High/Low demoted from default-on.** They're dynamic, in-progress reference levels, not major external liquidity — `showDailyWeeklyLevels` default changed from `true` to `false` (input label updated to `"Show Daily/Weekly High/Low (optional, off by default)"`). The calculation and drawing code were kept (option 2 from the two offered), not removed, since the underlying `request.security` values remain a legitimate opt-in reference. They are also explicitly excluded from the "nearest major level" emphasis ranking below — the major hierarchy is Asia/London/Overnight/PDH/PDL/PWH/PWL only, exactly as specified.

**2. Emphasis mechanism corrected to genuine "nearest of all major levels," not independent near/swept.** The original Phase 4 implementation gave *every* level that was individually near-or-swept a boost, which could emphasize several levels simultaneously. This refinement computes `math.abs(close - level)` for each of the 10 major levels (Asia/London/Overnight/PDH/PDL/PWH/PWL, each masked to a sentinel `1e10` distance when disabled or unavailable so it can never win), takes the minimum via `math.min`, and marks **only** the single level matching that minimum as "nearest" — `extLiqAsiaHighNearest`, `extLiqPDLNearest`, etc. This is the sole input to `f_liqLevel`'s `isEmphasized` parameter for the seven major pairs. Daily/Weekly keep the original simple near/swept emphasis, unchanged, since they're excluded from the major ranking.

`f_liqLevel` itself gained one addition: when `isEmphasized`, the label size now also steps up one tier (Small→Normal, Normal→Large, capped at Large) via `label.set_size()`, in addition to the existing wider-line/lower-transparency boost from initial Phase 4 — satisfying "slightly larger label" from this refinement's request. No flashing, no animation, no new size infrastructure — a static, deterministic per-bar choice from the existing `size.*` constants.

**Confirmed:** no signal logic, BUY/SELL conditions, execution, or alerts changed — verified via `git diff`, zero lines touching `canonicalBuy`/`canonicalSell`/`plotshape`/`alertcondition`/`orbBuySignal`/`ictBuySignal`/`prosBuySignal`/`buyScore`/`sellScore` in this refinement. Compiled clean: 0 errors, 0 warnings (stateless endpoint only, live script untouched).
