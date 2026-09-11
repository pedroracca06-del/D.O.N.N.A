# NOVA EXECUTION V1 — Phase 2: Canonical BUY/SELL Chart Markers

**Status:** Implemented in `indicators/nova_execution_v1.pine` only. The live TradingView cloud script was not touched — no `pine new`/`set`/`save`/`compile` or any CDP write action was run against it. Verification used only TradingView's stateless server-side compile-check endpoint (a plain HTTPS POST with a throwaway Guest credential, no connection to the live Desktop app or account).

## Problem this closes

Per the original audit (`INDICATOR_SIGNAL_REJECTION_AUDIT.md`, root cause #4), the script had zero `plotshape()`/`plotchar()`/`plotarrow()` calls anywhere in its tracked history — no BUY/SELL chart marker ever existed to restore. Phase 2 builds this new, wired to the canonical signal state Phase 1 established.

## Exact marker booleans

Marker source of truth — no new, independently-computed signal boolean was created:

```pine
canonicalBuyNew  = canonicalBuy  and not canonicalBuy[1]
canonicalSellNew = canonicalSell and not canonicalSell[1]
```

`canonicalBuy`/`canonicalSell` are Phase 1's canonical variables (unchanged, still wrapping `buySignal`/`sellSignal`). `canonicalBuyNew`/`canonicalSellNew` are a pure rising-edge filter over them — added directly beside the Phase 1 canonical block (`indicators/nova_execution_v1.pine`, right after the existing `canonicalBuy`/`canonicalSell` lines).

## Exact plotting calls

```pine
plotshape(showSignals and canonicalBuyNew,
     title="NOVA BUY", style=shape.labelup, location=location.belowbar,
     color=color.new(color.lime, 0), text="BUY", textcolor=color.black,
     size=signalLabelSize)

plotshape(showSignals and canonicalSellNew,
     title="NOVA SELL", style=shape.labeldown, location=location.abovebar,
     color=color.new(color.red, 0), text="SELL", textcolor=color.white,
     size=signalLabelSize)

if showSignals and showSignalContext and canonicalBuyNew
    label.new(bar_index, low - atrValue * 1.5, canonicalMarkerContextText,
         style=label.style_label_up, color=color.new(color.lime, 80),
         textcolor=color.lime, size=signalLabelSize)

if showSignals and showSignalContext and canonicalSellNew
    label.new(bar_index, high + atrValue * 1.5, canonicalMarkerContextText,
         style=label.style_label_down, color=color.new(color.red, 80),
         textcolor=color.red, size=signalLabelSize)
```

- `plotshape()` carries the BUY/SELL word itself (`shape.labelup`/`shape.labeldown` render a filled label with the given `text`), placed below/above the bar per the requirement. Color is fully opaque (0% transparency) for both — not transparent, readable against dark or light chart backgrounds.
- `label.new()` is used only for the optional strategy/liquidity-source context line, gated separately by `showSignalContext`, positioned an ATR-scaled distance beyond the primary marker (`atrValue * 1.5`, using the existing `atrValue` purely for visual spacing — no new calculation logic) so the two objects don't overlap.
- Context text (`canonicalMarkerContextText`) maps existing `setup_type` values to readable strings (e.g. `ORB_MID_REJECT` → `"ORB MID REJECTION"`), and appends `canonicalLiquiditySource` as a second line when it's not `"NONE"` (currently only possible when `canonicalStrategy == "ORB"`, per Phase 1 scope).

**Known limitation, confirmed during implementation:** the "BUY / ORB BREAK & RETEST" example from the original request is not reachable today. `orbBuySignal` (which feeds `canonicalBuy`) is built from `orbBuyPass = orbPassMidRejectBull or orbPassLiqRejectBull or orbPassEdgeRejectBull` — the break-and-retest path (`orbValidBreakBull`/`orbValidBreakBear`, part of the separate, currently-unwired `orbLongSignal`/`orbShortSignal` variables) is not one of `orbBuyPass`'s inputs. Wiring it in would change ORB signal eligibility, which is explicitly out of scope for this phase. Documented here rather than silently worked around.

## Inputs added

| Input | Variable | Default | Notes |
|---|---|---|---|
| Show Signal Context (strategy/liquidity source) | `showSignalContext` | `true` | New |
| Signal Label Size | `signalLabelSizeInput` → `signalLabelSize` | `"Normal"` → `size.normal` | New; string input mapped to `size.small`/`size.normal`/`size.large` |
| Show Signals | `showSignals` | `true` | **Not new** — was declared at line 25 since before this file entered git history, but never referenced anywhere. Phase 2 wires it into the actual plotting gate (`showSignals and canonicalBuyNew`, etc.) instead of adding a duplicate input. |

## Duplicate suppression

Rising-edge guard (`canonicalBuy and not canonicalBuy[1]`) — exactly the condition specified in the Phase 2 request. `canonicalBuy`/`canonicalSell` can stay true for more than one consecutive bar depending on which underlying family fired; without the edge guard the marker/alert would reprint every bar the condition holds. With it, exactly one marker prints per rising edge, and the count resets only when the boolean returns to false first.

## Conflict handling

No new guard was added for `canonicalSignalConflict` — none is needed. Phase 1 already proved `canonicalBuy`/`canonicalSell` are both forced `false` whenever `canonicalSignalConflict` is true (they're defined as `buySignal and not canonicalSignalConflict` / `sellSignal and not canonicalSignalConflict`). Since `canonicalBuyNew`/`canonicalSellNew` are built directly from `canonicalBuy`/`canonicalSell`, a conflicted bar cannot produce a marker — verified by construction, not by an added runtime check.

## Alert mapping

```pine
alertcondition(canonicalBuyNew,  "NOVA BUY",  "NOVA canonical buy signal (ORB/ICT/PROS)")
alertcondition(canonicalSellNew, "NOVA SELL", "NOVA canonical sell signal (ORB/ICT/PROS)")
```

These are the same two canonical `alertcondition()` entries added in Phase 1 — updated in place to read `canonicalBuyNew`/`canonicalSellNew` instead of the raw (non-edge-guarded) `canonicalBuy`/`canonicalSell`, so the alert and the chart marker share exactly the same source and the same transition, and neither fires more than once per setup. The four legacy per-family alertconditions (`ORB BUY`, `ORB SELL`, `PROS BUY`, `PROS SELL`) are untouched. ICT remains covered only via the existing, untouched `alert()` JSON webhook block.

## Execution independence

Confirmed by code review: nothing in the Phase 2 addition references execution state, broker state, Auto Execute, paper/live mode, prop gates, dry-run mode, or execution path health — none of those concepts exist anywhere in this Pine script (Pine has no mechanism to read Python-side `services/execution.py` state at all). The marker fires purely from `canonicalBuyNew`/`canonicalSellNew`, which depend only on chart data and the existing, unmodified ORB/ICT/PROS evaluators.

## Visibility

- Both `plotshape()` colors are fully opaque (`color.new(..., 0)`).
- Size is configurable via `signalLabelSize` (Small/Normal/Large), default Normal — legible at both desktop and typical mobile zoom levels; the user can size up further if needed.
- BUY prints `location.belowbar` (below the qualifying candle); SELL prints `location.abovebar` (above it) — as required.
- Context labels use `bar_index`/price-relative `y` values (not fixed pixel offsets), so they scale with the chart's own coordinate system rather than risking an off-screen fixed position.
- No mobile-specific preset exists in this script (none did before Phase 2 either) — the same size/color settings apply on both platforms; there is nothing that hides markers specifically on mobile.
- Object limits: `max_labels_count=500` (declared at the top of the file, unchanged). Context labels are created without manual deletion/array bookkeeping — TradingView's built-in automatic recycling (oldest-first) applies once the count is exceeded, the same pattern already implicitly relied on elsewhere in the script for per-bar-created objects. Given the existing 20-bar cooldown (`canSmartBuy`/`canSmartSell`, unchanged) and the observed historical signal rate (roughly 15% of ~94 recent evaluation cycles produced any BUY/SELL per the audit's live-log sample), this is not expected to approach the cap in normal use.

## Confirmed unchanged

- No strategy, ORB, RP, PROS, or IB logic was modified.
- No threshold, grade, session gate, or instrument gate was modified — verified via `git diff`, which shows exactly four changed regions (new inputs, two new canonical edge variables, two updated `alertcondition()` lines, and the new marker-plotting block) and nothing else.
- `CMD`, `SYS_STATE`, and the Python parser (`engines/reasoning.py`) were not touched.
- No execution/broker file was modified — only `indicators/nova_execution_v1.pine` and this documentation file changed.
- RP still has no canonical path — `canonicalBuy`/`canonicalSell` remain scoped to ORB/ICT/PROS exactly as Phase 1 left them. RP identity is still Phase 3.

## Test results (reasoned against the committed code, TradingView compile-check confirmed 0 errors/0 warnings — no local Pine sandbox execution available)

| Case | Expected | Result |
|---|---|---|
| `canonicalBuy` rising edge | Exactly one BUY marker | Confirmed — `canonicalBuyNew` is true only on the bar `canonicalBuy` transitions false→true |
| `canonicalSell` rising edge | Exactly one SELL marker | Confirmed, mirrored |
| `canonicalSignalState == "WAIT"` | No marker | Confirmed — WAIT requires both `canonicalBuy` and `canonicalSell` false, so both `*New` flags are false |
| `canonicalSignalState == "HEADS_UP"` | No BUY/SELL marker | Confirmed, same reasoning |
| `canonicalSignalConflict == true` | No marker | Confirmed by construction (Phase 1 proof) |
| Execution disabled | Marker still displays | Confirmed — no execution-state reference exists in the added code |
| Marker vs. canonical alert | Same source | Confirmed — both read `canonicalBuyNew`/`canonicalSellNew` directly |
| Thresholds | Unchanged | Confirmed via `git diff` — zero changes outside the four new/edited regions |
| Strategy eligibility | Unchanged | Confirmed — `orbBuySignal`/`ictBuySignal`/`prosBuySignal`/`orbSellSignal`/`ictSellSignal`/`prosSellSignal` byte-identical to Phase 1 |
| Execution/broker files | Unchanged | Confirmed — only the Pine file and this doc changed this phase |
