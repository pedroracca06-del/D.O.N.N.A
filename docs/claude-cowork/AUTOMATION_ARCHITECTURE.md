# Automation Architecture

How the pieces fit: who acts, where truth lives, how worktrees stay separate, how
concurrent sessions avoid each other, and what must be proven before any mutation.

---

## A. Actors and boundaries

| Actor | Owns | May never |
|---|---|---|
| **Pedro** | Approval, strategy, risk, capital, deployment authority | — |
| **Claude Code / Cowork** | Engineering, maintenance, tests, documentation, audits, proposals | Decide or influence trades; submit orders; enable guarded flags; edit strategy specs or risk limits; push, merge, or deploy |
| **Obsidian** | Durable curated knowledge, research notes, decisions, learning records | Execute anything — no scripts, no scheduled actions, no repository writes |
| **NOVA Brain** | Financial understanding, market intelligence, research synthesis, structured analysis | Submit broker orders; size positions; alter risk limits; write to the execution path |
| **NOVA Trader** (future) | Deterministic trading policy inside an approved strategy and risk envelope | Override risk controls; expand its own mandate; act on unapproved strategies |
| **Risk engine** | Hard limits, kill switches, loss caps, concurrency caps, session gates | Be bypassed or overridden by any actor above it |
| **Execution engine** | Broker mechanics — order construction, submission, reconciliation | Originate a decision |

### What the retirement guard actually enforces

The installed guard is **one mechanical layer, not the architecture**. It enforces:

- the retired-subsystem boundary — protected files cannot be modified;
- kill-switch integrity in `main.py` and `monitor.py`;
- the two activation flags cannot be set to an enabling value.

It does **not** enforce the rest of this document. It inspects tool calls against
a fixed path and flag list, so it says nothing about new code in unguarded paths,
a parameter changed in an unprotected file, advice given in prose, or a future
system that consumes Claude's output. The broader boundaries rest on approval
policy, worktree separation, ownership, deterministic risk/execution design, and
future architecture controls. Any claim that "the guard makes it safe" is a
category error.

---

## B. Source-of-truth split

| Store | Holds | Never holds |
|---|---|---|
| **Git** | Code, tests, formal specifications, approved architecture, immutable history | Runtime state, credentials, raw third-party transcripts |
| **Obsidian** | Human-readable knowledge, research notes, decisions, learning records | Anything executable; anything that is the authority for behavior |
| **NOVA Brain** | Structured intelligence, consumed and produced through defined interfaces | Order authority |
| **Local disk (ignored)** | Runtime data, caches, raw transcripts pending a copyright decision | — |

Rules:

- Runtime data stays outside Git. It is preserved on disk, never committed.
- Raw third-party transcripts stay local and ignored. Derived summaries are tracked.
- **No document store becomes an execution surface.** Neither Obsidian nor the
  knowledge core can cause anything to run.
- Where Git and Obsidian appear to disagree about an approved specification,
  **Git wins** — Obsidian holds the reasoning, Git holds the contract.

### Promotion flow

```
research observation
  → Obsidian review               (human reading, notes, conflicts recorded)
  → Pedro approval                (explicit, naming the rule)
  → formal Git specification      (the contract)
  → tests                         (the specification made checkable)
  → implementation
```

**No automatic promotion at any step.** An observation never becomes a NOVA rule
because it was ingested, summarized, or found convincing.

---

## C. Worktree model

| Worktree | Branch | Purpose | Status |
|---|---|---|---|
| Primary checkout | `retirement/disable-legacy-trading` | Stable retirement/security reference | exists |
| `nova-foundation` | `integration/nova-foundation` | Integration and Claude infrastructure | exists |
| `nova-development` | (future) | Active application engineering | not created |
| `nova-research` | (future) | Brain/research ingestion | not created |
| `nova-indicator` | (future) | Market Map / Pine work | not created |

### How worktrees actually behave

- Each worktree has **its own index and working directory**.
- **Branches and the object database are shared.** A commit made in one is
  immediately reachable from the others; a branch checked out in one cannot be
  checked out in another.
- **`.claude/settings.local.json` is git-ignored and therefore per-worktree.** A
  new worktree starts without it. It must be installed and verified explicitly —
  hash and allow/ask/deny counts checked, not assumed.
- **Guard and config blobs come from the checked-out branch.** A worktree on an
  older branch gets that branch's guard, which may be weaker. Verify the hook and
  harness blobs after creating any worktree.
- **Submodules require independent initialization and state verification per
  worktree.** A new worktree does not populate them; the directory is empty until
  initialized, and its checked-out commit must be verified separately.
- Line endings can differ between worktrees (`core.autocrlf`), so **raw file
  hashes are not comparable across worktrees**. Compare `git rev-parse HEAD:<path>`.
- **Never casually copy files between worktrees.** Move work as commits
  (`git format-patch` / `git cherry-pick`).
- **Integrations happen through reviewed commits**, never by synchronizing
  directories.

---

## D. Shared session registry (design only — not created)

A machine-local registry lets a session detect that another session is already
working on the same branch or worktree before it starts an audit or a staging
plan. It lives **outside every repository**, at a portable location such as:

```
${HOME}/.claude/nova-session-registry.json
```

**This file is not created in this phase.**

### Required fields

| Field | Purpose |
|---|---|
| `session_id` | Unique identifier for the session |
| `worktree_identity` | Stable logical name (e.g. `nova-foundation`) |
| `worktree_path` | Canonical absolute path, resolved and case-normalized |
| `branch` | Currently checked-out branch |
| `task` | Short description of what the session is doing |
| `read_scope` | Paths the session expects to read |
| `write_scope` | Paths the session may mutate |
| `protected_scope` | Paths the session must not touch |
| `started_at` | ISO-8601 timestamp with offset |
| `heartbeat_at` | Last liveness update |
| `status` | `active` · `idle` · `stale` · `finished` |
| `owner` | Who or what started it |
| `expected_commit` | The HEAD or baseline the session measured against |

### Stale-session handling

A record is **stale** when its `heartbeat_at` is older than a defined threshold.
A stale record is reported, never silently deleted — a session may be paused
rather than dead. Only Pedro, or the owning session itself, clears a record.
The registry **never blocks a human**; it warns.

### Collision detection

A collision is any of:

- two `active` sessions on the same `branch`;
- two `active` sessions whose `write_scope` sets intersect;
- one session's `write_scope` intersecting another's `protected_scope`;
- an `expected_commit` that no longer matches the real HEAD.

On collision: stop, report both records, and ask. Do not proceed on the
assumption that the other session is finished.

---

## E. Evidence format and A7 gates

### Evidence format

Every claim about repository state carries, in the report:

- the **exact command** run;
- the **counts** it produced;
- the **failures**, named individually;
- the **hashes or refs** the measurement was taken against.

A claim without these is not made.

### A7 gates

Runnable against the working tree (advisory) or staged blobs (**gating**). A hard
gate failing produces a **no-go**: the commit is not offered and the index is left
untouched for inspection.

| ID | Gate | Checks | Gating on staged? |
|---|---|---|---|
| A7.1 | Secrets | Keys, tokens, credential keywords, high-entropy runs | **yes** |
| A7.2 | Machine-specific paths | User-home paths, temp/scratch paths, session UUIDs, absolute drive paths | **yes** |
| A7.3 | Protected files | Guarded files unmodified; guarded flags not enabled; kill-switch lines intact | **yes** |
| A7.4 | Runtime/generated data | Runtime JSON, caches, bytecode, scratch artifacts | **yes** |
| A7.5 | Exact committed paths | Staged set equals approved set, exactly | **yes** |
| A7.6 | Baseline/ref staleness | HEAD, refs, and target hashes re-read since measurement | **yes** |
| A7.7 | Test parity | Collection node IDs and counts unchanged where they should be | **yes** |
| A7.8 | Permission drift | `settings.local.json` hash and allow/ask/deny counts unchanged | **yes** |
| A7.9 | Worktree collision | Registry shows no conflicting active session | **yes** |

Gates must be **demonstrated to fail** on planted bad input before being trusted.
A gate that has never failed has not been tested. Audit logs live outside the
repository and never contain secret values.

### A7.7 and focused test selection

The Test Selector (B1.7) proposes a **focused** subset of tests from changed paths.
That subset is **optional preliminary evidence** and nothing more.

- **A focused selection never satisfies A7.7.** A7.7 compares collection node IDs
  and counts; a deliberately partial run cannot establish that.
- **Collection parity remains mandatory** before a commit, re-measured against the
  current pinned HEAD and compared as **exact node-ID sets**. Historical counts —
  926 at P0.9, 1722 at Phase 3U — are snapshots, never expected values.
- **The complete regression suite remains mandatory** before a commit. A focused run
  is for fast feedback while working, not for clearing a gate.
- **A focused selection makes no claim about the tests it did not select.** They
  were not chosen; they were not shown to pass.
- **An unmappable or ambiguous path escalates to a full-suite-required result.** The
  selector never narrows silently, and "no focused test" never means "no testing
  required".

The selector imports nothing and invokes pytest never — not even `--collect-only`,
which would import every test module and conftest and execute their module-level
code. It emits a structured argument array as evidence, and does not run it.

---

## F. Obsidian boundary

Obsidian is **optional and non-executing**. It is a place to read and write
knowledge, and nothing else.

- **Vault location must be configurable, never hard-coded.** No absolute path to a
  vault appears in this repository.
- **Start with manual, approval-gated synchronization.** No background sync, no
  file watcher, no scheduled job.
- **Stable IDs and provenance metadata** on every synced note: where it came from,
  when, which commit or source it reflects, and whether it is observation or
  approved rule.
- **Prevent duplicate authority.** Approved specifications live in Git; research
  notes and learning material live in Obsidian. The same rule must not be
  authoritative in both places.
- **Conflicts stop synchronization** and require Pedro. Automation never merges a
  knowledge conflict.
- **Never sync automatically**: credentials, runtime account state, raw
  copyrighted transcripts, or broker data.
- **No plugins or scripts are installed** in this phase.

---

## G. NOVA Brain and Trader handoff

### Staged boundary

| Component | Responsibility |
|---|---|
| **Claude / Cowork** | Builds and maintains systems |
| **NOVA Brain** | Understands finance, synthesizes research, explains markets, emits **structured analysis** |
| **NOVA Trader** (future) | Deterministic trading policy operating only on approved strategies |
| **Risk engine** | Independent **veto authority** — upstream of policy, not overridable |
| **Execution engine** | Broker mechanics only |

Brain emits analysis. Analysis is **not** an instruction. It enters a policy layer
through a defined, auditable contract; the policy layer is deterministic; risk
sits upstream of policy and can veto without appeal; execution only carries out
what survives.

### Required staged ladder

Autonomy advances only through these stages, in order, each a separate approval:

1. Documented strategy
2. Historical backtest
3. Out-of-sample validation
4. Paper account
5. Governance dry run
6. **Pedro's explicit funded-account authorization**
7. Monitored limited autonomy
8. Expansion only through new approval

**No stage may be skipped, and current work authorizes none of them.** The
repository today contains no approved strategy and no active trading capability.
