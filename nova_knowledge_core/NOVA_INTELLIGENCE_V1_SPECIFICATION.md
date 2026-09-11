# NOVA Intelligence V1 — Architecture Specification

Date: 2026-07-20 (revised — Pedro's ten final decisions locked, see §13)
Status: **Specification only. No implementation code exists yet.** This document designs one centralized, provider-independent intelligence layer for NOVA, replacing the eight disconnected Claude/Grok call sites documented in the read-only AI-architecture audit. Phase 0 safety and cost containment is complete (commit `1514bcd`) — the retired setup-monitor no longer auto-starts, and the health check no longer makes a billable Anthropic call. This document does not authorize implementation; each migration commit in §14 requires Pedro's separate approval, same discipline as the Market Map V1 track.

Claude may continue helping write this system's code in Codespaces. **NOVA itself must not depend on Claude specifically to operate** — the entire point of this layer is that the active provider is a configuration value, not a hardcoded dependency.

---

## 0. Requirements status key

- **FINAL** — Pedro has explicitly locked this; no re-approval needed. As of this revision, all ten of Pedro's decisions (§13) are FINAL — no PROPOSED items remain outstanding from that table.
- **PROPOSED** — a default this document recommends where structure, not a specific number or scope, is still flexible (e.g. §14's exact commit granularity); does not block implementation the way an open Pedro decision would have.
- **DEFERRED** — intentionally out of V1 scope, documented so it is neither silently dropped nor silently built.

---

## 1. Purpose and primary goals (FINAL — as stated by Pedro)

Design one centralized, provider-independent intelligence layer for NOVA. NOVA Intelligence V1 replaces the current collection of disconnected Claude and Grok call sites with one controlled gateway.

1. One central AI gateway.
2. One active runtime provider at a time.
3. Provider-independent application code.
4. Low and predictable operating cost.
5. No automatic surprise spending.
6. No duplicate AI calls.
7. No autonomous trading behavior.
8. Clear failure behavior when credits or providers are unavailable.
9. Preserve the working Journal, Market/News, and NOVA Assistant.
10. Keep all retired trading systems retired.

---

## 2. Current state this replaces (evidence, from the read-only audit)

For traceability, every call site this system is designed to eventually absorb:

| # | File : line | Feature | Provider |
|---|---|---|---|
| 1 | `services/assistant.py:194` | NOVA Assistant chat | Anthropic |
| 2 | `main.py:3131` | Journal "NOVA Review" | Anthropic |
| 3 | `engines/engines.py:1179` | Scenario engine | Anthropic |
| 4 | `engines/engines.py:1315` | Performance-insight one-liner | Anthropic |
| 5 | `engines/engines.py:1592` | Morning brief | Anthropic |
| 6 | `engines/reasoning.py:2663` | Legacy setup grading (archived, disabled Phase 0) | Anthropic |
| 7 | `main.py:224` / `main.py:593` | Grok market-sentiment card | xAI Grok (raw HTTP) |
| 8 | `services/news.py:271` | Grok headline classifier | xAI Grok (`openai` SDK) |

No shared abstraction exists between these eight call sites today — each imports `core.config`'s client or builds its own provider client independently, with its own prompt, its own `max_tokens`, and its own error handling.

---

## 3. V1 features (FINAL scope, as defined by Pedro)

NOVA Intelligence V1 supports **exactly three** features. Nothing else is migrated or built in V1.

### 3.1 NOVA Assistant
- User-initiated chat only.
- Read-only guidance.
- May explain Journal and Market/News information, but Journal context specifically is **explicit selection only** (§13 decision 10, FINAL) — Pedro must deliberately select or attach a trade; the Assistant never automatically pulls Journal history.
- Must not generate canonical trades, BUY/SELL signals, execution instructions, grades, or alerts.

### 3.2 Journal NOVA Review
- User-initiated analysis of a selected trade.
- May identify discipline, risk-management, execution, and behavioral patterns.
- Must preserve historical Journal data.
- Must not depend on retired strategy fields to function — historical legacy fields (`pros_phase`, `ib_draw`, `nova_cmd`, grade, etc., per the current `main.py:3070-3090` signal-context block) may remain **readable** as historical context but must never **control** whether or how the review runs.

### 3.3 Market/News Summary
- **Manual-only in V1** (§13 decision 8, FINAL) — user-initiated requests only, never silent background polling. Scheduling of any kind is deferred and requires a future, separately-approved specification (§4).
- Summarizes existing NOVA market/news data (already-fetched headlines, risk state — not a live web/X search).
- Must not create trading signals or directional commands.

---

## 4. Deferred — not in V1 (FINAL, explicitly not migrated)

These remain exactly where they are today (most already archived per the trading-subsystem retirement and Phase 0 safety work) — not ported into the new gateway, not deleted:

- Legacy setup grading (A–D grades)
- Harvey
- Market Reality V1/V2 (as an AI-consuming feature — the underlying price-truth engines stay, per the retirement's "KEEP Market Reality" decision; only the AI-grading use of them is deferred)
- Execution Bot
- Broker actions
- Discord setup alerts
- TradingView/CDP reasoning loops
- Scenario engine
- Morning brief
- Performance-insight one-liner
- Canonical BUY/SELL state
- Autonomous chart monitoring
- Autonomous trading analysis
- Automatic cross-provider fallback
- Any background AI polling
- Any AI-generated trade entry or exit

If a future version needs any of these, that is a new, separately-scoped, separately-approved specification — not a silent addition to V1, consistent with every prior retirement/spec document in this project.

---

## 5. Grok direction (FINAL — decision 9, locked)

**Grok is fully retired from active V1 architecture.** It is not an independently active second brain, not an optional adapter, and not present in the V1 module tree in any form — inert or otherwise.

**Locked for V1:**
- No `providers/grok_adapter.py` is created. §6's module tree contains exactly one provider adapter: `providers/anthropic_adapter.py`.
- No Grok is a valid value of `NOVA_AI_PROVIDER` in V1 (§10). The only valid value is `anthropic`.
- No automatic or optional Grok runtime support of any kind — not as a fallback, not as a manually-selectable alternate, not as a future-flagged inert stub.
- The OpenAI SDK is **not** included in V1's dependencies merely to communicate with Grok. If a future Grok (or other OpenAI-compatible) adapter is ever built, that dependency is added in that adapter's own separately-approved migration commit, not carried into V1 "just in case."
- The Market/News **feed itself** (headlines, calendar, risk state — all deterministic ingestion) is preserved untouched; only the AI-summarization layer on top of it is affected.
- Deterministic news processing is used wherever it's sufficient — risk classification, calendar parsing, etc. do not need an LLM and never route through the gateway just because one exists.
- Any *optional* AI news summary in V1 uses the single active provider (Anthropic, §13 decision 1) — never a Grok-specific path.

**What does NOT happen in this specification revision:** the two existing Grok implementations (`main.py`'s raw HTTP call, `services/news.py`'s `openai`-SDK call) are **not deleted or modified now**. They remain exactly as they are — historical code, preserved — until a separately-scoped, separately-approved future retirement migration commit removes them. See §14's migration-sequence correction: Grok removal is its own later commit, after the three V1 features are working through the gateway, never bundled into V1's build-out.

After that future retirement commit completes, **no provider-specific application code remains** — `openai`, `requests.post('https://api.x.ai/...')`, and direct `anthropic` imports are removed from every feature file, existing only inside the gateway's provider adapter(s) (§6).

---

## 6. Central gateway module structure (PROPOSED structure, FINAL provider scope per §5/§13)

```
intelligence/
├── __init__.py
├── gateway.py             # request_intelligence() -- the one application-facing entry point
├── config.py              # centralized env-var reads for this layer only (§10)
├── registry.py            # feature registry: maps feature name -> template + schema + limits
├── envelope.py            # shared response envelope dataclass/schema (§11)
├── errors.py              # error_code enum + controlled-error construction (§9)
├── budget.py              # daily request count + estimated-cost ceiling + circuit breaker + persistent state (§8, §8.1)
├── cache.py               # input-hash response cache, per-feature TTL (§8's #6-#7)
├── audit.py               # usage/observability logging, secret-safe (§12)
├── model_registry.py      # reviewed table of supported model IDs + per-token pricing (§8.2)
├── providers/
│   ├── __init__.py
│   ├── base.py            # ProviderAdapter interface (§6.1)
│   └── anthropic_adapter.py
└── prompts/
    ├── assistant.py        # NOVA Assistant prompt template + input/output schema
    ├── journal_review.py   # Journal NOVA Review prompt template + input/output schema
    └── market_summary.py   # Market/News Summary prompt template + input/output schema
```

V1 contains **exactly one** provider adapter. There is no `grok_adapter.py`, present-but-inert or otherwise — see §5 (FINAL). Package directories use `__init__.py` (double-underscore), not `init.py`.

### 6.1 Responsibilities

| Module | Responsibility |
|---|---|
| `gateway.py` | The only function application code calls: `request_intelligence(...)` (§7.1). Resolves the active provider, loads the feature's template/schema/limits from the registry, checks the budget, checks the cache, calls the provider adapter, wraps the result in the response envelope, writes the audit log entry. Contains no feature-specific knowledge and no provider-specific knowledge. |
| `config.py` | Reads every env var in §10. Nowhere else in the codebase reads an AI-related env var directly once migration (§14) completes. |
| `registry.py` | A single dict/table mapping each of the three V1 feature names to its prompt template module, its input/output schema, its `max_tokens`, its cache TTL, and its timeout — the one place a new feature is "turned on." |
| `envelope.py` | Defines the shared response shape (§11) every gateway call returns, success or failure. |
| `errors.py` | Defines the fixed `error_code` vocabulary (§9) and maps provider-specific exceptions to it — the only place that translates "Anthropic raised X" into "NOVA means Y." |
| `budget.py` | Daily request counter and estimated-cost ceiling (§8's #8-#9), backed by the **persistent** daily-usage state defined in §8.1 (not the in-memory cache — a process restart must not reset today's count), plus the circuit breaker (§8's #10). Performs the atomic pre-call budget reservation described in §8.3 — checking only already-accrued spend is not sufficient, since it does not guarantee the *next* request stays under budget. Provider-agnostic, keyed by feature and by day. |
| `cache.py` | Input-hash keyed **response** cache (hash of feature + normalized input_data), reusing the existing `core.config.CACHE`/`cache_get`/`cache_set` TTL pattern already used elsewhere in the codebase. This cache is intentionally ephemeral — losing cached responses on restart is acceptable (§8.1 note) — and is a separate concern from `budget.py`'s persistent counters. |
| `audit.py` | Writes the observability log (§12) to a new `nova_intelligence_usage_log.json`-style file, following the existing `_data_file()` naming convention in `core/config.py`. |
| `model_registry.py` | A reviewed, manually-maintained table mapping supported `NOVA_AI_MODEL` values to their per-token input/output pricing, used by `budget.py` to compute `estimated_cost_usd`. See §8.2 (fail-closed behavior for unregistered models). |
| `providers/base.py` | Defines the `ProviderAdapter` interface every adapter must implement: `call(prompt, max_tokens, timeout) -> AdapterResult` (raw text/structured output + token usage), nothing feature-specific. |
| `providers/anthropic_adapter.py` | The one V1 provider adapter, wrapping the Anthropic SDK. This is the **only** file in the entire codebase permitted to `import anthropic` or construct an Anthropic client. |
| `prompts/*.py` | One file per V1 feature: builds the prompt from `input_data`, defines the expected output schema, and parses the raw provider response back into `structured_data`. This is where each of the three existing prompt bodies (from `services/assistant.py`, `main.py:3092-3123`, and a new deterministic-first market-summary prompt) land, unmodified in substance — moved, not rewritten, per the migration plan's "one feature per commit" rule (§14). |

No feature file (Assistant, Journal, Market/News) imports `anthropic`, `openai`, or performs a raw `requests.post` to a provider endpoint after migration — everything routes through `gateway.request_intelligence()`.

---

## 7. Application-facing request interface

### 7.1 Conceptual signature (FINAL shape, per Pedro)

```python
request_intelligence(
    feature,       # one of: "assistant", "journal_review", "market_summary"
    input_data,    # dict — feature-specific, schema-validated by registry.py
    user_id,       # currently always "pedro" (single-user system) -- kept for
                   # audit-log consistency and to avoid a breaking signature
                   # change if NOVA ever becomes multi-user
    request_id,    # caller-supplied or gateway-generated UUID, threaded through
                   # the envelope and the audit log for correlation
)
```

Returns the response envelope (§11) — always, on both success and failure. The caller never receives a raw provider exception.

### 7.2 One active provider rule (FINAL)

- V1 uses exactly **one** configured runtime provider at a time (`NOVA_AI_PROVIDER`, §10).
- **No automatic cross-provider fallback.** If the active provider fails, the gateway returns a controlled error (§9) — it does not silently try the other adapter.
- **No sending the same request to multiple providers** "just to see" or for redundancy.
- **No hidden secondary-provider call** anywhere in the gateway or in feature code.
- Changing providers is a configuration change (`NOVA_AI_PROVIDER` set to whichever adapter is registered — in V1 the only valid value is `anthropic`, per §5/§13 decision 9 — or a future provider added by its own separately-approved adapter) — never a code change in feature files, since feature files only ever call `request_intelligence()`.
- If the configured provider is unavailable (missing key, auth failure, quota, etc.), `request_intelligence()` returns `success: false` with a specific `error_code` (§9) — it never falls back and never fabricates a response.
- **NOVA's non-AI features must keep working** when the provider is down — Journal CRUD, Market/News data display, and everything else not listed in §3 has zero dependency on the gateway and is unaffected by any AI outage.

---

## 8. Cost-control requirements (FINAL — Pedro's locked numbers, §13)

| # | Control | Locked value | Notes |
|---|---|---|---|
| 1 | Per-feature max output tokens | Assistant 400 · Journal Review 800 · Market Summary 500 | Matches the token budgets already in use today (`services/assistant.py` uses 400, `main.py:3135` uses 800) — carried forward, not invented. |
| 2 | Max input/context size | ~4,000 tokens per feature (rough char-count guard, not exact tokenization) | Prevents an unbounded prompt (e.g., a huge nearby-signal-log dump) from silently ballooning cost. |
| 3 | Request timeout | 30 seconds | Matches the existing Grok call's `timeout=30` (`main.py:238`); Anthropic SDK calls currently have no explicit timeout — this closes that gap. |
| 4 | Retry policy | At most **one** controlled retry, transient errors only (timeout, 5xx, connection error) | |
| 5 | No-retry errors | Billing, authentication, quota/rate-limit errors never retry | Retrying a billing failure just wastes another attempt on a request that cannot succeed — matches the real incident documented in `tests/test_nova_review.py` (Anthropic credit exhaustion). |
| 6 | Response caching | Input-hash keyed, per §6.1's `cache.py` | Reuses `core.config.CACHE` pattern — ephemeral, restart-safe to lose (§8.1). |
| 7 | Cache duration by feature | Assistant: **no cache** (conversational, each message is distinct) · Journal Review: **24 hours** (§13 decision 6 — a trade's facts don't change) · Market Summary: **30 minutes** (§13 decision 7) | Both durations are FINAL, not ranges. |
| 8 | Daily request limit | **20 total provider attempts per day, across all three V1 features combined** (§13 decision 4) | Not per-feature — one shared daily counter. Counts **provider attempts**, not user-visible requests: a cache hit (row #6) makes zero provider calls and never counts; a retry (row #4) is itself a second provider attempt and counts separately from the initial attempt. Enforced via the pre-call reservation in §8.3, not a post-hoc count. |
| 9 | Daily estimated-cost ceiling | **$0.25 USD per day** (§13 decision 5) | Computed from each response's reported token usage × the active provider's per-token rate, looked up in `model_registry.py` (§8.2) — not fetched live. Enforced via the pre-call reservation in §8.3 using a worst-case *projected* cost, not just already-settled spend, since checking only accrued cost cannot guarantee the next request stays under the ceiling. |
| 9a | Budget-exceeded behavior | When **either** the daily request limit (#8) **or** the daily cost ceiling (#9) would be exceeded by reserving this request's worst-case attempt count and cost, the gateway returns `BUDGET_EXCEEDED` (§9) **without calling the provider** | Whichever limit trips first wins; checked and reserved atomically, under a single lock, before every paid call (§8.3) — never a check followed by a separate, unlocked reservation step. |
| 9b | Budget-state failure behavior | If the persistent budget state (§8.1) is corrupt, unreadable, or its lock cannot be acquired, the gateway returns `BUDGET_STATE_UNAVAILABLE` (§9) **without calling the provider** | Fails closed. Never silently resets the daily counters and never proceeds as if budget were unlimited just because the tracking mechanism itself failed (§8.3). |
| 10 | Circuit breaker | 3 consecutive failures for the same feature within 5 minutes trips the breaker for that feature for 15 minutes, returning a controlled error immediately without attempting the provider | Prevents hammering a down/exhausted provider. |
| 11 | No background AI calls by default | FINAL, matches §3's "user-initiated only" requirement for all three features | |
| 12 | Every paid request traceable to a visible user action or explicitly approved schedule | FINAL | No feature may originate a gateway call from a passive page-load or polling loop. |
| 13 | Usage logging without secrets | FINAL, see §12 | |
| 14 | Clear "AI unavailable" user-facing behavior | FINAL, see §9 | |
| 15 | Non-AI NOVA features continue when budget exhausted | FINAL, same guarantee as §7.2's provider-down case | |

### 8.1 Durable daily budget state (FINAL)

The daily request counter and estimated-cost ceiling (#8, #9, #9a, #9b above) **must not** rely solely on the existing in-memory `core.config.CACHE` — an application restart (deploy, crash, manual restart) would silently reset the count to zero and reopen the budget mid-day, defeating the ceiling entirely.

`budget.py` instead maintains a small **persistent** daily-usage state file inside NOVA's existing configured data directory (following the `_data_file()` convention already used throughout `core/config.py`, e.g. `data/nova_intelligence_budget.json`), with:

- **Atomic writes** — write to a temp file and rename, never a partial in-place write, consistent with how other NOVA state files avoid torn writes.
- **Date-based reset** — the stored record is keyed by date (e.g. `"2026-07-20"`); the first request of a new day finds no matching key and starts all counters at zero, rather than requiring a separate scheduled reset job.
- **Safe locking appropriate for the current deployment** — NOVA today is a single-process local/Render deployment per feature (§ system architecture in `CLAUDE.md`), so a simple file-lock or atomic-rename-based guard is sufficient; this is not designed for concurrent multi-process writers. The lock guards the read-check-reserve sequence in §8.3 as a single atomic unit, not just the write.
- **No prompts, responses, API keys, or private Journal content** — the persisted record contains only: date, `request_count` (settled provider attempts today), `accrued_cost` (settled actual/worst-case-settled cost today), `reserved_count` (in-flight provider attempts not yet settled), and `reserved_cost` (in-flight worst-case cost not yet settled). See §8.3 for how reservation and settlement move values between these fields. Nothing else is stored.

**External hard backstop:** the provider's own workspace/monthly spend limit (configured directly in the Anthropic console, outside NOVA) must also be documented and set as the true hard backstop. NOVA's $0.25/day application-level ceiling is a **safeguard implemented in NOVA's own code**, not a guarantee against every possible process failure (e.g., a bug in `budget.py` itself, or a corrupted state file bypassing the check). Pedro should set a corresponding monthly cap directly with the provider as defense in depth.

Response caching (`cache.py`, #6-#7 above) is **not** held to this durability requirement — losing cached responses on restart only costs a few redundant paid calls at worst, not a silent budget blowout, so it may continue using the existing ephemeral `CACHE` pattern unchanged. A cache hit also never touches the budget state at all (§8.3) — it isn't a provider attempt.

### 8.2 Supported-model budget safety (FINAL)

The cost calculator in `budget.py` computes `estimated_cost_usd` by looking up the configured `NOVA_AI_MODEL` in `model_registry.py` — a small, manually reviewed table of supported model IDs and their published per-token input/output pricing.

**If `NOVA_AI_MODEL` is set to a model with no entry in `model_registry.py`, the gateway must fail closed**: every paid request returns `error_code: MODEL_NOT_SUPPORTED` (§9) rather than silently proceeding without a cost estimate. An unregistered model must never be allowed to bypass the daily cost ceiling (§8's #9) simply because its price is unknown — "unknown cost" is treated as "cannot verify the budget is respected," not as "assume zero."

### 8.3 Pre-call budget reservation and atomicity (FINAL)

Checking only the already-*accrued* daily cost (§8.1) is not sufficient — it tells you what has already happened, not whether the *next* request will stay under the $0.25 ceiling once it completes. `budget.py` therefore reserves the request's worst-case cost and attempt count **before** calling the provider, not just afterward:

1. **Normalize and validate the bounded input** — the existing input-size guard (§8's #2) runs first, so the reservation estimate is computed from a bounded prompt, not an unbounded one.
2. **Estimate the request's maximum possible cost**, using:
   - the bounded estimated input tokens (from step 1),
   - the feature's maximum output-token allowance (§8's #1), and
   - the registered price for `NOVA_AI_MODEL` in `model_registry.py` (§8.2) — if the model is unregistered, this step itself fails closed with `MODEL_NOT_SUPPORTED` before any reservation is attempted.
   - If the request's retry policy (§8's #4) permits one controlled retry, the projection accounts for **up to two provider attempts** (the initial call plus one retry), since a retry is itself a second billable attempt, not a free redo.
3. **Under a single atomic lock on the persistent budget-state file (§8.1)**:
   - re-read the current persisted state fresh (`request_count`, `accrued_cost`, `reserved_count`, `reserved_cost`) — never trust a stale in-memory copy, so two simultaneous requests cannot both check against the same remaining budget and both pass;
   - verify `request_count + reserved_count + (this request's up-to-2 attempts)` remains within the daily limit of 20 (§8's #8);
   - verify `accrued_cost + reserved_cost + (this request's projected max cost)` remains within $0.25 (§8's #9);
   - if either check would be exceeded, release the lock and return `BUDGET_EXCEEDED` (§9's #9a) **without calling the provider**;
   - otherwise, add this request's projected attempt count and projected max cost into `reserved_count` / `reserved_cost`, persist atomically, and release the lock. This reservation is now "in flight."
4. **Call the provider** (the initial attempt, and the single retry per §8's #4 if it's needed and was already accounted for in step 2's projection).
5. **After the response** (success, or a final failure after retry is exhausted): under the same lock, remove this request's reservation from `reserved_count`/`reserved_cost` and settle the real outcome into `request_count`/`accrued_cost`:
   - if the provider reported actual token usage, settle using the **real** cost computed from that usage and the **real** number of attempts actually made (1 or 2);
   - persist the corrected totals atomically.
6. **If the provider fails without ever reporting usage** (e.g., a connection error or timeout with no response body) such that the real cost is unknown: settle using the reservation's *projected max cost* as the actual charge, not zero. An unknown, potentially-billable attempt is never assumed to have cost nothing — the worst-case estimate becomes the recorded spend for that attempt.
7. **If the persistent budget-state file is corrupt, unreadable, or its lock cannot be acquired**: fail closed immediately with `error_code: BUDGET_STATE_UNAVAILABLE` (§9) — do not call the provider, and do not silently reset or recreate the daily counters as though it were a fresh day just because the file couldn't be read.

**Clarifications:**
- A cache hit (§8's #6) makes zero provider calls and is never checked against, or reserved from, the daily budget — it isn't a provider attempt.
- Every actual provider attempt counts toward the daily limit, including the single retry (§8's #4) — a visible user request that triggers a retry consumes **two** provider attempts, not one.
- The check-and-reserve sequence in step 3 is one atomic, locked operation — a budget check that isn't immediately followed by its own reservation, under the same lock, would let two simultaneous requests both observe the same "remaining budget" and both proceed, together exceeding the ceiling.

---

## 9. Error behavior (FINAL structure, one `error_code` per condition)

| `error_code` | Condition | User-facing behavior |
|---|---|---|
| `PROVIDER_NOT_CONFIGURED` | No API key set for the active provider | "AI features are not configured right now." No retry. |
| `AUTH_FAILED` | Provider rejects the API key | Same user message as above (no key-detail leakage). No retry. |
| `INSUFFICIENT_CREDITS` | Billing/quota exhausted (the exact incident `test_nova_review.py` documents) | "AI credits are unavailable right now — try again later." No retry. |
| `RATE_LIMITED` | Provider 429 | "AI is temporarily busy — try again in a moment." No retry (rate limits need real backoff time, not an immediate retry). |
| `TIMEOUT` | Request exceeded §8's #3 timeout | One retry per §8's #4, then the same user message as rate-limited if the retry also times out. |
| `INVALID_PROVIDER_RESPONSE` | Non-2xx or empty response body | Generic "AI request failed" message. No retry beyond §8's #4 transient-error allowance. |
| `MALFORMED_OUTPUT` | Response received but fails schema validation (e.g., NOVA Review's expected section structure) | Generic failure message. **The raw or complete response is never logged** (§12 is not overridden by this row) — only `request_id`, `feature`, provider/model, response character length, a response hash (if useful for correlating repeat failures), the schema-validation error category, latency, and token usage when available. If deep debugging of a malformed-output incident ever requires the actual response content, that requires a separate, temporary, Pedro-approved debug mechanism that does not exist in V1 — not a standing log level or an exception to this row. |
| `BUDGET_EXCEEDED` | Reserving this request's worst-case attempt count or cost would exceed the daily request limit (20/day) or cost ceiling ($0.25/day) (§8, §8.3) | "Today's AI usage limit has been reached." No retry, no override without a config change. |
| `BUDGET_STATE_UNAVAILABLE` | The persistent budget-state file (§8.1) is corrupt, unreadable, or its lock cannot be acquired (§8.3's step 7) | "AI usage tracking is temporarily unavailable, so no paid request was made." No retry; never proceeds as if budget were unlimited and never silently resets the daily counters. |
| `CIRCUIT_OPEN` | §8's #10 breaker is tripped for this feature | "AI is temporarily unavailable — try again shortly." |
| `MODEL_NOT_SUPPORTED` | `NOVA_AI_MODEL` has no entry in `model_registry.py` (§8.2) — cost cannot be verified | "AI is misconfigured — the configured model isn't recognized." No retry; this is a configuration error, not a transient one. |

Every error is surfaced to the user through the existing UI error-handling paths already established during the UI retirement work (e.g., the `_novaReviewError()` toast pattern `test_nova_review.py` already covers) — never a silent empty response, never an infinite retry loop, and never a crash that takes down Journal or Market/News alongside it.

---

## 10. Configuration (FINAL variable names and locked defaults, no secret values)

| Variable | Purpose | Locked V1 value |
|---|---|---|
| `NOVA_AI_PROVIDER` | Active provider — single source of truth for §7.2's one-active-provider rule. | `anthropic` (§13 decision 1 — the only valid V1 value; no `grok` option exists) |
| `ANTHROPIC_API_KEY` | The Anthropic adapter's API key. **V1 continues using this existing variable** rather than introducing a generic `NOVA_AI_API_KEY` — provider-independent application code does not require renaming the existing secret, since only `providers/anthropic_adapter.py` ever reads it. A future non-Anthropic provider adds its own provider-specific key variable inside its own adapter when that adapter is built; no generic cross-provider key variable is introduced speculatively. | (secret, not stored in this document) |
| `NOVA_AI_MODEL` | Default model for the active provider, looked up in `model_registry.py` (§8.2). | `claude-haiku-4-5-20251001` (§13 decision 2) |
| `NOVA_AI_DAILY_REQUEST_LIMIT` | §8's #8. | `20` |
| `NOVA_AI_DAILY_COST_LIMIT_USD` | §8's #9. | `0.25` |
| `NOVA_AI_REQUEST_TIMEOUT_SECONDS` | §8's #3. | `30` |
| `NOVA_AI_CACHE_ENABLED` | Boolean master switch for §8's #6-#7 (per-feature TTLs still come from the registry, not a second env var each). | `true` |
| `NOVA_AI_LOG_LEVEL` | Controls §12's logging verbosity (e.g., `INFO` vs `DEBUG` — `DEBUG` still never logs full prompts, per §12's hard rule). | `INFO` |

**`NOVA_AI_REASONING_MODEL` does not exist in V1** (§13 decision 3, FINAL) — none of the three V1 features request a separate higher-reasoning-model tier. If a future feature needs one, that is a new, separately-approved specification, consistent with §4's deferred-feature discipline.

This intentionally **replaces** `ANTHROPIC_MODEL` and `ANTHROPIC_ASSISTANT_MODEL` (two separate model vars for no-longer-relevant reasons — one was for the retired grading pipeline) with a single `NOVA_AI_MODEL`. It does **not** touch `GROK_API_KEY` — that variable, and the code that reads it in `main.py` and `services/news.py`, is untouched historical configuration until Grok's separate future retirement commit (§5, §14) removes it. No provider gets a generic always-present key variable; each adapter reads its own provider-specific secret name internally.

---

## 11. Structured response envelope (FINAL shape)

```python
{
    "success":         bool,
    "feature":         str,             # "assistant" | "journal_review" | "market_summary"
    "provider":        str,             # which provider actually served this (or attempted to)
    "model":           str,
    "content":         str | None,      # raw text reply, when applicable
    "structured_data":  dict | None,     # parsed/validated feature-specific payload
    "error_code":      str | None,      # one of §9's fixed vocabulary, else None
    "user_message":    str | None,      # the exact string shown to the user on failure
    "request_id":      str,
    "cached":          bool,            # true if served from cache.py, no provider call made
    "usage": {
        "input_tokens":  int | None,
        "output_tokens": int | None,
        "estimated_cost_usd": float | None,
    },
    "latency_ms":      int,
}
```

`usage` never contains anything beyond token counts and a computed cost estimate — no request/response body, no headers, no key fragments.

---

## 12. Observability (FINAL — what is logged, and the hard exclusion)

Logged per request (new file, e.g. `nova_intelligence_usage_log.json`, following the existing `_data_file()` convention):

- Feature name
- Request ID
- Provider / model
- Input token estimate (pre-call) and actual usage (post-call, when the provider returns it)
- Output tokens
- Cache hit/miss
- Latency
- Success/failure
- Error category (`error_code`, not the raw exception text)
- Estimated cost, when calculable from `model_registry.py` (§8.2)
- For `MALFORMED_OUTPUT` specifically (§9): response character length and a response hash (if useful for correlating repeat failures) — never the response content itself

**Hard exclusion, no exceptions:** complete prompts and complete responses are never logged, at any `NOVA_AI_LOG_LEVEL`, under any V1 error condition including `MALFORMED_OUTPUT`. This is not a default that a log-level setting can override. If deep debugging of a malformed-output incident is ever genuinely needed, that requires a separate, temporary, Pedro-approved mechanism that does not exist in V1 — not a standing log level and not a config flag inside this specification's scope.

---

## 13. Pedro's final decisions (FINAL — all ten locked, 2026-07-20)

All ten decisions are now locked. None of them were chosen silently by this document — each is Pedro's explicit instruction, recorded here for traceability back to the requirements that reference them.

| # | Decision | Locked value |
|---|---|---|
| 1 | First active runtime provider | **Anthropic.** `NOVA_AI_PROVIDER=anthropic` (§10). |
| 2 | Default model | **`claude-haiku-4-5-20251001`.** `NOVA_AI_MODEL` (§10). |
| 3 | Separate higher-reasoning model | **Not included in V1.** `NOVA_AI_REASONING_MODEL` is removed from the specification entirely (§10). A stronger model tier requires a future, separately-approved specification. |
| 4 | Daily request limit | **20 total provider attempts per day, across all three V1 features combined.** `NOVA_AI_DAILY_REQUEST_LIMIT=20` (§8, §10). Counts provider attempts, not user-visible requests — cache hits don't count, a retry is a second attempt (§8.3). Enforced via pre-call reservation, not a post-hoc count. |
| 5 | Daily estimated-cost ceiling | **$0.25 USD per day.** `NOVA_AI_DAILY_COST_LIMIT_USD=0.25` (§8, §10). When reserving either this request's worst-case cost or attempt count would exceed decision 4's or this limit, the gateway returns `BUDGET_EXCEEDED` without calling the provider (§8's #9a, §8.3, §9). |
| 6 | Journal Review cache duration | **24 hours** for identical normalized input (§8's #7). |
| 7 | Market/News Summary cache duration | **30 minutes** for identical normalized input (§8's #7). |
| 8 | Market/News summary scheduling | **Manual-only in V1.** Scheduling beyond user-initiated requests is deferred and requires future approval (§3.3, §4). |
| 9 | Grok's fate | **Fully retired from active V1 architecture.** No `grok_adapter.py` (inert or otherwise), no Grok value for `NOVA_AI_PROVIDER`, no OpenAI SDK dependency in V1. Historical Grok code (`main.py`'s raw HTTP call, `services/news.py`'s `openai`-SDK call) is preserved untouched until its own separately-approved retirement migration commit — not migrated into `intelligence/` now (§5, §14). |
| 10 | Assistant's Journal-context access | **Explicit selection only.** The Assistant may receive Journal context only when Pedro deliberately selects or attaches a trade — it must never automatically pull Journal history (§16). |

---

## 14. Migration plan — one small commit at a time (FINAL sequence, PROPOSED granularity)

No commit beyond #1 (this document) happens without Pedro's separate go-ahead, matching the Market Map V1 track's discipline.

| # | Commit | Scope |
|---|---|---|
| 1 | `Define NOVA Intelligence V1 specification` | This document only — no code. (commit `8b1d227`, this revision supersedes it as a new commit, §13/§14 corrections.) |
| 2 | Central gateway interfaces + configuration | `intelligence/gateway.py`, `config.py`, `registry.py`, `envelope.py`, `errors.py`, `model_registry.py` skeletons — no live provider call yet, no feature migrated. |
| 3 | Anthropic provider adapter with mocked tests | `providers/base.py` + `providers/anthropic_adapter.py` (the **only** V1 adapter, §5/§13 decision 9), fully unit-tested with mocks — zero real API calls in tests (§15.18). No Grok adapter is created in this or any V1 commit. |
| 4 | Usage limits, caching, and error handling | `budget.py` (including the §8.1 persistent daily-usage state file), `cache.py`, `audit.py` wired into `gateway.py`. |
| 5 | Migrate NOVA Assistant | `services/assistant.py` calls `request_intelligence("assistant", ...)` instead of `core.config.client` directly; old path removed once verified. Journal-context access follows §13 decision 10 — explicit selection only. |
| 6 | Migrate Journal NOVA Review | `main.py`'s `/journal/analyze` calls the gateway instead of `core.config.client` directly. |
| 7 | Migrate Market/News Summary | New feature built against the gateway from the start, manual-only per §13 decision 8. This commit does **not** touch the existing Grok call sites — they are a separate, later commit (#8 below), not part of building this feature. |
| 8 | Retire Grok (separate, later commit — not bundled with #2-#7) | Only after commits #2-#7 land and the three approved features are confirmed working through the gateway: remove or archive (matching the trading-subsystem retirement's "archive, don't delete" precedent where historically meaningful) the direct-import Grok code in `main.py` (raw HTTP) and `services/news.py` (via `openai`), per §13 decision 9. Removes Grok's two entries from the **temporary active-migration allowlist** (§15.1a), which reaches zero entries once this commit lands. This commit requires its own separate approval and is explicitly **not** authorized by this specification revision. `engines/engines.py`'s deferred features (§4) are **not** touched by this or any other V1 commit — they are tracked instead in the separate, permanent **archived-code inventory** (§15.1b), which requires each entry proven unreachable from the active application, not merely left alone by omission. |
| 9 | Final cost, security, and regression audit | Full test suite, a real (small, Pedro-approved) live smoke test of all three migrated features, confirmation of §15's full test list including the allowlist-empty check (§15's #25), confirmation no deferred/retired feature was reactivated. |

Each commit is independently revertable and independently testable — no step combines "add the gateway" and "migrate a feature" in one commit. Commit #8 (Grok retirement) in particular must not be pulled earlier or merged into #2-#7: V1's gateway build-out and Grok's removal are two separately-scoped, separately-approved pieces of work.

---

## 15. Testing requirements (FINAL list)

### 15.1 Provider-call governance during migration (FINAL)

Test item 3 below enforces that no file outside `intelligence/providers/*.py` performs a direct AI-provider call. This governance has two independent parts that must never be conflated: a **temporary allowlist** for active call sites mid-migration (§15.1a), and a **permanent archived-code inventory** for historical code that is never migrated because it is already unreachable (§15.1b). An allowlist entry is evidence of *pending migration work*; an archived-code entry is evidence of *proven unreachability*. Nothing may appear in both lists at once, and nothing in either list is itself permission for a new direct provider call.

#### 15.1a Temporary active-migration allowlist (commits #2–#7)

Grok's historical call sites and any not-yet-migrated Anthropic call sites are intentionally preserved, still active, and still reachable from the running application until their own commit lands (§5, §13 decision 9, §14). Because of this, the static check in test item 3 cannot hold repo-wide during commits #2-#7. Instead, it runs against a **shrinking, exact allowlist** for the duration of commits #2-#7:

- **Allowlist entries name an exact file and function/call site — never a broad directory, module, or wildcard glob.** Starting entries: `main.py`'s Grok raw-HTTP market-sentiment call (§2, finding 7) — removed by commit #8; `services/news.py`'s Grok/OpenAI-compatible headline-classifier call (§2, finding 8) — removed by commit #8; `services/assistant.py:194`'s direct Anthropic call — removed by commit #5; `main.py:3131`'s Journal Review Anthropic call — removed by commit #6.
- **Every entry names an active, currently-reachable call site awaiting migration — never a permanently-deferred or already-archived feature.** §4's permanently-deferred features never appear on this allowlist; they are tracked in the archived-code inventory (§15.1b) instead, precisely because they are not being migrated and are not (by design) reachable in the first place.
- **No new direct provider call may ever be added to this allowlist** — it only shrinks as commits land.
- **Each migration commit that moves a call site behind the gateway removes that exact entry from the allowlist in the same commit.**
- **This allowlist must be empty by the end of commit #8**: commits #5 and #6 remove the two Anthropic entries, and commit #8 removes the remaining two Grok entries — its last members.
- **Commit #9's final audit must explicitly verify this allowlist is empty** before signing off — a non-empty allowlist at that point means unfinished migration work, not a passing state.

#### 15.1b Archived-code inventory (permanent, separate from the allowlist above)

§4's permanently-deferred features (scenario engine, performance-insight one-liner, morning brief, legacy setup grading, and the rest of §4's list) are never migrated into V1 and are never added to §15.1a's allowlist. Instead they are tracked as a permanent, exact **archived-code inventory** — specific files/call sites that are historical, preserved, and inert, not a runtime exception to the static check:

- Every entry names an exact file — e.g. `engines/engines.py`'s scenario-engine, performance-insight, morning-brief, and legacy-setup-grading Anthropic call sites — and states which prior retirement made it unreachable (most already disabled per the trading-subsystem retirement and Phase 0 safety work, commit `1514bcd`).
- Every entry must be proven unreachable from normal application startup, HTTP routes, scheduled jobs, background workers, and user-initiated actions — not asserted by description alone. Where an existing test already proves this (e.g. `test_intelligence_phase0_safety.py`'s AST-level proof, extended by test item 17), that test is the entry's proof; where no such test exists yet, one must be added before the entry is accepted into the inventory.
- Archived code must not be imported by any file reachable from active startup, routes, workers, schedules, or UI actions; must not construct or hold a live provider client; and must not be capable of initiating a network call during normal operation.
- **The archived-code inventory is never treated as permission for an active, reachable direct provider call.** It documents dead code, not a sanctioned exception.
- If a preserved historical call site cannot be reliably proven unreachable by the tests above, it does **not** qualify for this inventory — its provider imports and callable network behavior must instead be neutralized in a separately-reviewed retirement commit before V1's final audit (commit #9) can pass.
- Grok's two call sites (`main.py`, `services/news.py`) move from §15.1a (temporary allowlist, while still active) into this archived-code inventory only after commit #8 retires them — never before, and never in both lists simultaneously.

1. Provider adapter contract — every adapter implementing `ProviderAdapter` passes the same shared contract test suite (mocked).
2. One-active-provider enforcement — with `NOVA_AI_PROVIDER=anthropic` (the only valid V1 value, §5/§13 decision 9), every gateway call resolves to the Anthropic adapter and no other provider client is ever constructed.
3. **Static repo-wide check, in two independent parts (§15.1)**:
   - **(A) Active-runtime check** — no file outside `intelligence/providers/*.py`, and outside the current exact temporary allowlist (§15.1a), contains `import anthropic`, `from openai import`, or a raw `requests`/`httpx` call to a known AI-provider hostname; no `grok_adapter.py` exists anywhere in `intelligence/` at any point. Fails if the temporary allowlist contains anything beyond the exact identities recorded in §15.1a, and fails if any entry remains once commit #8 has landed.
   - **(B) Archived-code check** — every entry in the archived-code inventory (§15.1b) is confirmed unreachable from active application startup, routes, scheduled jobs, background workers, and user actions, via the specific test named in its inventory entry. Fails if any archived file is imported by active startup/routes/workers/schedules/UI, or if any archived call site can construct a live provider client or initiate a network call during normal operation.
4. Cache behavior — identical `input_data` for the same feature within the TTL window returns `cached: true`, makes zero provider calls (mocked adapter asserts call count), and never touches the daily budget state (§8.3) — a cache hit is not a provider attempt.
5. Daily request limit — the 21st provider-attempt of a day (not the 21st user-visible request — cache hits and reservation-only rejections don't count, §8.3) returns `BUDGET_EXCEEDED` without calling the provider.
6. Cost-ceiling enforcement — a request whose projected worst-case cost (§8.3) would push `accrued_cost + reserved_cost` over $0.25 returns `BUDGET_EXCEEDED` without calling the provider, even if the actual cost of prior requests turned out lower than their reservations.
7. Retry rules — a mocked transient failure retries exactly once, and that retry is reserved and settled as a **second** provider attempt against the daily budget (§8.3), not a free redo; a mocked billing/auth/quota failure never retries.
8. Circuit breaker — 3 consecutive mocked failures within the window trips `CIRCUIT_OPEN`; a request during the open window makes zero provider calls.
9. Billing-credit failure — mocked `INSUFFICIENT_CREDITS` response produces the correct `error_code` and user message, and the failure is visible (not silently swallowed) — directly extending `test_nova_review.py`'s existing coverage of this exact incident.
10. Malformed model output — a mocked response that fails schema validation produces `MALFORMED_OUTPUT`, not a crash.
11. Provider timeout — a mocked hang past §8's #3 timeout produces `TIMEOUT` behavior per §9.
12. Non-AI feature availability during provider failure — Journal CRUD, Market/News data endpoints, and app startup all succeed with the provider fully unavailable (extends the existing `test_intelligence_phase0_safety.py::test_journal_market_assistant_modules_still_import_cleanly` pattern).
13. Journal Review context boundaries — the gateway call for this feature never receives broker/execution state, only the selected trade + bounded nearby signal-log context per §3.2/§16.
14. Assistant context boundaries — the gateway call never receives broker credentials or unrelated personal data; Journal access only if §13 decision 10 allows it, and only then in the bounded form it specifies.
15. Market/News context boundaries — the gateway call never receives private Journal data unless a future explicit combined-review feature is separately specified.
16. No broker/execution access — static + runtime confirmation that no gateway code path can reach `services/execution.py` or any broker-write function.
17. No retired setup-monitor or grading integration — confirms `engines/reasoning.py::evaluate_with_claude` and `delivery/alert_engine.py::start_setup_monitor` are never called from the new gateway (extends `test_intelligence_phase0_safety.py`'s existing AST-level proof).
18. **No external API calls in unit tests** — every test in this suite runs fully mocked; a CI-style guard (e.g., a `pytest` fixture that raises if any real network socket is opened during the intelligence test module) enforces this structurally, not just by convention.
19. Model-registry fail-closed behavior — a mocked `NOVA_AI_MODEL` value with no `model_registry.py` entry produces `MODEL_NOT_SUPPORTED` (§8.2/§9) on every paid-request attempt, without ever falling through to an unverified cost calculation.
20. Persistent budget survives restart — the daily request count and estimated cost, once written to the §8.1 state file, are correctly re-read (not reset) by a freshly-started process on the same date.
21. Pre-call reservation occurs before the provider call — a mocked provider adapter asserts that `reserved_count`/`reserved_cost` are written to the budget-state file (§8.1, §8.3) *before* the mocked adapter's `call()` is ever invoked, not only after a response returns.
22. Reservation settles correctly on every outcome — (a) a successful mocked response settles `accrued_cost` to the real reported usage and releases the unused portion of the reservation; (b) a mocked failure with no reported usage (timeout/connection error) settles `accrued_cost` using the reservation's projected max cost, never zero (§8.3 step 6).
23. Concurrent-request atomicity — two simulated simultaneous requests that would each individually fit under the remaining budget, but would together exceed it, result in exactly one succeeding and one receiving `BUDGET_EXCEEDED` — never both proceeding against the same stale remaining-budget read (§8.3).
24. Budget-state failure fails closed — a simulated corrupt/unreadable budget-state file, and a simulated failure to acquire its lock, both produce `BUDGET_STATE_UNAVAILABLE` (§9) without calling the provider and without resetting the file's existing counters.
25. Allowlist-empty and archived-code final check (§15.1a/§15.1b) — commit #9's final audit re-runs check (A) with zero temporary-allowlist entries and confirms it passes, proving no legacy direct-provider call site remains active anywhere outside `intelligence/providers/*.py`; and independently re-runs check (B), confirming every archived-code inventory entry is still proven unreachable. Neither check substitutes for the other, and passing (B) never excuses a non-empty result on (A).

---

## 16. Privacy and data boundaries (FINAL)

**NOVA Assistant** may access only the context required for the user's request. Journal access is **explicit selection only** (§13 decision 10, FINAL): the Assistant may receive Journal context only when Pedro deliberately selects or attaches a specific trade — it must never automatically pull Journal history on its own. Market/News access must likewise be explicit and bounded. Never broker credentials, execution state, or unrelated personal data.

**Journal NOVA Review** may access the selected trade, limited nearby relevant journal context (the existing "8 nearest signal-log entries for this ticker" pattern from `main.py:3076-3078` is a reasonable bound to carry forward), and approved historical statistics — never a full journal/database dump.

**Market/News Summary** may access existing stored headlines and approved market data only — never private Journal data, unless a future, separately-specified combined-review feature is explicitly built and approved.

**Never included in any prompt, log, or envelope, for any feature:** API keys, authentication tokens, broker credentials, environment-secret values, unbounded logs, or unrelated user data.

---

## Summary: what's locked

**Final (structure, scope, and all ten decisions locked):** the three V1 features and their boundaries (§3), the deferred-list (§4), Grok's full retirement from active V1 architecture with historical code preserved for a separate future commit (§5), the one-active-provider rule (§7.2), the cost-control numbers, persistent-budget design, and atomic pre-call reservation (§8, §8.1, §8.2, §8.3), the error-code vocabulary including `MODEL_NOT_SUPPORTED` and `BUDGET_STATE_UNAVAILABLE` (§9), the never-log-raw-response rule applying to `MALFORMED_OUTPUT` with no exceptions (§9, §12), the configuration variable names and locked defaults (§10), the response envelope shape (§11), the observability exclusions (§12), all ten of Pedro's final decisions (§13), the migration commit sequence with Grok removal isolated to its own later, separately-approved commit (§14), the full test list including the shrinking temporary active-migration allowlist that must reach zero by commit #8, kept strictly separate from the permanent archived-code inventory of already-unreachable deferred features (§15, §15.1a, §15.1b), and the privacy boundaries including Assistant Journal-access being explicit-selection-only (§16).

**Still requiring separate future approval before it happens:** nothing in V1's own scope — but commit #2 onward in §14 (writing any `intelligence/` code) still requires Pedro's go-ahead per commit, and Grok's actual removal (§14 commit #8) is explicitly a separate, later, separately-approved piece of work, not part of this specification's authorization.

Nothing in this document authorizes writing `intelligence/` code. Commit #2 in §14 is the next step, and only after Pedro reviews and approves this specification as a whole — the same gate every other spec in this project has required.
