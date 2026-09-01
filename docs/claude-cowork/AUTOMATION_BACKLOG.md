# Automation Backlog

Every item carries an ID, owner, automation class, mutation scope, prerequisites,
evidence required, approval gate, and status.

Classes are defined in [APPROVAL_MATRIX.md](APPROVAL_MATRIX.md): **FA** fully
automatic · **AR** automatic read-only · **AAM** approval before mutation ·
**AM** always manual.

---

## Tier 0 — Completed foundation

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| P0.1 | Install the corrected retirement guard | Claude | AAM | `.claude/hooks/**` | Validated candidate | Guard suite counts; installed hashes | Per-commit | **DONE** — installed, committed, **pushed** |
| P0.2 | Guard test harness | Claude | AR | none | P0.1 | **188 checks, 188 passed, 0 failed** | none | **DONE** |
| P0.3 | Permission cleanup | Claude | AAM | `settings.local.json` | Snapshot + manifest | Hash + counts before/after | Per-stage | **DONE** — now **338 allow / 31 ask / 8 deny** |
| P0.4 | Runtime-artifact ignore rules | Claude | AAM | `.gitignore` | Validated candidate | Ignore validation; files preserved on disk | Per-commit | **DONE** — committed and pushed |
| P0.5 | Triage the dirty working tree | Claude | AAM | working tree | P0.4 | Preservation manifest; clean status | Per-action | **DONE** — primary checkout clean, nothing deleted |
| P0.6 | Foundation worktree | Claude | AAM | new worktree | Clean tree | Worktree list; secured config verified | Named approval | **DONE** — local only |
| P0.7 | Knowledge-core casing normalization | Claude | AAM | 69 tracked paths | P0.6 | 69 R100 renames; blob identity; test parity | Per-commit | **DONE** — local only |
| P0.8 | Refresh `CLAUDE.md` | Claude | AAM | `CLAUDE.md` | P0.7 | Path existence; guard + suite results | Per-commit | **DONE** — local only |
| P0.9 | Pytest discovery defaults | Claude | AAM | `pytest.ini` | P0.8 | Collection parity (926 node IDs) | Per-commit | **DONE** — local only |
| P0.10 | Install these documents | Claude | AAM | `docs/claude-cowork/**` | P0.9 | Six files; guard suite | Per-commit | **DONE** — local only |

> Items P0.6–P0.10 exist **only on `integration/nova-foundation`**, which is
> neither merged nor pushed.

### Remaining prerequisites

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| P0.11 | Raw-transcript copyright policy | Pedro | AM | policy | — | Decision recorded | Pedro only | **OPEN** |
| P0.12 | Decide Execution Phase 8 disposition | Pedro | AM | archived work | — | Decision recorded | Pedro only | **OPEN** |

---

## Tier 1 — Read-only trust layer

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| B1.1 | **Evidence Formatter** — no claim without command + counts | Claude | FA | none (stdout only) | — | 53 formatter tests; guard 188/188; full suite 2 failed / 964 passed / 13 skipped | Per-commit | **DONE** — local only |
| B1.2 | **Staleness Guard** — re-read HEAD/hashes before reporting | Claude | FA | none | — | Demonstrated catch of a real ref move | none | TODO |
| B1.3 | **A7 battery** — secrets, machine paths, protected files, runtime data, committed paths, staleness, test parity, permission drift, worktree collision | Claude | AR | none | B1.1 | Each gate demonstrated **failing** on planted input | none | TODO |
| B1.4 | **Session Registry** — machine-local, outside every repo | Claude | AR→FA | registry file outside repo | B1.2 | Collision + stale detection demonstrated | Named approval to first write | TODO |
| B1.5 | **Worktree bootstrap validator** — verify a new worktree is secured | Claude | AR | none | B1.3, B1.4 | Guard blobs, permission hash/counts, submodule state | none | TODO |
| B1.6 | **Change Classifier** — cluster changed paths, mark do-not-commit | Claude | AR | none | B1.3 | Classification of a real dirty tree | none | TODO |
| B1.7 | **Test Selector** — changed paths → test list | Claude | AR | none | P0.9 | Selection matches Pedro's choice on repeated trials | none | TODO |

---

### B1.1 Evidence Formatter — implemented

`tools/cowork/evidence_formatter.py`, tested by `tests/test_cowork_evidence_formatter.py`.

**Purpose.** Render a JSON evidence document as Markdown or normalized JSON so
that no claim about repository or test state can be made without the command,
the counts, and the failures behind it.

**Contract.** Input is one UTF-8 JSON document (`schema_version: 1`) with
`phase`, `scope`, `checks`, and optional `tests`, `changes`, `repository_state`,
`permission_state`, `notes`. Output is deterministic: stable key and ID
ordering, explicit UTF-8 bytes, exactly one trailing newline.

**Derived status.** Overall status is computed from the check statuses, never
from a caller-supplied claim: any `fail` -> `failed`; else any `stopped` ->
`stopped`; else any `warning` -> `passed_with_warnings`; else `passed`. **Zero
checks can never yield `passed`.**

**Read-only boundary.** Executes nothing — command strings are data and are
never passed to a shell, a subprocess, `eval`, or `exec`. Writes no file. No
network. Reads no environment variable and no clock; a timestamp appears only if
supplied in the input. Standard library only.

**CLI.**

```bash
python -B tools/cowork/evidence_formatter.py --format markdown
python -B tools/cowork/evidence_formatter.py --format json
python -B tools/cowork/evidence_formatter.py --format markdown --input evidence.json
```

Output is stdout only; there is deliberately no output-file option.

**Exit codes.** `0` valid input formatted (whatever the checks reported) ·
`2` invalid usage or validation failure · `3` safety-limit rejection
(1 MiB size, depth 32, 1000-item collections).

**Privacy.** Values under credential-shaped keys are replaced wholesale;
recognizable credential formats are replaced without echoing the match; home
directories are rewritten to `${HOME}` by pattern, so no username reaches the
output. Ordinary prose such as "tokenizer" or "secret scan" is not redacted.
Errors are sanitized and never contain the rejected payload.

**Status.** Implemented locally on `integration/nova-foundation`. **Not pushed,
not merged.**

## Tier 2 — Proposal layer

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| B2.1 | Staging Plan Builder | Claude | AAM | index | B1.3, B1.6 | Literal path list shown in full | Per-plan | TODO |
| B2.2 | Staged Diff Reviewer | Claude | AR | none | B2.1 | Full cached diff | none | TODO |
| B2.3 | Commit Executor | Claude | AAM | commits | B2.2 | Paths + message + tests + audit together | Per-commit | TODO |
| B2.4 | Doc Staleness Detector | Claude | AR | none | P0.8 | Mechanically checkable claims only | none | TODO |
| B2.5 | Retirement-Boundary Linter | Claude | AR | none | — | Flags a planted stale reference | none | TODO |
| B2.6 | **Knowledge provenance validator** — every note has source, date, and observation-vs-rule status | Claude | AR | none | B1.3 | Validation over the knowledge core | none | TODO |

---

## Tier 3 — Knowledge and research

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| B3.1 | Three-layer extraction template (source claims / interpretation / approved rules) | Claude | AR | none | P0.11 | Approved layer left empty | none | TODO |
| B3.2 | Source acquisition with lineage recording | Claude | AAM | research files | P0.11 | Provenance + stated limitations | Before any network fetch | TODO |
| B3.3 | Conflict detector across sources | Claude | AR | none | B3.1 | Conflicts tabulated, not reconciled | none | TODO |
| B3.4 | **Obsidian adapter** — manual, approval-gated, configurable vault path | Claude | AAM | vault files | B2.6, B3.1 | Stable IDs; provenance; conflict stop | Per-sync | TODO |

---

## Tier 4 — Intelligence and future trading contracts

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| B4.1 | **NOVA Brain output contract** — schema for structured analysis, explicitly non-instructional | Pedro + Claude | AAM | spec + tests | B2.6, B3.1 | Schema, tests, worked examples | Pedro approves the contract | TODO |
| B4.2 | Brain implementation against the contract | Claude | AAM | source | B4.1 | Contract conformance tests | Per-commit | TODO |
| B4.3 | **Risk engine interface contract** — independent veto, non-overridable | Pedro + Claude | AAM | spec + tests | B4.1 | Veto demonstrated to win | Pedro only | TODO |
| B4.4 | **Execution engine interface contract** — mechanics only, originates nothing | Pedro + Claude | AAM | spec + tests | B4.3 | No decision path in the interface | Pedro only | TODO |
| B4.5 | **NOVA Trader architecture** — deterministic policy, approved strategies only | Pedro | AM | spec | B4.1–B4.4 | Full staged ladder defined | Pedro only | **BLOCKED** |

---

## Tier 5 — Multi-worktree structure

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| B5.1 | Integrate with current remote `main` | Pedro + Claude | AM | branches | P0.10, B1.5 | Re-measured divergence; conflict review | Pedro only | TODO |
| B5.2 | `nova-development` worktree | Claude | AAM | new worktree | B1.5, B5.1 | Bootstrap validator pass | Named approval | TODO |
| B5.3 | `nova-research` worktree | Claude | AAM | new worktree | B5.2 | Bootstrap validator pass | Named approval | TODO |
| B5.4 | `nova-indicator` worktree | Claude | AAM | new worktree | B5.2 | Bootstrap validator pass | Named approval | TODO |
| B5.5 | Cross-worktree transfer discipline (patch/cherry-pick only) | Claude | AM | commits | B5.2 | Transfer demonstrated without file copying | Pedro only | TODO |

---

## Deliberately excluded

| Item | Why |
|---|---|
| Auto-push / auto-deploy | Reaches other machines. Permanently manual |
| Auto-merge / auto-rebase | Silent conflict resolution on shared branches |
| Auto-`restore` / auto-`clean` | Destroys uncommitted work |
| Auto-fix failing tests | Turns a verification signal into a moving target |
| Auto-promote research to rules | Violates the standing strategy-approval rule |
| Auto-edit trading specifications | Pedro's authority |
| Auto-rotate credentials | Outside remit |
| A "commit when tests pass" loop | Removes the approval that makes the system safe |
| Any automated order submission | Prohibited without exception |

---

## Note on counts

Figures such as test totals and file counts are **snapshots at the time of
measurement**, not invariants. Re-measure before relying on any of them. Where
this backlog states a count (188 guard checks; 338/31/8 permissions), it reflects
the verified state at the time these documents were installed.
