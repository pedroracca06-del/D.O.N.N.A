# NOVA Replay — Real-Session Validation Checklist

Run this checklist after the first real monitor cycle produces a decision snapshot.
One tick per item. Flag anything that doesn't match expected behavior.

---

## Pre-check: confirm a real decision snapshot exists

```
GET /api/mcp-replay/decisions?limit=1
```
Expected: array with at least one record where `snapshot_type = decision` and `decision_id` starts with `DEC_`.
If empty: monitor has not run yet. Wait for a cycle.

---

## 1. Tab loads without errors

- [ ] Click NOVA REPLAY tab in dashboard topbar
- [ ] No JS console errors (open DevTools → Console)
- [ ] Page renders without blank white screen
- [ ] Panels visible: Latest Decision Card, Similar Setups, Recent Decisions Table

---

## 2. Latest Decision Card fills with real data

- [ ] Card is not showing "No replay data yet" or "Click REFRESH to load"
- [ ] `symbol` shows the actual instrument (e.g. CME_MINI:MES1!)
- [ ] `session` shows a real session label (e.g. NY_CASH, NY_OPEN)
- [ ] `timestamp` shows a real UTC timestamp from today's session
- [ ] `decision_id` shows `DEC_YYYYMMDD_HHMM_XXXXXX` format

---

## 3. Section A — What NOVA Saw

Verify each field shows a real value (not all `—`):

- [ ] Session (e.g. NY_CASH)
- [ ] IB Status (e.g. COMPLETE, BUILDING)
- [ ] IB Draw (e.g. IB_H, IB_L, or null if not aligned)
- [ ] IB Aligned (Yes / No)
- [ ] ORB Active (Yes / No)
- [ ] ORB Phase (e.g. ORB_EXPIRED, ORB_ACTIVE, or `—` if no ORB data)
- [ ] PROS Active (Yes / No)
- [ ] PROS Phase (e.g. CONTINUATION, BUILDING, etc.)
- [ ] PROS OTE (e.g. TAGGED, DEEP, SHALLOW)
- [ ] PROS Cont (e.g. CONFIRMED, BUILDING)
- [ ] Peer Align (e.g. CONFIRM, DIVERGE)
- [ ] Draw Dir (e.g. UP, DOWN)
- [ ] MCP Status (e.g. HEALTHY, DEGRADED)
- [ ] MCP Conf (e.g. HIGH, MEDIUM, LOW)
- [ ] Parser (e.g. BRIDGE_V2, LEGACY)

---

## 4. Section B — What NOVA Decided

- [ ] Pre-Signal shows the deterministic classifier output (e.g. EXECUTION_READY, NO_TRADE)
- [ ] Final Signal matches signal_type in the table
- [ ] Setup Type is populated (e.g. PROS_CONT, ORB_EDGE)
- [ ] Direction is LONG or SHORT (with colour: green/red)
- [ ] Grade is populated if Claude was called (A / B / C / D)
- [ ] Rationale box shows Claude's reasoning text (or `—` if Claude was not called)
- [ ] Claude Called shows Yes / No correctly
- [ ] Exec Ready / Heads Up / Rejected flags match signal_type

---

## 5. Section C — What Happened

- [ ] trade_status is one of: NOT_TAKEN / REJECTED_OR_NO_TRADE / EXECUTION_READY_NOT_EXECUTED / TAKEN
- [ ] outcome is one of: WIN / LOSS / UNKNOWN / REJECTED
- [ ] match_method shows how the link was made (SIGNAL_TIMESTAMP_FUZZY / DATE_TICKER_DIR / TRACE_DATE_SYM / NONE)
- [ ] match_confidence shows HIGH / MEDIUM / LOW / NONE
- [ ] If match_confidence is LOW → low_confidence_note box is visible and says outcome is not confirmed
- [ ] If no match → outcome = UNKNOWN, match_method = NONE, no strong claims made

---

## 6. Review conclusion is conservative

- [ ] Conclusion chip is one of the valid labels:
  `GOOD_READ_GOOD_DECISION` / `GOOD_READ_BAD_DECISION` /
  `NO_TRADE_REVIEW_ONLY` / `NO_TRADE_CONFIRMED_CORRECT` /
  `MISSED_OPPORTUNITY` / `INSUFFICIENT_DATA`
- [ ] No skipped/rejected trade shows `NO_TRADE_CONFIRMED_CORRECT` unless match_confidence = HIGH + outcome = LOSS
- [ ] No LOW-confidence match produces a strong conclusion (must be INSUFFICIENT_DATA)
- [ ] Lesson note never says "correct" as a standalone claim for unconfirmed skips
- [ ] Lesson note always ends with a confidence qualifier if confidence is not HIGH
- [ ] **No `win_rate`, `avg_r`, or `expected_value` appears anywhere on the page**

---

## 7. Recent Decisions Table updates

- [ ] Table has at least one row after refresh
- [ ] Columns populate: Time, Symbol, Session, Setup, Signal, Dir, Grade, Parser, Parse, MCP, Conf, Exec?, Rej?, Status, Outcome, Match Conf, Conclusion
- [ ] Direction column is coloured (green for LONG, red for SHORT)
- [ ] Conclusion column shows coloured chip

---

## 8. Filters work

- [ ] Symbol filter: select MES or MNQ → table updates, no crash
- [ ] Conclusion filter: select INSUFFICIENT_DATA → table shows only those rows (or empty message)
- [ ] Confidence filter: select NONE → filters correctly
- [ ] Clearing a filter back to "All" restores full list
- [ ] Filters combine correctly (AND logic)

---

## 9. Similar Historical Setups

With only a few cycles, matches will likely be empty:

- [ ] Panel renders without crash
- [ ] If no matches: shows "No similar historical setups found yet. More cycles needed." safely
- [ ] If matches exist: each card shows SIM %, symbol, setup_type, direction, signal_type, outcome, outcome_note

---

## 10. No execution controls exist in replay tab

Visually confirm:
- [ ] No BUY / SELL buttons
- [ ] No EXECUTE button
- [ ] No position sizing inputs
- [ ] No override or lock controls
- [ ] No links to /api/execution or /api/broker endpoints

---

## 11. No mutation endpoints introduced

Check DevTools Network tab after clicking REFRESH:

- [ ] Only GET requests fired (no POST, PUT, PATCH, DELETE)
- [ ] URLs: `/api/mcp-replay/post-trade-reviews` and `/api/mcp-replay/similar-with-outcomes`
- [ ] No unexpected calls to journal, execution, or signal endpoints

---

## 12. No execution behavior changes

- [ ] Monitor still fires alerts normally (check Discord for any alerts during the session)
- [ ] Journal still records trades as before
- [ ] Execution trace still writes correctly
- [ ] State engine locks/counters behave normally

---

## Post-session notes

After completing the checklist, note any items that failed or looked unexpected here:

```
Date:
Session:
Decision snapshots generated:
Items failed:
Notes:
```

---

## Pass criteria

All 12 sections must be checked before considering the Replay Viewer validated.
Any section with a failed item: fix the replay UI only — do not touch strategy, execution, or governance logic.
