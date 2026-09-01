# NOVA — Codebase Guide

AI-native **market intelligence** system for MES/ES and MNQ/NQ futures.
FastAPI backend + Claude AI + TradingView MCP.

> **The legacy trading/execution subsystem is RETIRED.** NOVA currently observes,
> reasons, and reports. It does not trade. Read *Retirement boundary* below before
> touching anything execution-related.

---

## Current application state

**Active surfaces** — Overview, Markets/News, Journal, Settings, and the NOVA
Assistant.

**Retired surfaces** — the legacy H.A.R.V.E.Y / Market Reality trading tab, the
legacy strategy-alert pipeline, and the legacy execution/broker surfaces. That
code is archived, not deleted; see
`nova_knowledge_core/TRADING_SUBSYSTEM_RETIREMENT_AUDIT.md`,
`TRADING_SUBSYSTEM_DISABLEMENT.md`, and `TRADING_SUBSYSTEM_UI_RETIREMENT.md`.

**Interface layout** — the UI is modular:

```
ui/pages/          overview.py · market_news.py · journal.py · nova_ai.py · settings.py
ui/scripts.py      client-side behavior
ui/styles.py       styling
ui/html.py         thin composition layer that assembles the above
```

`ui/html.py` is no longer the monolith it once was — treat it as composition only.
Beware the historical fragility of Python triple-quoted strings containing JS: use
`\\'` or `data-*` attributes, never a bare `\'`.

---

## Retirement boundary

Two flags gate the retired subsystem. **Neither may ever be set to an enabling
value** (`true`, `1`, `yes`, `on`, `enabled`):

- `NOVA_TRADING_SUBSYSTEM_ENABLED` — master kill switch (`core/config.py`, default false)
- `NOVA_AUTO_EXECUTE`

A **PreToolUse retirement guard is installed** at `.claude/hooks/nova_guard_hook.py`,
wired through `.claude/settings.json`. It blocks modification of Tier 1 files
(`services/execution*.py`, `core/config.py`, `tests/conftest.py`), blocks
kill-switch edits and whole-file replacement of `main.py` / `monitor.py`, and
blocks any recognized assignment that would enable a guarded flag.

**If the guard blocks you, report it — never bypass, disguise, split, or disable
it.** For a Tier 2 file it will direct you to the Edit tool instead of a shell
mutation; that is the sanctioned path.

The guard is one mechanical layer, not a complete guarantee. It enforces the
retired-subsystem boundary, the protected file list, and the activation flags. It
does **not** by itself prevent every possible form of influence on trading — that
also depends on approval policy, worktree separation, ownership boundaries, and
deterministic risk/execution design.

Run the guard's own suite:

```bash
python -B .claude/hooks/test_nova_guard_hook.py
```

---

## How to run

```bash
# Backend (Render-deployed, or local dev)
uvicorn main:app --reload --port 8000
# Dashboard → http://localhost:8000/dashboard
```

`scripts/start_trading_session.ps1` still exists but no longer launches
`monitor.py`, and explicitly forces `NOVA_TRADING_SUBSYSTEM_ENABLED=false`.

---

## Repository map

| Path | Role |
|---|---|
| `main.py` | FastAPI entry point — routes, background loops, market data |
| `intelligence/` | Provider-independent AI gateway — `gateway.py`, `registry.py`, `model_registry.py`, `budget.py`, `cache.py`, `audit.py`, `envelope.py`, `providers/`, `prompts/` |
| `engines/` | `reasoning.py` (intelligence pipeline), `engines.py`, `analytics.py`, `risk_engine.py`, `signals.py`, `native_shadow.py`, market-context engines |
| `services/` | `assistant.py`, `news.py`, `finnhub.py`, `headlines.py`; plus retired `execution*.py` (Tier 1 — guarded) |
| `core/` | `config.py` (constants, env, kill switch), `state.py`, `state_engine.py` |
| `delivery/` | `alert_engine.py`, `macro_discord.py`, `signal_log.py` |
| `health/` | `health.py` — subsystem health checks |
| `ui/pages/` | One module per active page (see *Current application state*) |
| `indicators/` | Pine Script — `nova_market_map_v1.pine`, `nova_execution_v1.pine` |
| `mcp/tradingview` | Node.js MCP server (git submodule → `pedroracca06-del/tradingview-mcp`) |
| `nova_knowledge_core/` | Strategy rules, methodology, retirement audits. **Lowercase is canonical.** |
| `nova_ui_vision/` | UI design philosophy, navigation architecture, mockups |
| `tests/` | Test suite |
| `docs/` | Technical documentation |
| `scripts/` | Windows PowerShell ops scripts |
| `.claude/hooks/` | Retirement guard and its test harness |
| `data/` | Runtime JSON, auto-generated. Ignored except `donna_settings.json` |
| `monitor.py` | Local session monitor (Tier 2 — guarded) |

---

## Tests

```bash
# Full suite
python -B -m pytest tests -q

# Retirement guard suite
python -B .claude/hooks/test_nova_guard_hook.py

# Focused, by explicit path
python -B -m pytest tests/test_ui_modularization.py -q
```

**Never claim a test result you did not measure.** Any statement that tests pass
must carry the exact command, the counts, and any failures. Where a suite has
pre-existing failures, record them as an observed baseline for that run — a known
failure is never a licence to wave through a new one.

**Never weaken a test to make a change pass.** If a test blocks you, either the
change is wrong or the test needs a deliberate, separately approved update.

---

## Git and worktree safety

- **Stage by exact path only.** Never `git add .`, `git add -A`, or a bare
  directory path — runtime JSON and scratch artifacts live inside the tree.
- **Answer permission prompts with "Allow once."** Never select a permanent
  "don't ask again" approval.
- **Push, merge, deploy, rebase, reset, restore, clean, and any permission or
  settings change require Pedro's explicit approval, every time.** Approval for
  one action never extends to the next.
- **Worktrees are separate working directories over one shared object store.** Do
  not mix work between them or copy files across casually — move work as commits
  (`git format-patch` / `git cherry-pick`).
- **`.claude/settings.local.json` is git-ignored and therefore per-worktree.** A
  new worktree starts without it; install and verify it explicitly, checking its
  hash and allow/ask/deny counts rather than assuming them.
- `core.autocrlf=true` here: a fresh worktree materializes CRLF while an older
  checkout may hold LF, so **raw file hashes can differ across worktrees for
  identical content**. Compare `git rev-parse HEAD:<path>` instead.

---

## Responsibility boundaries

- **Pedro** owns approval, strategy, risk, capital, and deployment authority.
- **Claude** owns engineering, maintenance, tests, documentation, and proposals.
- **Obsidian** is a non-executing knowledge store.
- **NOVA Brain** provides financial analysis and decision support; it cannot
  submit orders.
- **NOVA Trader** (future) is deterministic policy, constrained by an independent
  risk engine it cannot override.
- **The execution engine** handles broker mechanics only; it never originates a
  decision.
- **LLM output stays outside the live order path.** An LLM may explain an order;
  it may never be a link in the chain that creates one.

**Nothing in this repository authorizes autonomous or funded trading.**

---

## Preservation rules

- Raw third-party transcripts stay local and git-ignored, pending a copyright
  decision. Derived summaries and analysis are tracked normally.
- Runtime data under `data/` stays local and git-ignored. Do not delete it to
  "clean up" — it is live state and validation evidence.
- **Research does not become an active NOVA rule without Pedro's explicit
  approval.** Ingested material stays in a quarantined layer.
- Archived **Execution Bot Phase 8** is preserved but **not approved and not
  active**. Do not activate it, merge it into retirement work, or treat it as
  sanctioned trading-bot development.

---

## Critical patterns

**State-first architecture** — intelligence flows from computed state objects,
never invented in the UI: `compute_macro_state()` → macro panel, and so on.

**Deterministic before AI** — Claude is called only when a deterministic engine
detects something real. No speculative AI calls.

**CDP port** — TradingView launches with `--remote-debugging-port=9222`, via the
`TV_CDP_PORT` env var (default 9222).

---

## Runtime state (data/)

All runtime JSON lives in `data/` and is git-ignored except `donna_settings.json`.
Key files include `donna_risk_state.json` (market snapshot, VIX, macro risk),
`donna_journal.json` (trade records), `donna_macro_events.json` (economic
calendar), and `donna_settings.json` (user display preferences).

---

## Environment variables

See `.env.example` for the full list. Never commit real values, and never print a
credential value in output or logs.

---

## Deployment

- **Render** — cloud backend (`uvicorn main:app`), auto-deploys on push to `main`.
- **Local** — TradingView MCP tooling and ops scripts.

Because Render deploys on Linux, **path casing is significant there even though
Windows hides it locally.** Keep `nova_knowledge_core/` lowercase everywhere.
