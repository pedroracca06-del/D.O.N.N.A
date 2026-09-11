# Phased Implementation Order

Each phase has an entry condition, a deliverable, and an **exit criterion that
must be demonstrated, not asserted**. No phase begins before its predecessor's
exit criterion is met.

Item IDs refer to [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md).

---

## Phase 0 — Foundation · **COMPLETE**

Retirement guard installed and pushed; guard suite at 188/188; permissions reduced
to 338/31/8; runtime artifacts ignored while preserved on disk; primary checkout
clean; foundation worktree created; knowledge-core casing normalized; `CLAUDE.md`
and pytest discovery refreshed.

**Exit criterion met.** Primary checkout reports an empty `git status`; the guard
suite passes against the installed copy; permission hash and counts verified.

**Carried forward:** the casing normalization, `CLAUDE.md`, `pytest.ini`, and
these documents exist **only on `integration/nova-foundation`** — not merged, not
pushed.

## Phase 1 — Documents installed · **COMPLETE**

This directory. Boundaries written down before automation is built against them.

**Exit criterion met.** Six documents present, internally consistent, no
contradiction in responsibility assignments.

## Phase 2 — Evidence Formatter (B1.1)

**Entry:** Phase 1 complete.
**Deliverable:** every test or state claim carries command, counts, and failures.
**Exit:** ten consecutive reports where no claim appears without its evidence.
**Abort if:** the formatter is bypassed even once "because the result was obvious."

## Phase 3 — Staleness Guard (B1.2)

**Entry:** Phase 2 exit met.
**Deliverable:** HEAD, refs, and target hashes re-read immediately before reporting.
**Exit:** the guard correctly flags at least one real concurrent ref move.
**Abort if:** it produces false staleness often enough to be ignored.

## Phase 4 — A7 battery (B1.3)

**Entry:** Phase 3 exit met.
**Deliverable:** nine gates runnable against worktree and staged blobs.
**Exit:** each gate **demonstrated to fail** on planted bad input — a fake secret,
a machine path, a runtime-data file, a protected-file modification, a mismatched
staged set, a stale ref, a collection delta, a permission drift, a worktree
collision.
**Abort if:** the false-positive rate is high enough that findings get skimmed.

## Phase 5 — Session Registry (B1.4)

**Entry:** Phase 4 exit met.
**Deliverable:** machine-local registry outside every repository, with the fields
defined in [AUTOMATION_ARCHITECTURE.md](AUTOMATION_ARCHITECTURE.md) §D.
**Exit:** a simulated second session is detected before it can begin a staging
plan; a stale record is reported rather than deleted.
**Abort if:** the registry ever blocks a human.

## Phase 6 — Worktree bootstrap validator (B1.5)

**Entry:** Phase 5 exit met.
**Deliverable:** a check that a newly created worktree is correctly secured —
guard and harness blobs match the branch, `settings.local.json` installed with the
expected hash and counts, submodule state verified.
**Exit:** run against a freshly created throwaway worktree and correctly reports a
deliberately omitted permission file.

## Phase 6a — Change Classifier (B1.6) · **COMPLETE**

**Entry:** Phase 4 exit met (A7 running).
**Deliverable:** a read-only tool reporting the **minimum approval class** a change
requires — FA/AR, AAM, AM, or PROHIBITED — and never granting approval.
**Exit met.** Every class and every mode demonstrated; each path classified
independently and aggregated to the most restrictive; unknown paths, unknown change
kinds, and unscannable content escalate to AM; retirement-flag activation, guard
bypass, and LLM-to-order wiring are PROHIBITED. 216 tests, 10 planted
demonstrations.
**Abort if:** any output could be read as an approval.

## Phase 6b — Test Selector (B1.7) · **COMPLETE**

**Entry:** Phase 6a exit met.
**Deliverable:** a read-only tool proposing a focused test list from changed paths,
built by static AST analysis of tracked blobs — importing nothing and invoking
pytest never, not even `--collect-only`.
**Exit met.** Self, direct, transitive, relative, conftest-subtree, and explicit
policy mappings demonstrated; deletion, rename, and case-only rename handled;
unmapped, dynamic-import, unresolvable-star-import, unresolved-internal-import,
syntax-error, and binary changes all escalate to full suite; a recomputed closure
proof shows no statically discovered dependent test is omitted. 167 tests, 10
planted demonstrations.
**Abort if:** a focused selection is ever presented as sufficient evidence for a
commit. It is not, and cannot be — see the A7.7 note in
[AUTOMATION_ARCHITECTURE.md](AUTOMATION_ARCHITECTURE.md#a77-and-focused-test-selection).

## Phase 7 — Integration with current remote `main` · **AM**

**Entry:** Phases 2–6, 6a, and 6b exit met.
**Deliverable:** `integration/nova-foundation` reconciled with `origin/main`.
**Preconditions:** remote `main` has been observed moving repeatedly, so the
divergence **must be re-measured immediately before planning**, never taken from
an earlier report. Both branches carry substantive UI work, so conflicts are
expected.
**Exit:** a reviewed integration with no unreviewed conflict resolution.
**Approval:** fetch, merge, and push are **three separate Pedro approvals**. None
is implied by approving this phase.

## Phase 8 — Dedicated worktrees (B5.2–B5.4)

**Entry:** Phase 7 complete; bootstrap validator running.
**Deliverable:** `nova-development`, `nova-research`, `nova-indicator`, each with a
disjoint file domain.
**Exit:** a change moves between two worktrees by patch or cherry-pick with no
file copying, and each worktree's commits touch only its own domain.
**Abort if:** any working tree is dirty at creation time.

## Phase 9 — Approval-gated Obsidian adapter (B3.4)

**Entry:** Phase 8 complete; provenance validator (B2.6) running.
**Deliverable:** manual, approval-gated synchronization with a configurable vault
path, stable IDs, and provenance metadata.
**Exit:** one full sync where a planted conflict **stops** synchronization and
escalates rather than merging.
**Abort if:** any credential, runtime account state, raw transcript, or broker
data is ever included in a sync set.

## Phase 10 — NOVA Brain handoff contract (B4.1)

**Entry:** Phase 9 complete.
**Deliverable:** a schema for Brain's structured analysis, explicitly
non-instructional, with tests and worked examples.
**Exit:** the contract demonstrably cannot express an order instruction.
**Approval:** Pedro approves the contract itself.

## Phase 11 — Brain implementation (B4.2)

**Entry:** Phase 10 exit met.
**Deliverable:** Brain built against the approved contract.
**Exit:** conformance tests pass; Brain output reaches no execution path.

## Phase 12 — Trader architecture · **BLOCKED**

**Entry:** Phase 11 complete **and** the risk (B4.3) and execution (B4.4)
interface contracts approved.
**Deliverable:** design only — deterministic policy over approved strategies,
with risk holding independent veto.
**Approval:** Pedro only. Not started, not scheduled.

## Phase 13 — Staged validation ladder · **NOT AUTHORIZED**

Autonomy advances only through, in order:

1. Documented strategy
2. Historical backtest
3. Out-of-sample validation
4. Paper account
5. Governance dry run
6. **Pedro's explicit funded-account authorization**
7. Monitored limited autonomy
8. Expansion only through new approval

**No stage may be skipped. Nothing in the current repository authorizes any of
them.**

---

## Standing approval notes

- **Push, merge, and deploy are always separate Pedro approvals**, each named at
  the moment it is proposed. Approving a phase never approves its push.
- Every count in these documents is a snapshot; re-measure before relying on it.
- If approvals start being granted without reading, the system has failed even
  while appearing to work.
