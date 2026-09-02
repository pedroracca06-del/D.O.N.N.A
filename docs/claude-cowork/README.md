# NOVA Claude/Cowork — Operating Architecture

## Purpose

This directory defines how Claude Code (and any future "Cowork" automation) is
allowed to operate on the NOVA repository: what runs unattended, what requires an
approval naming exact targets, what is always Pedro's decision, and what is never
permitted at all.

The governing rule is one sentence:

> Automation may **observe, analyse, propose, and verify** without asking.
> It may **mutate** only after an explicit approval that names exactly what will
> change. It may **never** perform an outward-facing or irreversible action.

Everything in these documents is an application of that rule.

## Document index

| Document | Answers |
|---|---|
| [APPROVAL_MATRIX.md](APPROVAL_MATRIX.md) | For a given action, what approval is required? |
| [AUTOMATION_ARCHITECTURE.md](AUTOMATION_ARCHITECTURE.md) | Actors, source-of-truth split, worktree model, session registry, evidence gates, Obsidian, Brain/Trader handoff |
| [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md) | What is built, what is next, and each item's approval gate |
| [PHASED_IMPLEMENTATION_ORDER.md](PHASED_IMPLEMENTATION_ORDER.md) | In what order, with what exit criteria |
| [RESPONSIBILITY_CONTRACT.md](RESPONSIBILITY_CONTRACT.md) | Who owns what, and the invariants that never bend |

## Completed foundation

The following is done and verified. Each claim below was measured, not assumed.

| Item | State |
|---|---|
| Retirement guard | Installed at `.claude/hooks/nova_guard_hook.py`, wired via `.claude/settings.json`, **committed and pushed** to `retirement/disable-legacy-trading` |
| Guard test suite | **188 checks, 188 passed, 0 failed** (`python -B .claude/hooks/test_nova_guard_hook.py`) |
| Local permissions | Reduced to **338 allow / 31 ask / 8 deny**, installed and validated in two stages |
| Runtime artifacts | Ignored via `.gitignore` — runtime JSON, `data/` scratch files, and raw transcripts are hidden but **preserved on disk** |
| Primary checkout | Clean — `git status --porcelain` and `-uall` both empty |
| Foundation worktree | Created as a sibling of the primary checkout, on branch `integration/nova-foundation` |
| Knowledge-core casing | Normalized to lowercase `nova_knowledge_core/` — 69 path-only renames, zero content change |
| `CLAUDE.md` | Refreshed: retirement boundary, modular UI, `intelligence/`, test commands, worktree and permission guidance, responsibility boundaries |
| Pytest discovery | `pytest.ini` pins `testpaths = tests`; collection parity verified at 926 node IDs |

**The casing normalization, `CLAUDE.md` refresh, and `pytest.ini` exist only on
`integration/nova-foundation`. That branch has not been merged and has not been
pushed.** Only the guard and the ignore rules are on a remote branch.

## Immediate next automation sequence

1. ~~**Evidence Formatter**~~ — **implemented locally** as `tools/cowork/evidence_formatter.py` (53 tests). Deterministic, executes nothing, writes no file, derives overall status from the checks rather than trusting a caller. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b11-evidence-formatter--implemented).
2. ~~**Staleness Guard**~~ — **implemented locally** as `tools/cowork/staleness_guard.py` (61 tests). Re-measures branch, HEAD, refs, index, worktree, tracked blobs, permission hash and counts, gitlinks, and worktree identity against an explicit baseline. Local-only by default; `--check-remote` reads refs via `git ls-remote` without fetching, proven not to touch FETCH_HEAD, refs, index, or config. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b12-staleness-guard--implemented).
3. ~~**A7 battery**~~ — **implemented locally** as `tools/cowork/a7_battery.py` with the versioned `a7_policy.json` (84 tests). Seven gates: scope integrity, secrets, machine paths, protected boundary, runtime/generated/copyright, baseline staleness, and test-evidence parity. Every gate was demonstrated **failing** on planted input. A declared protected change yields exit 5 (approval required) rather than a silent pass. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b13-a7-battery--implemented).
4. ~~**Session Registry**~~ — **implemented locally** as `tools/cowork/session_registry.py` (104 tests). Detects worktree, branch, and scope collisions between concurrent sessions; live collisions block, stale or ambiguous ones escalate to you. It never deletes a record — `close` marks history. `advance` moves an active session's pinned commit forward after a reviewed local commit: the destination is always the verified HEAD, it must be a descendant of the recorded commit, and there is no force or rewind. Advancing records where a session sits — it approves nothing and never pushes, merges, or deploys. The real registry has been initialized under separate approval; each write remains your decision. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b14-session-registry--implemented-tool-only-registry-not-initialized).
5. ~~**Worktree bootstrap validator**~~ — **implemented locally** as `tools/cowork/worktree_bootstrap_validator.py` (86 tests). Answers one question before an automated session begins: is this worktree safely configured for its declared role? It checks identity, cleanliness, tracked content, local and permission state, path casing, submodules, forbidden inherited artifacts, and registry compatibility against an explicit manifest. Tracked files are compared **by Git blob id**, so `core.autocrlf` cannot cause a false failure. It observes only — it never creates, removes, repairs, populates, or registers anything, and every Git call reuses the A7 battery's existing read-only allowlist rather than adding a new capability. Nine planted cases were demonstrated, and against the real foundation worktree it returns exit 0 with 30 checks passing. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b15-worktree-bootstrap-validator--implemented-tool-local-only).

All five are read-only in effect. Items 1-3 and 5 are done locally, and item 4's tool is done locally with its registry initialized under separate approval. Nothing beyond them is scheduled, and nothing here is pushed or merged.

## What this documentation does not do

Nothing here authorizes trading, deployment, merging, pushing, or autonomous
execution. These documents describe boundaries; they grant no permission. Every
mutating or outward-facing action still requires Pedro's approval at the moment it
is proposed.
