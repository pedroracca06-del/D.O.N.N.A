# NOVA Intelligence V1 — Architecture Specification

Date: 2026-07-20
Status: **Specification only. No implementation code exists yet.** This document designs one centralized, provider-independent intelligence layer for NOVA, replacing the six-plus disconnected Claude/Grok call sites documented in the read-only AI-architecture audit. Phase 0 safety and cost containment is complete (commit `1514bcd`) — the retired setup-monitor no longer auto-starts, and the health check no longer makes a billable Anthropic call. This document does not authorize implementation; each migration commit in §12 requires Pedro's separate approval, same discipline as the Market Map V1 track.

Claude may continue helping write this system's code in Codespaces. **NOVA itself must not depend on Claude specifically to operate** — the entire point of this layer is that the active provider is a configuration value, not a hardcoded dependency.

---

## 0. Requirements status key

- **FINAL** — Pedro has explicitly locked this; no re-approval needed.
- **PROPOSED** — a default this document recommends; requires Pedro's explicit approval before implementation (see §13, the approval table).
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
- May explain Journal and Market/News information.
- Must not generate canonical trades, BUY/SELL signals, execution instructions, grades, or alerts.

### 3.2 Journal NOVA Review
- User-initiated analysis of a selected trade.
- May identify discipline, risk-management, execution, and behavioral patterns.
- Must preserve historical Journal data.
- Must not depend on retired strategy fields to function — historical legacy fields (`pros_phase`, `ib_draw`, `nova_cmd`, grade, etc., per the current `main.py:3070-3090` signal-context block) may remain **readable** as historical context but must never **control** whether or how the review runs.

### 3.3 Market/News Summary
- User-initiated or explicitly scheduled only — never silent background polling.
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

## 5. Grok direction (PROPOSED)

Grok is **not** an independently active second brain in V1. The two existing implementations (`main.py`'s raw HTTP call, `services/news.py`'s `openai`-SDK call) are both slated for retirement or routing through the central gateway — never both kept as-is.

**V1 default (PROPOSED):**
- No automatic Grok calls of any kind.
- The Market/News **feed itself** (headlines, calendar, risk state — all deterministic ingestion) is preserved untouched; only the AI-summarization layer on top of it is affected.
- Deterministic news processing is used wherever it's sufficient — risk classification, calendar parsing, etc. do not need an LLM and should not route through the gateway just because one exists.
- Any *optional* AI news summary in V1 uses the **same single active provider** as the rest of NOVA (§7) — not a Grok-specific path.
- After migration, **no provider-specific application code remains** — `openai`, `requests.post('https://api.x.ai/...')`, and direct `anthropic` imports are removed from every feature file, existing only inside the gateway's provider adapters (§6).

Whether Grok is retired completely or preserved as a future optional adapter behind the gateway is Pedro's call — see §13, decision 9.

---

## 6. Central gateway module structure (PROPOSED)

```
intelligence/
├── __init__.py
├── gateway.py            # request_intelligence() -- the one application-facing entry point
├── config.py              # centralized env-var reads for this layer only (§10)
├── registry.py            # feature registry: maps feature name -> template + schema + limits
├── envelope.py             # shared response envelope dataclass/schema (§11)
├── errors.py               # error_code enum + controlled-error construction (§9)
├── budget.py               # daily request count + estimated-cost ceiling + circuit breaker (§8)
├── cache.py                # input-hash response cache, per-feature TTL (§8.6-8.7)
├── audit.py                # usage/observability logging, secret-safe (§12)
├── providers/
│   ├── __init__.py
│   ├── base.py             # ProviderAdapter interface (§6.1)
│   ├── anthropic_adapter.py
│   └── grok_adapter.py     # present but inert unless explicitly configured active (§5, §7)
└── prompts/
    ├── assistant.py         # NOVA Assistant prompt template + input/output schema
    ├── journal_review.py    # Journal NOVA Review prompt template + input/output schema
    └── market_summary.py    # Market/News Summary prompt template + input/output schema
```

### 6.1 Responsibilities

| Module | Responsibility |
|---|---|
| `gateway.py` | The only function application code calls: `request_intelligence(...)` (§7.1). Resolves the active provider, loads the feature's template/schema/limits from the registry, checks the budget, checks the cache, calls the provider adapter, wraps the result in the response envelope, writes the audit log entry. Contains no feature-specific knowledge and no provider-specific knowledge. |
| `config.py` | Reads every env var in §10. Nowhere else in the codebase reads an AI-related env var directly once migration (§12) completes. |
| `registry.py` | A single dict/table mapping each of the three V1 feature names to its prompt template module, its input/output schema, its `max_tokens`, its cache TTL, and its timeout — the one place a new feature is "turned on." |
| `envelope.py` | Defines the shared response shape (§11) every gateway call returns, success or failure. |
| `errors.py` | Defines the fixed `error_code` vocabulary (§9) and maps provider-specific exceptions to it — the only place that translates "Anthropic raised X" into "NOVA means Y." |
| `budget.py` | Daily request counter, optional daily estimated-cost ceiling, and the circuit breaker (§8.10) — provider-agnostic, keyed by feature and by day. |
| `cache.py` | Input-hash keyed cache (hash of feature + normalized input_data), reusing the existing `core.config.CACHE`/`cache_get`/`cache_set` TTL pattern already used elsewhere in the codebase rather than introducing a second caching mechanism. |
| `audit.py` | Writes the observability log (§12) to a new `nova_intelligence_usage_log.json`-style file, following the existing `_data_file()` naming convention in `core/config.py`. |
| `providers/base.py` | Defines the `ProviderAdapter` interface every adapter must implement: `call(prompt, max_tokens, timeout) -> AdapterResult` (raw text/structured output + token usage), nothing feature-specific. |
| `providers/anthropic_adapter.py`, `providers/grok_adapter.py` | Thin wrappers around each SDK, implementing `ProviderAdapter`. These are the **only** files in the entire codebase permitted to `import anthropic` or construct a Grok/OpenAI-compatible client. |
| `prompts/*.py` | One file per V1 feature: builds the prompt from `input_data`, defines the expected output schema, and parses the raw provider response back into `structured_data`. This is where each of the three existing prompt bodies (from `services/assistant.py`, `main.py:3092-3123`, and a new deterministic-first market-summary prompt) land, unmodified in substance — moved, not rewritten, per the migration plan's "one feature per commit" rule (§12). |

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
- Changing providers is a configuration change (`NOVA_AI_PROVIDER=anthropic` → `grok`, or whatever is added later) — never a code change in feature files, since feature files only ever call `request_intelligence()`.
- If the configured provider is unavailable (missing key, auth failure, quota, etc.), `request_intelligence()` returns `success: false` with a specific `error_code` (§9) — it never falls back and never fabricates a response.
- **NOVA's non-AI features must keep working** when the provider is down — Journal CRUD, Market/News data display, and everything else not listed in §3 has zero dependency on the gateway and is unaffected by any AI outage.

---

## 8. Cost-control requirements (PROPOSED defaults, FINAL structure)

| # | Control | Proposed default | Notes |
|---|---|---|---|
| 1 | Per-feature max output tokens | Assistant 400 · Journal Review 800 · Market Summary 500 | Matches the token budgets already in use today (`services/assistant.py` uses 400, `main.py:3135` uses 800) — carried forward, not invented. |
| 2 | Max input/context size | ~4,000 tokens per feature (rough char-count guard, not exact tokenization) | Prevents an unbounded prompt (e.g., a huge nearby-signal-log dump) from silently ballooning cost. |
| 3 | Request timeout | 30 seconds | Matches the existing Grok call's `timeout=30` (`main.py:238`); Anthropic SDK calls currently have no explicit timeout — this closes that gap. |
| 4 | Retry policy | At most **one** controlled retry, transient errors only (timeout, 5xx, connection error) | |
| 5 | No-retry errors | Billing, authentication, quota/rate-limit errors never retry | Retrying a billing failure just wastes another attempt on a request that cannot succeed — matches the real incident documented in `tests/test_nova_review.py` (Anthropic credit exhaustion). |
| 6 | Response caching | Input-hash keyed, per §6.1's `cache.py` | Reuses `core.config.CACHE` pattern. |
| 7 | Cache duration by feature | Assistant: **no cache** (conversational, each message is distinct) · Journal Review: 24h (a trade's facts don't change) · Market Summary: 15–30 min (PROPOSED, pending Pedro's approval range in §13) | |
| 8 | Daily request limit | PROPOSED default 50/day total across all three features, configurable | Pedro's exact number is an open decision (§13, decision 4). |
| 9 | Daily estimated-cost ceiling | PROPOSED, optional, off by default until Pedro sets a number (§13, decision 5) | Computed from each response's reported token usage × the active provider's published per-token rate (a small static rate table in `budget.py`, updated manually when pricing changes — not fetched live). |
| 10 | Circuit breaker | PROPOSED: 3 consecutive failures for the same feature within 5 minutes trips the breaker for that feature for 15 minutes, returning a controlled error immediately without attempting the provider | Prevents hammering a down/exhausted provider. |
| 11 | No background AI calls by default | FINAL, matches §3's "user-initiated only" requirement for all three features | |
| 12 | Every paid request traceable to a visible user action or explicitly approved schedule | FINAL | No feature may originate a gateway call from a passive page-load or polling loop. |
| 13 | Usage logging without secrets | FINAL, see §12 | |
| 14 | Clear "AI unavailable" user-facing behavior | FINAL, see §9 | |
| 15 | Non-AI NOVA features continue when budget exhausted | FINAL, same guarantee as §7.2's provider-down case | |

---

## 9. Error behavior (FINAL structure, one `error_code` per condition)

| `error_code` | Condition | User-facing behavior |
|---|---|---|
| `PROVIDER_NOT_CONFIGURED` | No API key set for the active provider | "AI features are not configured right now." No retry. |
| `AUTH_FAILED` | Provider rejects the API key | Same user message as above (no key-detail leakage). No retry. |
| `INSUFFICIENT_CREDITS` | Billing/quota exhausted (the exact incident `test_nova_review.py` documents) | "AI credits are unavailable right now — try again later." No retry. |
| `RATE_LIMITED` | Provider 429 | "AI is temporarily busy — try again in a moment." No retry (rate limits need real backoff time, not an immediate retry). |
| `TIMEOUT` | Request exceeded §8.3's timeout | One retry per §8.4, then the same user message as rate-limited if the retry also times out. |
| `INVALID_PROVIDER_RESPONSE` | Non-2xx or empty response body | Generic "AI request failed" message. No retry beyond §8.4's transient-error allowance. |
| `MALFORMED_OUTPUT` | Response received but fails schema validation (e.g., NOVA Review's expected section structure) | Generic failure message; the raw response is logged (with prompt/content still excluded per §12) for debugging, never shown raw to the user. |
| `BUDGET_EXCEEDED` | Daily request or cost ceiling hit | "Today's AI usage limit has been reached." No retry, no override without a config change. |
| `CIRCUIT_OPEN` | §8.10's breaker is tripped for this feature | "AI is temporarily unavailable — try again shortly." |

Every error is surfaced to the user through the existing UI error-handling paths already established during the UI retirement work (e.g., the `_novaReviewError()` toast pattern `test_nova_review.py` already covers) — never a silent empty response, never an infinite retry loop, and never a crash that takes down Journal or Market/News alongside it.

---

## 10. Configuration (PROPOSED variable names, no secret values)

| Variable | Purpose |
|---|---|
| `NOVA_AI_PROVIDER` | Active provider: `anthropic` \| `grok` \| (future). Single source of truth for §7.2's one-active-provider rule. |
| `NOVA_AI_API_KEY` | The active provider's API key — **one** variable, not one per provider, since only one is ever active. (Superseded, once migration completes: `ANTHROPIC_API_KEY` / `GROK_API_KEY` become internal to their adapters, read only when that adapter is selected, not duplicated at the application level like `GROK_API_KEY` is today between `main.py` and `services/news.py`.) |
| `NOVA_AI_MODEL` | Default model for the active provider. |
| `NOVA_AI_REASONING_MODEL` | Optional higher-reasoning model, only used if a future feature explicitly requests it (none of the three V1 features do by default) — whether this exists at all in V1 is Pedro's call (§13, decision 3). |
| `NOVA_AI_DAILY_REQUEST_LIMIT` | §8.8. |
| `NOVA_AI_DAILY_COST_LIMIT_USD` | §8.9, optional. |
| `NOVA_AI_REQUEST_TIMEOUT_SECONDS` | §8.3, default 30. |
| `NOVA_AI_CACHE_ENABLED` | Boolean master switch for §8.6-8.7 (per-feature TTLs still come from the registry, not a second env var each). |
| `NOVA_AI_LOG_LEVEL` | Controls §12's logging verbosity (e.g., `INFO` vs `DEBUG` — `DEBUG` still never logs full prompts, per §12's hard rule). |

This intentionally **replaces** `ANTHROPIC_MODEL` and `ANTHROPIC_ASSISTANT_MODEL` (two separate model vars for no longer-relevant reasons — one was for the retired grading pipeline) with a single `NOVA_AI_MODEL`, and eliminates the duplicated `GROK_API_KEY` read between `main.py` and `services/news.py` (§2, finding 7/8) in favor of one key for whichever provider is active. No provider gets its own always-present env var block; only the active provider's adapter reads its provider-specific variable name internally.

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
- Estimated cost, when calculable from §8.9's static rate table

**Hard exclusion, no exceptions:** complete prompts and complete responses are never logged by default, at any `NOVA_AI_LOG_LEVEL`. If deep debugging of a malformed-output incident is ever needed, that requires a separate, explicit, temporary debug flag reviewed by Pedro before use — not a standing log level.

---

## 13. Open decisions for Pedro — do not choose silently

| # | Decision | Notes |
|---|---|---|
| 1 | First active runtime provider | Anthropic (current, working) is the obvious default, but this is Pedro's call, not assumed. |
| 2 | Default model | Carry forward `claude-sonnet-4-6` (current `ANTHROPIC_ASSISTANT_MODEL`)? Or a cheaper default given the "low and predictable operating cost" goal? |
| 3 | Allow a separate higher-reasoning model | None of the three V1 features currently request one — is `NOVA_AI_REASONING_MODEL` built into V1 at all, or deferred until a feature actually needs it? |
| 4 | Daily request limit | §8.8 proposed 50/day as a strawman only. |
| 5 | Daily estimated-cost ceiling | §8.9 — off by default; what number, if any? |
| 6 | Journal Review cache duration | §8.7 proposed 24h. |
| 7 | Market/News Summary cache duration | §8.7 proposed 15–30 min range, needs a specific number. |
| 8 | Market/News summaries: manual-only forever, or may later be scheduled | §3.3 requires "explicitly scheduled only" if ever automated — confirm whether V1 ships manual-only with scheduling deferred, or whether a specific schedule is wanted now. |
| 9 | Grok's fate | Retired completely (both existing implementations removed after migration), or preserved as a future optional adapter behind the gateway (§5, §6's `grok_adapter.py` present-but-inert)? |
| 10 | Assistant's Journal-context access | May the Assistant automatically pull Journal context when relevant, or must the user explicitly select/attach a trade every time (tighter privacy boundary, matches §3.2's "explicit and bounded" language for Journal access in general)? |

---

## 14. Migration plan — one small commit at a time (FINAL sequence, PROPOSED granularity)

No commit beyond #1 (this document) happens without Pedro's separate go-ahead, matching the Market Map V1 track's discipline.

| # | Commit | Scope |
|---|---|---|
| 1 | `Define NOVA Intelligence V1 specification` | This document only — no code. |
| 2 | Central gateway interfaces + configuration | `intelligence/gateway.py`, `config.py`, `registry.py`, `envelope.py`, `errors.py` skeletons — no live provider call yet, no feature migrated. |
| 3 | Provider adapter with mocked tests | `providers/base.py` + one adapter (whichever provider is decided in §13.1), fully unit-tested with mocks — zero real API calls in tests (§15.18). |
| 4 | Usage limits, caching, and error handling | `budget.py`, `cache.py`, `audit.py` wired into `gateway.py`. |
| 5 | Migrate NOVA Assistant | `services/assistant.py` calls `request_intelligence("assistant", ...)` instead of `core.config.client` directly; old path removed once verified. |
| 6 | Migrate Journal NOVA Review | `main.py`'s `/journal/analyze` calls the gateway instead of `core.config.client` directly. |
| 7 | Migrate Market/News Summary | New feature built against the gateway from the start (no legacy path to replace, since today's Grok calls are separate features being retired, not migrated in place). |
| 8 | Remove/archive superseded direct AI call paths | Delete or archive (matching the trading-subsystem retirement's "archive, don't delete" precedent where historically meaningful) the now-dead direct-import code in `main.py` (Grok raw HTTP), `services/news.py` (Grok via `openai`), and confirm `engines/engines.py`'s deferred features (§4) are left alone, not touched. |
| 9 | Final cost, security, and regression audit | Full test suite, a real (small, Pedro-approved) live smoke test of all three migrated features, confirmation of §15's full test list, confirmation no deferred/retired feature was reactivated. |

Each commit is independently revertable and independently testable — no step combines "add the gateway" and "migrate a feature" in one commit.

---

## 15. Testing requirements (FINAL list)

1. Provider adapter contract — every adapter implementing `ProviderAdapter` passes the same shared contract test suite (mocked).
2. One-active-provider enforcement — configuring `NOVA_AI_PROVIDER=anthropic` never results in a Grok call, and vice versa; no code path contacts both.
3. **Static repo-wide check**: no file outside `intelligence/providers/*.py` contains `import anthropic`, `from openai import`, or a raw `requests`/`httpx` call to a known AI-provider hostname — the same style of static audit used throughout this project's retirement work (`grep`-based, run as a test).
4. Cache behavior — identical `input_data` for the same feature within the TTL window returns `cached: true` and makes zero provider calls (mocked adapter asserts call count).
5. Daily request limit — the (N+1)th request in a day returns `BUDGET_EXCEEDED` without calling the provider.
6. Cost-ceiling enforcement — same shape as #5, keyed on estimated cost instead of count.
7. Retry rules — a mocked transient failure retries exactly once; a mocked billing/auth/quota failure never retries.
8. Circuit breaker — 3 consecutive mocked failures within the window trips `CIRCUIT_OPEN`; a request during the open window makes zero provider calls.
9. Billing-credit failure — mocked `INSUFFICIENT_CREDITS` response produces the correct `error_code` and user message, and the failure is visible (not silently swallowed) — directly extending `test_nova_review.py`'s existing coverage of this exact incident.
10. Malformed model output — a mocked response that fails schema validation produces `MALFORMED_OUTPUT`, not a crash.
11. Provider timeout — a mocked hang past §8.3's timeout produces `TIMEOUT` behavior per §9.
12. Non-AI feature availability during provider failure — Journal CRUD, Market/News data endpoints, and app startup all succeed with the provider fully unavailable (extends the existing `test_intelligence_phase0_safety.py::test_journal_market_assistant_modules_still_import_cleanly` pattern).
13. Journal Review context boundaries — the gateway call for this feature never receives broker/execution state, only the selected trade + bounded nearby signal-log context per §3.2/§16.
14. Assistant context boundaries — the gateway call never receives broker credentials or unrelated personal data; Journal access only if §13 decision 10 allows it, and only then in the bounded form it specifies.
15. Market/News context boundaries — the gateway call never receives private Journal data unless a future explicit combined-review feature is separately specified.
16. No broker/execution access — static + runtime confirmation that no gateway code path can reach `services/execution.py` or any broker-write function.
17. No retired setup-monitor or grading integration — confirms `engines/reasoning.py::evaluate_with_claude` and `delivery/alert_engine.py::start_setup_monitor` are never called from the new gateway (extends `test_intelligence_phase0_safety.py`'s existing AST-level proof).
18. **No external API calls in unit tests** — every test in this suite runs fully mocked; a CI-style guard (e.g., a `pytest` fixture that raises if any real network socket is opened during the intelligence test module) enforces this structurally, not just by convention.

---

## 16. Privacy and data boundaries (FINAL)

**NOVA Assistant** may access only the context required for the user's request; Journal or Market/News access must be explicit and bounded (per §13 decision 10); never broker credentials, execution state, or unrelated personal data.

**Journal NOVA Review** may access the selected trade, limited nearby relevant journal context (the existing "8 nearest signal-log entries for this ticker" pattern from `main.py:3076-3078` is a reasonable bound to carry forward), and approved historical statistics — never a full journal/database dump.

**Market/News Summary** may access existing stored headlines and approved market data only — never private Journal data, unless a future, separately-specified combined-review feature is explicitly built and approved.

**Never included in any prompt, log, or envelope, for any feature:** API keys, authentication tokens, broker credentials, environment-secret values, unbounded logs, or unrelated user data.

---

## Summary: what's approved vs. what's open

**Final (structure and scope locked):** the three V1 features and their boundaries (§3), the deferred-list (§4), the one-active-provider rule (§7.2), the error-code vocabulary (§9), the response envelope shape (§11), the observability exclusions (§12), the migration commit sequence (§14, though exact commit count may flex slightly during implementation), and the full test list (§15).

**Proposed, awaiting approval (§13's ten decisions):** first provider, default model, whether a reasoning-model tier exists in V1 at all, the daily request limit, the daily cost ceiling, Journal Review and Market Summary cache durations, whether Market/News scheduling is ever allowed, Grok's ultimate fate, and how much Journal context the Assistant may access automatically.

Nothing in this document authorizes writing `intelligence/` code. Commit #2 in §14 is the next step, and only after Pedro reviews and approves this specification as a whole — the same gate every other spec in this project has required.
