# PRIME Emotionless Validation Foundation

Status: foundation only — **no dataset, no result, no approval**
Phase: 2F (read-only intelligence work)
Authority: this document describes a research tool. It grants nothing.

---

## 1. What this is

`research/prime_validation/` is a standard-library-only, read-only Python
package that measures **pre-labeled, finalized historical PRIME candidates**. It
is the mechanical floor under the first rung of the validation ladder in
[`docs/claude-cowork/RESPONSIBILITY_CONTRACT.md`](claude-cowork/RESPONSIBILITY_CONTRACT.md)
§2.6 — nothing more.

"Emotionless" means one specific thing here: the package removes the human from
the *arithmetic*, not from the *judgement*. It does not decide what was a setup,
which model should have been taken, or whether any of it was good. Those remain
Pedro's, upstream, before a record ever reaches this code.

### 1.1 No dataset is included, and no profitability claim can be made

**There is no historical dataset in this repository, and this package ships
none.** Every record in the test suite is a synthetic fixture constructed inside
the test that uses it.

Consequently:

- **no win rate, expectancy, profit factor, or drawdown figure exists yet** for
  Strict OTE, 10AM Key Level Open, or ORB;
- **no profitability claim about PRIME can be made**, in any direction, from
  anything in this package today;
- the presence of a `profit_factor` field is not a result. It is a field.

When a dataset does arrive, it arrives under a separate approval, with its own
provenance, and the numbers it produces are still descriptive history — not a
forecast and not an authorization.

---

## 2. What it must never do

These are constraints on the code, not just on its current use. Extending the
package into any of them is out of scope and requires a separate owner-approved
system change:

| Prohibited | Why |
|---|---|
| Detect or infer a setup | Eligibility is an upstream human/approved-deterministic judgement. The engine reads `already_eligible`; it never computes it |
| Invent, tune, rank, or optimize a rule or parameter | That is strategy authority, and strategy authority is Pedro's |
| Assign model priority | The engine has no priority table. Preference is a **caller-supplied key**, written in the caller's own reviewable code |
| Grade or score | No A–D grades, no signal scores. Those are retired frameworks (`EXECUTION_MODELS.md`) |
| Execute, size dollars, or contact a broker or webhook | The trading subsystem is disabled. This package has no order path and no network access |
| Read or toggle a guarded flag | `NOVA_TRADING_SUBSYSTEM_ENABLED` and `NOVA_AUTO_EXECUTE` are untouched by this package; it reads no environment at all |
| Promote research into PRIME | Promotion is Pedro's explicit act. Research stays quarantined |

The package performs no file I/O, no network access, no environment reads, no
randomness, and no printing. A test enforces the import allowlist and the
absence of `open`/`eval`/`exec`/`print` calls, so drift shows up as a failure
rather than as a review miss.

---

## 3. The locked universe

Taken from `nova_knowledge_core/CURRENT/PRIME/EXECUTION_MODELS.md`, which is
Git-authoritative:

**Exactly three execution models.**

| Identifier | Doctrine name |
|---|---|
| `strict_ote` | Strict OTE |
| `10am_key_level_open` | 10AM Key Level Open |
| `orb` | ORB |

**Symbols:** `NQ`, `MNQ`. **Directions:** `long`, `short`.

- **FVG is confluence metadata only.** It is carried as a boolean
  (`fvg_confluence`) and is never an entry model. It does not affect R.
- **Standard deviation is a Strict-OTE companion read only.**
  `ote_standard_deviation_context` may only be populated when the model is
  `strict_ote`; attaching it to ORB or 10AM Key Level Open is rejected.
- **There is no fourth model**, and there is no legacy PROS logic, bounce /
  rejection framework, signal score, or Harvey grading anywhere in this package.
  A fourth entry in `PRIME_MODELS` would be an unapproved system change wearing
  a code change's clothes.

Model-specific timing gates (for example, ORB being the only approved model
before 09:45 ET per `RISK_AND_SESSION_RULES.md`) are **eligibility** questions
and therefore upstream of this package. It reads the eligibility flag and does
not re-litigate it.

---

## 4. Schema — `research/prime_validation/schema.py`

`ValidatedCandidate` is a frozen dataclass. Construction *is* validation: if an
instance exists, it passed every check. There is no partially valid record, no
repaired record, and no defaulted field.

### 4.1 Required fields

| Field | Rule |
|---|---|
| `candidate_id` | Non-empty, whitespace-clean, **unique** across the set |
| `model` | One of the three identifiers above |
| `symbol` | `NQ` or `MNQ` |
| `direction` | `long` or `short` |
| `candidate_timestamp_utc` | **Timezone-aware, UTC (zero offset)**. Naive or non-UTC is rejected |
| `session_date` | A plain `datetime.date` that **matches** the UTC timestamp's date |
| `source_id` | Non-empty, whitespace-clean dataset identity |
| `source_sha256` | **Exactly 64 lowercase hexadecimal characters** |
| `label_method` | `deterministic` or `human-confirmed` |
| `entry_price`, `exit_price` | **Strictly positive** finite real numbers. Zero and negative prices are rejected (`ENTRY_PRICE` / `EXIT_PRICE`) — a non-positive NQ/MNQ price is a corrupt row, even though R would still compute |
| `structural_risk_points` | **Strictly positive** finite real number |
| `already_eligible` | A real `bool` — `1`, `"true"`, and `"yes"` are rejected |
| `outcome` | Finalized: `W`, `L`, or `BE`. There is no pending state |
| `actual_trade_state` | `taken`, `missed`, `rule-deviation`, or `not-applicable` |

Optional: `fvg_confluence` (bool, default `False`) and
`ote_standard_deviation_context` (Strict OTE only).

### 4.2 Derived R

R is derived, never stored, and always direction-aware:

```
long   R = (exit_price - entry_price) / structural_risk_points
short  R = (entry_price - exit_price) / structural_risk_points
```

Structural risk is in **points**, taken from the structural invalidation the
model implies — not a tick offset and not a dollar amount. This package never
converts R to currency, because sizing is not its business.

### 4.3 Fail closed

Rejection is the default, and every rejection carries a stable machine-readable
`code`:

- **incomplete provenance** — a missing field, a missing source id, a hash that
  is not a lowercase SHA-256;
- **an unknown field** — a silently dropped column is indistinguishable from
  missing data, so the schema is closed;
- **an ambiguous instant** — a naive or non-UTC timestamp cannot be ordered
  against another instant, and unordered records cannot be split without
  leakage;
- **a session date that disagrees with its own timestamp**;
- **a label that contradicts its own prices** — a record marked `W` whose exit is
  adverse is a wrong row, and one wrong row poisons every downstream metric. `BE`
  means a scratch at the entry price; the tolerance
  (`BREAKEVEN_R_TOLERANCE = 1e-9`) absorbs binary floating point only and is not
  a policy band.

Set-level integrity (`find_integrity_issues`) additionally rejects:

- `DUPLICATE_CANDIDATE_ID` — one identity, one record;
- `MIXED_PROVENANCE` — one `source_id` carrying two different content hashes,
  which means two datasets are wearing one name;
- `DUPLICATE_OBSERVATION` — the same `(symbol, model, instant)` claimed by two
  identities, which is a double-counted event.

---

## 5. Splits — `research/prime_validation/splits.py`

Deterministic chronological partitions: `train`, `validation`, `out_of_sample`,
returned frozen.

- **Time is the only ordering.** No shuffle, no random seed, no stratification,
  no re-balancing. The ordering key is
  `(instant, session_date, symbol, model, candidate_id)`, which is total, so the
  same input always yields identical partitions regardless of input order.
- **Ratios** must be three strictly positive fractions summing to 1.0.
  `DEFAULT_RATIOS` is 0.6 / 0.2 / 0.2 — a default argument, not an approved
  methodology. The caller owns the choice and should state it.
- **Sizes** are floor-based and deterministic; every partition must hold at least
  one record, so fewer than five records at the default ratios is an
  `EMPTY_PARTITION` rejection rather than a silently degenerate split.
- **`as_of` is required** and declares the knowledge cutoff. It must be an
  explicit, timezone-aware UTC `datetime`. Omitting it or passing `None` is
  `AS_OF_REQUIRED`; a string, `date`, or epoch number is `AS_OF_TYPE`; a naive
  or non-UTC datetime is `TIMESTAMP_NAIVE` / `TIMESTAMP_NOT_UTC` on field
  `as_of`. The package never reads the wall clock: a cutoff taken from "now"
  would give the same input a different frozen split on a different day. Any
  record after the cutoff is `FUTURE_LEAKAGE`, and the split records the exact
  cutoff it was given. `assert_no_future_leakage` applies the same rule.
- **A boundary-straddling instant is rejected**, not absorbed. Because the input
  is already ordered, only an exact timestamp tie can cross a cut — nudging the
  boundary to swallow it would hide the fact that two records share an instant.
- Duplicate identity, mixed provenance, and duplicate observations all block
  partitioning outright: a contaminated set cannot be partitioned.

Nothing partial is ever returned. A rejected split returns no split.

---

## 6. Engine — `research/prime_validation/engine.py`

The engine does exactly one mechanical thing: given candidates already marked
eligible, it applies a **caller-supplied** deterministic key and records which
candidate that key selects in each session.

- **`selection_key` is mandatory and belongs to the caller.** It must return a
  tuple; the lowest tuple in a session wins. There is no default, and there is no
  fallback ordering, because a built-in default *is* the engine deciding a trade.
- **A non-eligible candidate is a rejection** (`NOT_ELIGIBLE`), not a candidate
  to evaluate. The engine detects nothing.
- **Keys see the decision, never the outcome** (§6.1). Both `selection_key` and
  `session_key` receive a `SelectionView`, not a `ValidatedCandidate`.
- **At most one selection per session.** `session_key` defaults to the view's
  `session_date` and is also the caller's to override (per symbol, for example). This
  mirrors the one-real-trade-per-day accountability rule in
  `RISK_AND_SESSION_RULES.md`, as an *observation* of that rule, not an
  enforcement of it.
- **An unresolved tie is an error** (`AMBIGUOUS_TIE`), naming the tied
  candidates. Two candidates the caller's key ranks equally must be resolved by
  extending the caller's key. The engine will not break a tie with a rule it had
  to invent. Mutually incomparable keys are likewise rejected.

### 6.1 Keys see a pre-decision view only

A selection key that can read the result can pick winners, and a backtest built
on that key measures hindsight instead of a decision. So the engine never hands
a caller callback the finalized record. For each call it builds a fresh, frozen,
slotted `SelectionView` holding exactly the fields knowable at the candidate
instant (`SELECTION_VIEW_FIELDS`):

`candidate_id`, `model`, `symbol`, `direction`, `candidate_timestamp_utc`,
`session_date`, `already_eligible`, `fvg_confluence`,
`ote_standard_deviation_context`.

The view does **not** contain `exit_price`, `outcome`, `r_multiple`,
`actual_trade_state`, or source/label provenance. It is a copy, not a wrapper:
it holds no reference to the candidate, has no `__dict__`, and has no property
or method that reaches one. The finalized `ValidatedCandidate` is joined back to
the evidence only after the key has run. `SelectionKeyFn` and `SessionKeyFn`
are typed over `SelectionView` accordingly.

The tests check this adversarially. Both callbacks get exactly one
`SelectionView`. Reading any of the four blocked fields raises. No field value
or direct referent is a candidate. And two datasets with identical setups but
opposite results select the same rows under the same keys.

**Limit, stated plainly:** this closes the ordinary attribute path. It is not an
in-process sandbox. A key that walks interpreter frames, or that closes over the
finalized records itself, is circumventing the boundary. That is a review
failure, not a supported use.

### 6.2 Everything returned is evidence

Each candidate gets a neutral label from the `(disposition, actual_trade_state)`
pair:

| | `taken` | `missed` | `rule-deviation` | `not-applicable` |
|---|---|---|---|---|
| **selected** | `selected_and_taken` | `selected_but_missed` | `selected_with_rule_deviation` | `selected_no_actual_trade` |
| **skipped** | `skipped_but_taken` | `skipped_and_missed` | `skipped_with_rule_deviation` | `skipped_no_actual_trade` |

These are descriptions, not verdicts. `skipped_but_taken` says the caller's key
would not have picked a candidate that was in fact traded. It does not say
either party was right, and `rule-deviation` is a factual state, not a
reprimand.

---

## 7. Metrics — `research/prime_validation/metrics.py`

Descriptive arithmetic over provenance-complete finalized records:
sample count, wins, losses, breakevens, win rate, expectancy R, profit factor,
maximum drawdown R, longest win and loss streak, and the 2R-or-better hit rate.

The design priority is **not being misleading**:

- **An empty sample returns `None` for every rate**, never `0.0`, with
  `data_state = "empty"`.
- **Zero-loss profit factor is `None`** with
  `profit_factor_state = "undefined_no_losses"` — never `inf`, never a
  flattering large number. A zero denominator is stated as a zero denominator.
- **A sample below the caller's declared `minimum_sample` withholds every rate**
  (`data_state = "below_minimum"`) rather than printing a confident-looking
  fraction of four trades. Raw observations — counts, streaks, drawdown — are
  still reported, because those are measurements rather than extrapolations.
- **`minimum_sample` defaults to `0`, which asserts no minimum**, and the report
  says so in its notes. The package does not invent a statistical-significance
  threshold; that is a methodology decision, and methodology is not Claude's.
- **Every report carries a note stating it is not a profitability claim.**
- **A breakeven ends a streak** rather than passing through it: treating a
  scratch as transparent would silently merge two runs into one longer-looking
  streak.
- **Maximum drawdown is a non-negative magnitude**, so a larger number always
  means a worse drawdown.
- **Aggregation is permitted only over provenance-complete records.** Per-model
  and combined-policy reports both refuse a set with duplicate identity, mixed
  provenance, or a double-counted observation. Per-model reports cover only the
  models actually present — emitting an empty report for an unobserved model
  would invite reading its zeros as measurements.

---

## 8. The staged ladder

This package builds the first rung and only the first rung. The ladder is the
approved one from the Responsibility Contract; **no stage may be skipped, and
each is a separate Pedro approval.**

```
  (0) foundation          ← this package. Built. No data, no result.
   │
  (1) historical backtest    labeled history, in-sample. Measures what the
   │                         recorded past contains. Proves nothing forward.
   │
  (2) out-of-sample          the frozen partition this package refuses to let
   │                         the earlier stages touch. First honest test.
   │
  (3) paper                  forward, unfunded, live data. First contact with
   │                         latency, fills, and real-time ambiguity.
   │
  (4) governance dry run     risk gates, session gates, and audit trail
   │                         exercised end to end with no order submitted.
   │
  (5) Pedro's explicit funded-account authorization
   │
  (6) monitored limited autonomy → expansion only through new approval
```

**Execution is disabled throughout stages 0–4 and remains disabled now.** The
trading subsystem is retired, `NOVA_TRADING_SUBSYSTEM_ENABLED` defaults to
false, and the retirement guard blocks re-enablement. Reaching stage 2 with
excellent numbers changes exactly one thing: it makes stage 3 a question worth
asking. It does not authorize stage 3, and it never authorizes an order.

### 8.1 What each stage cannot claim

| Stage | Cannot claim |
|---|---|
| Historical backtest | That the edge exists forward. In-sample arithmetic describes the sample it was fitted to observe |
| Out-of-sample | That live results will match. It shares the backtest's data source, labeling hand, and survivorship |
| Paper | That funded results will match. No slippage cost is real until capital is |
| Governance dry run | That the system is safe. It shows the gates fire, not that the gates are sufficient |

---

## 9. Running the tests

```bash
# Both new files
python -B -m pytest tests/test_prime_validation_schema.py tests/test_prime_validation_engine.py -q

# Full suite
python -B -m pytest tests -q
```

Run from the repository root with `python -m pytest`, so the repository root is
on `sys.path` and `research.prime_validation` resolves. The test files also
insert the root defensively.

Per `CLAUDE.md`: **never claim a test result you did not measure**, and never
weaken a test to make a change pass. If a test here blocks a change, either the
change is wrong or the test needs a deliberate, separately approved update.

The suite is adversarial by design. It covers:

- the exact three-model set;
- invalid models, symbols, directions, timestamps, session dates, provenance
  hashes, and risk values;
- zero and negative entry and exit prices;
- long and short R, including the sign flip;
- labels that contradict their own prices;
- duplicate identity, mixed provenance, and double-counted observations;
- a missing, mistyped, naive, or non-UTC `as_of` cutoff, and the absence of any
  wall-clock read in the package;
- future leakage and boundary-straddling instants;
- one-trade-per-session selection;
- selection and session keys that try to read outcome, exit price, R, actual
  trade state, or the full candidate;
- selection that stays the same when outcomes are flipped;
- deterministic tie behaviour and tie rejection;
- every honest-metric edge case above.

---

## 10. Authority and boundaries

- **Pedro** owns strategy, risk, approval, and the promotion of research into
  PRIME. Nothing in this package promotes anything.
- **Claude** owns the engineering, the tests, and this document. It does not own
  the methodology, the ratios, the minimum sample size, or the selection key —
  each of those is deliberately a caller or owner decision.
- **Git is authoritative.** `nova_knowledge_core/CURRENT/PRIME/` defines the
  locked universe; this package mirrors it and must be corrected if it drifts.
- **Obsidian is non-authoritative** and executes nothing.

**Nothing in this document or package authorizes autonomous or funded trading.**
No stage of the validation ladder is complete. The trading and execution
subsystem remains temporarily disabled, and its return requires a separate,
explicit, owner-approved system change.
