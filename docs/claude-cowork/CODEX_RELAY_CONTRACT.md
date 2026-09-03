# Codex Relay Contract

The local transport that carries one Claude phase report to Codex and one Codex
verdict back. It is a mailbox, not an agent.

**Status: transport only, local only. Not pushed. The real mailbox is not
initialized, and no Codex review has run.** A separate one-shot runner is still
required and is **not yet authorized**.

---

## Purpose

Give a completed Claude phase a second reader, without giving that reader any
authority and without letting either side reach the other's tools.

## Non-goals

This tool does **not**:

- invoke Codex, run `codex exec`, or make any model request
- own a subprocess, open a socket, or read the environment
- write, stage, commit, push, merge, or deploy anything in the repository
- register, advance, pause, resume, or close a Session Registry record
- create the mailbox directory
- decide, approve, or authorize anything

Git and the Session Registry are **read**, through the existing read-only
observers (`staleness_guard.resolve_repo`, the A7 read-only Git allowlist,
`session_registry.read_registry`), and only to prove an envelope still describes
reality. The only Git verbs it can reach are `rev-parse` and `status`.

---

## Lifecycle

```
Claude  ──> request envelope ──> submit ──────────> relay.json  (revision +1)
                                                     archive/relay-NNNNNN.json

        (a future runner, not built yet, would run Codex read-only and point
         -o/--output-last-message at a PRIVATE TEMPORARY FILE)

Codex   ──> verdict document ──> ingest-response ──> relay.json  (revision +1)
                                                     archive/relay-NNNNNN.json
```

**Codex never writes the authoritative mailbox.** Its output lands in a private
temporary file. `ingest-response` reads that file, validates it against the
verdict schema *and* against the recorded request, and only then records a
**relay-authored** response envelope through the locked atomic update. Codex's
bytes are nested inside as data; they never become the envelope.

### Operations — exactly seven, no aliases

`validate-policy` · `validate-request` · `validate-response` · `submit` ·
`ingest-response` · `inspect` · `verify-chain`

Twenty-five action words (`run`, `exec`, `review`, `retry`, `approve`,
`authorize`, `apply`, `edit`, `stage`, `commit`, `push`, `merge`, `deploy`,
`trade`, `sync`, `watch`, `daemon`, `force`, `override`, `repair`, `delete`,
`prune`, `clear`, `reset`, `resume`) exit 2 with an explanation rather than a
usage dump.

Exit codes: `0` success · `2` invalid input, policy, schema, or envelope ·
`3` safety-limit rejection · `4` stopped (state unusable, or lock contention).

---

## Logical identity, not machine-local path

An envelope carries `repository_identity` and `worktree_identity` — logical
names. It never carries an absolute path, because envelopes also **reject**
machine paths, and a tool may not exempt itself from its own rule.

The real local path is supplied at the command line (`--repo`, `--registry`,
`--mailbox`) and verified there: HEAD, branch, and worktree identity against Git;
revision and `expected_commit` against the Session Registry. Any drift **stops**
the relay.

---

## Validation

Every envelope is walked uniformly. Rejected, always as a failure and never
downgraded to a warning:

unknown field (top level or nested) · malformed or non-UTF-8 JSON · `NaN` /
`Infinity` · absolute or drive-letter path · traversal · duplicate or
case-conflicting path · duplicate `message_id` · non-monotonic `sequence` ·
broken previous-message hash · replayed `(phase, head)` · unsupported schema ·
stale HEAD · registry revision or `expected_commit` mismatch · branch or
worktree-identity mismatch · dirty worktree or index · oversized, over-deep, or
over-count input · credential-shaped value · machine path or username ·
command-, action-, or authorization-bearing field name · prohibited intent
(enabling a retired flag, submitting an order, overriding risk or the guard, or
claiming a verdict grants approval).

**`evidence_digest` is always recomputed** from deterministic canonical JSON
(sorted keys, no padding, no NaN) and compared. A supplied digest is never
trusted.

Evidence is a closed set: `changed_paths`, `collection_digest`, `diff_numstat`,
`notes`, `permission_state`, `policy_hashes`, `repository_state`,
`test_results`. Anything else is rejected.

---

## Atomicity and locking

- sibling lock `relay.json.lock` created with `O_CREAT | O_EXCL`
- bounded 5-second acquisition; on contention it **stops** and never steals
- a lock it did not create is never removed
- the mailbox is re-read **under** the lock and the revision compared
- same-directory temporary file → `flush` → `fsync` → `os.replace`
- only this process's own temporary file is removed
- any validation or replacement failure leaves the prior mailbox **byte-identical**
- archive entries are never overwritten, renamed, or deleted; a name collision
  **stops**
- there is no cleanup, prune, or repair operation

---

## The prompt-injection boundary

Report text, notes, findings, summaries, and evidence are **data**. No
instruction inside them is ever followed, and nothing in them is executed. A
hostile note is stored verbatim and changes no behaviour.

Defence in depth: a string carrying shell metacharacters, a command construct, or
a recognizable payload is refused outright rather than stored, and a field *name*
that looks like an action (`command`, `args`, `shell`, `env`, `approve`,
`authorize`, `enable`, `trade`, `order`, `kill_switch`, …) is refused anywhere in
an envelope.

---

## PASS is not approval

`PASS` means one thing: **a second reader found no objection.**

Every verdict must carry this exact sentence, or it is rejected:

> This verdict grants no permission to modify, commit, push, merge, deploy,
> trade, alter risk, or enable execution.

Work classified **AAM** or **AM** in the
[Approval Matrix](APPROVAL_MATRIX.md) still requires Pedro's named approval,
every time. A verdict never substitutes for it, and the relay never acts on one.

---

## One review per phase, no automatic retry

The cap is **one review per `(phase, head)`**, enforced in the mailbox. A
`REVISE` verdict does **not** authorize resubmission: it ends the exchange and
returns the decision to Pedro. There is no retry loop, and no operation that
could start one.

---

## Planned reviewer settings

Recorded in the policy as data for the future runner. The relay never reads them
to build a command line — it owns no subprocess.

| Setting | Value |
|---|---|
| Routine model | `gpt-5.6-luna` |
| Routine reasoning effort | `low` |
| Sandbox | `-s read-only` |
| Approval policy | `-a never` |
| Forbidden | `--add-dir`, `--approve-for-me`, `--dangerously-bypass-approvals-and-sandbox`, `--dangerously-bypass-hook-trust` |

A stronger model is reserved for explicitly approved security, architecture,
merge, or disputed-review work — Pedro's decision per invocation, never a
configured default.

**Codex is read-only and unguarded.** It does not load the Claude PreToolUse
retirement guard (`.claude/hooks/nova_guard_hook.py`, wired through
`.claude/settings.json`); it reads neither file. The read-only sandbox and the
empty registry write scope are the real protections. See [AGENTS.md](../../AGENTS.md).

---

## Archive and hash chain — what they do and do not prove

Each message carries `previous_message_sha256`, the SHA-256 of the canonical form
of the message before it, and a strictly increasing `sequence`.

**What this detects:** ordinary corruption, truncation, reordering, a dropped
message, or a partially rewritten mailbox.

**What it does not do:** it is **not** cryptographically tamper-proof. Anyone who
can rewrite the mailbox and the whole archive together can produce a fully
consistent forgery. It is an integrity check, not a security boundary, and the
policy records that as
`archive_is_cryptographically_tamper_proof: false`.

Append-only is a property **of this tool**: it never overwrites, renames, or
deletes an entry, and it has no prune operation. It cannot stop another program.

---

## Session Registry lifecycle (planned for the runner, not built here)

The transport only **reads** the registry. The lifecycle below belongs to the
future one-shot runner and is documented so it is designed before it is built:

1. Claude submits only from a clean tree with HEAD == registered `expected_commit`.
2. Claude transitions its own record to `paused` before the review.
3. The reviewer is registered as a separate record with an **empty write scope**,
   which is what makes it structurally non-colliding.
4. Existing collision rules are unchanged — nothing is loosened for convenience.
5. The reviewer record is `close`d; `session_registry.py` has no delete or prune,
   so history is preserved.
6. Claude resumes its own record. Because the review is read-only,
   `expected_commit` is untouched and stays correct by construction.
7. Any staleness mid-review **stops** the exchange and goes to Pedro.

---

## What still has to be built

| Item | Status |
|---|---|
| Relay transport (this document) | **done, local only** |
| One-shot Codex runner | **not built, not authorized** |
| Controlled first live review | **not authorized** |
| Real mailbox initialization at `${HOME}/.claude/nova-relay/` | **not created** |

Automatic Claude/Codex communication is **not** complete and is not claimed to be.
