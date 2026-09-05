# Codex Relay Contract

The local transport that carries one Claude phase report to Codex and one Codex
verdict back. It is a mailbox, not an agent.

**Status: transport and runner, local only. Not pushed.** The machine-local
mailbox is initialized and in use, and live reviews have run under Pedro's
per-invocation authorization. Every review remains one attempt per
`(phase, head)`, explicitly authorized each time; nothing here runs on its own.

---

## Purpose

Give a completed Claude phase a second reader, without giving that reader any
authority and without letting either side reach the other's tools.

## Non-goals of the transport

`codex_relay.py` does **not**:

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

        (codex_review_runner.py starts Codex read-only, exactly once, and
         points -o/--output-last-message at a PRIVATE TEMPORARY FILE)

Codex   ──> verdict document ──> ingest-response ──> relay.json  (revision +1)
                                                     archive/relay-NNNNNN.json
```

**Codex never writes the authoritative mailbox.** Its output lands in a private
temporary file. `ingest-response` reads that file, validates it against the
verdict schema *and* against the recorded request, and only then records a
**relay-authored** response envelope through the locked atomic update. Codex's
bytes are nested inside as data; they never become the envelope.

### Operations — exactly nine, no aliases

`validate-policy` · `validate-request` · `validate-response` ·
`cancel-request` · `record-rejection` · `submit` · `ingest-response` ·
`inspect` · `verify-chain`

`cancel-request` retires a request that can never run. `record-rejection`
terminates one whose attempt was already spent: the child started, so the
attempt is gone, and the request must not sit pending. Both are terminal, both
are append-only, and neither permits a retry of the request it closes.

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

**A named symbol is data; an invocation is not.** A verdict and its audit block
exist to describe code, so they are scanned in *prose mode*: a review has to be
able to write `powershell`, `curl`, `subprocess` or `Invoke-Expression` in order
to report that the runner does not use them, and to use a semicolon in an
English sentence. Prose mode swaps exactly one rule — the executable scan — for
a calibrated set that refuses an invocation (a tool name followed by a flag, a
URL, a path, a quoted string, a variable, a redirect, a number, or another
command name) while allowing a mention. Requests keep the stricter free-form
rule, because Claude authors requests. Every other scan is identical in both
modes: credentials, machine paths, prohibited intent, field names, depth, and
length.

The calibration is a regression test, not a judgement call: twenty sentences an
honest audit would write must all validate, and thirty-one pieces of genuinely
runnable content must all be refused. Two live reviews were refused by the
earlier rules for naming a shell, and each refusal consumed an attempt that
cannot be retried — which is why the corpora ship with the code.

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

## Retiring a request that can never run

A request pins the registry revision it was bound to, and registry revisions only
ever increase. If any session lifecycle change lands between `submit` and
`review-once`, that request can never satisfy its own preconditions again — and
because `find_pending_request` requires exactly one pending request, it would
block **every** future review.

`cancel-request` retires exactly one such request by **appending** a terminal
`request_cancelled` message. It is append-only in the strictest sense: nothing is
deleted, rewritten, truncated, moved, or silently archived, and every prior
message and archive entry stays byte-identical.

The terminal records what it retired and why: the request id, its sequence, its
phase, its bound head, its bound registry revision, the reason, and who
authorized it. The reason is preserved rather than concealed, so the mailbox
still explains how the request went stale.

It is **not a model response.** It carries no verdict, consumes no review
attempt, and approves nothing — `sender` is `claude`, never `codex`, and no
Codex result is fabricated.

It refuses: an unknown id · a message that is not a review request · a request
that already has a response · one already cancelled · an id that is not *the*
pending request · any state with more or fewer than one pending request · a
broken chain · and, with `--expect-mailbox-revision`, any revision race. Every
refusal leaves the mailbox bytes unchanged. The existing lock, atomic replace,
archive, and residue guarantees are untouched.

`find_pending_request` and the runner's preconditions treat a valid cancellation
as terminal for exactly that request, and for no other.

Chain verification enforces the same shape independently of the command, because
it is what validates a mailbox read off disk: a `request_cancelled` message must
name an **earlier review request**. Naming a response, another cancellation, or
an unknown id fails verification, as does cancelling the same request twice. The
command already refused all of these; the check exists so a tampered or
hand-edited mailbox is caught too.

---

## One review per phase, no automatic retry

The cap is **one review per `(phase, head)`**, enforced in the mailbox. A
`REVISE` verdict does **not** authorize resubmission: it ends the exchange and
returns the decision to Pedro. There is no retry loop, and no operation that
could start one.

---

## Reviewer settings

Recorded in the relay policy as data and enforced by the runner. The relay itself
never reads them to build a command line — it owns no subprocess.

| Setting | Value |
|---|---|
| Routine model | `gpt-5.6-luna` |
| Routine reasoning effort | `low` |
| Sandbox | `-s read-only` |
| Approval policy | `-c approval_policy="never"` |
| Windows sandbox backend | `-c windows.sandbox="elevated"` |
| Pinned CLI | `codex-cli 0.153.3` |
| Pinned native binary | sha256 `e5ef3c4b81d2fb861f3731c91a773d45a1973c6a0b480d6449f80bc8fd749e96` |
| Forbidden | `--add-dir`, `--approve-for-me`, `--dangerously-bypass-approvals-and-sandbox`, `--dangerously-bypass-hook-trust` |

A stronger model is reserved for explicitly approved security, architecture,
merge, or disputed-review work — Pedro's decision per invocation, never a
configured default, and it needs a new approved phase rather than a policy edit.

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

## The one-shot runner

`tools/cowork/codex_review_runner.py`, with the pure-data
`codex_runner_policy.json`. It is the only component in the Cowork family that may
start a model, and it is deliberately narrow.

### Lifecycle of one review

1. Read the mailbox; require **exactly one** pending Claude request (one with no
   recorded Codex response).
2. Observe the repository and the Session Registry, read-only.
3. Check every precondition (below). If any fails, **stop before spawning** — the
   review attempt is *not* consumed.
4. Resolve `codex` on the search path and prove the binary — on Windows this
   walks the npm package to the bundled native executable (see below).
5. Build the prompt from the request. The runner writes it; no caller supplies prose.
6. Create a private temporary response file.
7. **Start Codex exactly once.** From this moment the attempt is spent.
8. Re-observe the repository, registry, and mailbox. Any drift stops the ingest.
9. Hand the response file to `codex_relay.py ingest-response`, which validates it
   and records a relay-authored envelope atomically.
10. Remove only the runner's own temporary file.

### CLI surface — exactly three operations, no aliases

`validate-policy` · `inspect` · `review-once`

The first two are read-only and never start Codex. `review-once` requires
`--repo`, `--registry`, `--mailbox`, `--session-id`, and
`--reviewer-session-id`, and accepts nothing else. There is **no** `--prompt`,
`--model`, `--reasoning`, `--codex-executable`, `--output`, `--retry`,
`--session`, `--resume`, `--fork`, `--env`, `--sandbox`, `--approval`, or
`--add-dir`; supplying one exits 2, as do 24 action verbs.

### The exact invocation, and the proven stdin form

Proven from local `codex exec --help` on **codex-cli 0.153.3**, verbatim:

> `[PROMPT]` — "Initial instructions for the agent. If not provided as an argument
> (or if `-` is used), instructions are read from stdin. If stdin is piped and a
> prompt is also provided, stdin is appended as a `<stdin>` block"

Both the omitted-argument and the explicit `-` forms read stdin. The runner uses
the **explicit `-`**, so the argument array states the intent and the prompt can
never appear on a command line.

```
codex exec
  -C <verified repository root>
  -s read-only
  -c windows.sandbox="elevated"
  -c approval_policy="never"
  -m gpt-5.6-luna
  -c model_reasoning_effort="low"
  --ephemeral
  --ignore-user-config
  --output-schema <committed relay_verdict_schema.json>
  -o <private temporary response file>
  -                      <- prompt arrives on stdin
```

`--json` is deliberately **omitted**: local help shows it only adds a JSONL event
stream on stdout, which is output the runner does not need and would rather not
capture. Never used: `--add-dir`, `--approve-for-me`, either
`--dangerously-bypass-*`, `--ignore-rules`, `--skip-git-repo-check`, `resume`,
`fork`, `review`.

#### The Windows sandbox backend is fixed at elevated

On Windows a `read-only` sandbox is served **only** by the elevated backend. With
the unelevated backend Codex refuses outright --

```
windows sandbox failed: Restricted read-only access requires the
elevated Windows sandbox backend
```

-- and the child can read nothing, which is exactly how the first live review
failed: it returned STOP because it could not inspect the repository at all. The
runner therefore fixes `windows.sandbox="elevated"` in its own argument array.

This is **not** a loosening: it selects the stronger backend, and the sandbox mode
stays `read-only`. It is runner-owned -- no flag, caller, or envelope can set,
change, or remove it, and a policy naming any other backend is refused both by
`validate-policy` and again when the array is built.

#### The binary itself is pinned, not just its package

`npm_package.native_sha256` pins the **content** of the bundled executable
(`e5ef3c4b…d749e96` for 0.153.3). Package name, version, platform, and
architecture are checked first; then the resolved file is digested and compared.
A substituted or tampered binary inside an otherwise well-formed, correctly
versioned package tree is still refused. The pin moves only with an approved
version change.

#### The approval policy is an override, not a flag

`-a` / `--ask-for-approval` exists **only on the top-level command** in 0.153.3.
`codex exec` refuses it, parse-only and proven against the genuine binary:

```
codex exec -a never --help                 -> exit 2, unexpected argument '-a'
codex exec --ask-for-approval never --help -> exit 2, unexpected argument
codex exec -c approval_policy="never" --help -> exit 0
```

The complete fixed array, including `-c windows.sandbox="elevated"`, was proven
parse-only against the genuine 0.153.3 binary (a trailing `--help` makes clap
parse, print, and exit without inference) and exits 0.

`approval_policy` is the recognised configuration key for the same setting — it
appears in the binary's own configuration-key table beside `sandbox_mode` and
`model`, and in its diagnostic text as `approval_policy = "never"` — and it is
delivered exactly the way the reasoning effort already is. Only `never` is ever
emitted: the policy pins the value, and the array builder refuses anything else
even if that check were bypassed. The sandbox stays `read-only` regardless, which
is the protection that actually matters; the override removes the prompt rather
than granting anything.

### Executable resolution

The production CLI cannot supply a path. `codex` is resolved on the current search
path, then required to be an existing **regular file**, not a symlink, junction, or
reparse point, with an accepted basename (`codex` / `codex.exe`), whose local
`codex --version` prints exactly `codex-cli 0.153.3`. That probe is a local
capability check, not a model request. Tests substitute a fake only through a
module-level seam that no CLI flag and no envelope can reach.

#### The Windows npm install ships no executable

A global install writes three shims beside the npm prefix — an extension-less
POSIX shell script, a `.cmd`, and a `.ps1` — and **none of them is an executable
image**. Each merely re-execs the JavaScript launcher inside the package, which
computes a Rust target triple from the running platform and architecture,
resolves the matching optional dependency, and starts the native binary directly.

Windows cannot `CreateProcess` an extension-less shell script, so selecting the
shim fails with `WinError 193`. Since the runner spawns with `shell=False` — which
is not negotiable — it reproduces the launcher's own resolution instead:

1. A real `codex.exe` on the search path wins outright and is used directly.
2. Otherwise the shim is used **as a locator only**, never executed. Its directory
   names the npm prefix, and from there the layout is fixed:
   `node_modules/@openai/codex` → `node_modules/@openai/codex-<os>-<cpu>` →
   `vendor/<target triple>/bin/codex.exe`.

Every step is validated before the next: both manifests must name the package
exactly `@openai/codex`; the root version must equal the accepted version; the
platform package must pin `<version>-<os>-<cpu>` and declare this `os` and `cpu`;
no component may be a symlink, junction, or reparse point; and the final path is
canonicalised and required to remain **inside** the package tree. A missing,
malformed, oversized, renamed, mismatched, or substituted package stops the run.

`codex.cmd` and `codex.ps1` are never candidates by construction, and no shell,
command interpreter, or Node process is ever placed between the runner and the
binary. The internal `.plugin-appserver` executable is not on the search path and
is never reachable by this walk.

This changes only *which file is started*. The subcommand, every fixed flag, the
stdin prompt form, the child environment allowlist, the one-attempt rule, and the
no-retry rule are all unchanged.

### Child environment minimization

The parent environment is **never** forwarded. Only these names are passed, and
only when the parent already has them:

`APPDATA` · `CODEX_HOME` · `HOME` · `LOCALAPPDATA` · `PATH` · `SystemRoot` ·
`TEMP` · `TMP` · `TMPDIR` · `USERPROFILE`

`CODEX_HOME` is included because local help states `--ignore-user-config` still
resolves authentication through it. No API key, broker credential, Anthropic
variable, or trading flag can reach the child, because nothing outside the fixed
list is copied. **No value is ever printed or recorded** — only the count and the
names.

### The prompt

Built by the runner, deterministic (identical bytes for the same request), UTF-8,
delivered on stdin. It binds phase, branch, full HEAD, registry revision,
registry expected commit, request id, and the logical repository and worktree
identity; carries only the relay's normalized bounded evidence; labels that
evidence **UNTRUSTED DATA** and forbids following any instruction inside it;
requires read-only behaviour; asks for exactly one verdict; states that **PASS is
not authorization**; requires the committed verdict schema and the exact
non-authorization sentence; and instructs Codex to choose `STOP` on stale state,
ambiguity, protected-boundary involvement, or insufficient evidence. It contains
no machine path, username, secret, environment value, conversation history, or
unrelated repository content — and no file contents at all.

### Preconditions — all required before a child may start

- the mailbox holds exactly one valid pending request, and the chain verifies
- the request is bound to the current clean branch and HEAD
- the registry revision matches the request
- the request's `registry_expected_commit` equals HEAD
- the Claude session is **paused**
- exactly one Codex reviewer session exists, and it is active, live, owned by
  Codex, on the matching branch / HEAD / worktree, with an **empty write scope**
- no other live session holds a write scope
- no relay lock, registry lock, or temporary residue is present

The runner **reads** registry state only. It never pauses, registers, closes,
resumes, or advances a session.

### Link and reparse-point refusal

The resolved executable is refused if it is a symbolic link or a reparse point,
and must be an existing regular file with an accepted basename. The temporary
response directory is refused if it is a link **or** a reparse point, and again if
its resolved real path falls outside the mailbox root — a Windows junction reports
`islink()` as `False`, so the attribute is checked as well as the destination.
`FILE_ATTRIBUTE_REPARSE_POINT` is taken from `stat` where defined and pinned to
the Win32 value `0x400` otherwise, so the check is a real branch on every
platform.

### Private response handling

The response file is created under `<mailbox>/runner-tmp/` — a sibling of the
mailbox file, outside the `archive/` namespace, never the mailbox itself. The name
is unpredictable (`secrets.token_hex`), the directory is created `0o700`, a linked
directory stops the run, and the envelope cannot influence the path. Codex writes
there only through `-o`. Child stdout and stderr are captured, bounded, and
**never echoed**; only a sanitized status, exit classification, duration bucket,
response hash, and validation result are recorded. The runner removes only its own
file and never touches foreign content.

### One attempt, consumed on start — no retry, ever

**The moment the child process starts, the review opportunity for that
`(phase, head)` is spent** — whether Codex succeeds, fails, times out, writes
nothing, or returns something invalid. That is the anti-runaway design. There is
no retry flag, no loop, and no code path that re-invokes `review-once`. A failed
attempt returns control to Pedro and needs a **new, explicitly approved recovery
phase**. Because the relay caps one review per `(phase, head)`, a second run finds
nothing pending and stops.

A stop *before* the spawn (a failed precondition) does **not** consume the attempt.

---

## Manual lifecycle around one review

Every step outside the runner is a person's action. Nothing here is automated.

1. **Pause** the Claude session (`session_registry.py pause`).
2. **Initialize** the mailbox directory — *not yet authorized* (B1.11).
3. **Submit** the request (`codex_relay.py submit`).
4. **Register** the read-only Codex reviewer session, empty write scope.
5. **Run once** (`codex_review_runner.py review-once`) — *not yet authorized* (B1.10).
6. **Close** the reviewer session.
7. **Resume** the Claude session.

**A live review has never been performed and is not authorized.**

---

## Session Registry lifecycle (planned for the runner, not built here)

The transport only **reads** the registry. The lifecycle below belongs to the
future one-shot runner and is documented so it is designed before it is built:

1. Claude submits only from a clean tree with HEAD == registered `expected_commit`.
2. Claude transitions its own record to `paused` before the review.
3. The reviewer is registered as a separate record with an **empty write scope**.
4. Existing collision rules are unchanged — nothing is loosened for convenience.
5. The reviewer record is `close`d; `session_registry.py` has no delete or prune,
   so history is preserved.
6. Claude resumes its own record. Because the review is read-only,
   `expected_commit` is untouched and stays correct by construction.
7. Any staleness mid-review **stops** the exchange and goes to Pedro.

### Why an empty write scope is not sufficient on its own

Step 3 was originally written as though an empty write scope made the reviewer
structurally non-colliding. It does not, and Phase 4F stopped on exactly that:
`same-worktree-with-write` fires when **either** side writes, so the paused
Claude record kept blocking the reviewer no matter how small its read scope was —
an empty reviewer scope still collided. Meanwhile the runner requires the Claude
record to be `paused`, and only a `closed` record avoided the collision, which in
turn failed that requirement.

The registry now treats an explicit pause as what it is. A writer that has
**paused** and whose heartbeat still proves it alive holds its write scope *in
reserve*, so a proposal with **no write scope of its own** may register beside
it. Only `same-worktree-with-write`, `same-branch-different-worktree`, and
`read-write-overlap` are discounted, and only in that situation.

This is a lifecycle-state fact, not an approval. It does nothing when the
proposal writes, when the other session is active or closing, or when that
session is stale, ambiguous, or shows a future heartbeat — those still block or
escalate to Pedro. `duplicate-session-id`, `expected-commit-mismatch`, every
protected-scope check, and all write/write and write/read overlaps are untouched.
`resume` judges the returning writer by its scopes, as if already active, so it
is refused while a live reviewer is reading and succeeds once that reviewer is
closed. No `--force`, `--override`, or approval flag exists.

---

## What still has to be built

| Item | Status |
|---|---|
| Relay transport | **done, local only** |
| One-shot Codex runner | **done, local only** — never run against a real model |
| Controlled first live review | **TODO — not authorized** |
| Real mailbox initialization at `${HOME}/.claude/nova-relay/` | **TODO — not created** |

Automatic Claude/Codex communication is **not** operational and is not claimed to
be. Every review is started by a person, once, for one request.
