# Responsibility Contract

Who owns what, and the invariants that do not bend.

---

## 1. Actor boundaries

| Actor | Owns | Explicitly may not |
|---|---|---|
| **Pedro** | Ownership, all approvals, capital and risk mandate, strategy authority, promotion of research to rules, every push / merge / deploy | — |
| **Claude Code / Cowork** | Engineering, refactoring, tests, documentation, audits, scheduled repository workflows, proposals | Make or influence trading decisions; submit orders; enable guarded flags; edit strategy specs or risk limits; push, merge, or deploy |
| **Obsidian** | Durable curated knowledge, human-readable project memory, decision records, research synthesis for humans | Execute anything. It is a read/write document store with **no runtime** — no scripts, no scheduled actions, no repository writes |
| **NOVA Brain** | Financial understanding, market intelligence, research synthesis, decision *support* | Submit broker orders; size positions; alter risk limits; write to the execution path. Its output is **analysis, never instruction** |
| **NOVA Trader** (future) | Deterministic trading policy inside an approved strategy and an approved risk envelope | Override risk controls; expand its own mandate; act on unapproved strategies; trade funded capital before staged authorization |
| **Risk engine** | Hard limits, kill switches, daily loss caps, concurrency caps, session gates | Be bypassed, disabled, or overridden by any agent above it |
| **Execution engine** | Broker mechanics only — order construction, submission, reconciliation | Originate a decision. It executes what policy hands it, after risk approves |

---

## 2. Invariants

1. **Claude does not decide trades.** Not directly, not by proposing a signal, not
   by tuning a strategy parameter.
2. **Obsidian executes nothing.** Knowledge in, knowledge out.
3. **NOVA Brain cannot submit broker orders.** Its output enters a policy layer,
   never the order path.
4. **LLM output stays outside the live order path.** Every order is produced by
   deterministic code. An LLM may explain an order before or after; it may never
   be a link in the chain that creates one.
5. **The future Trader cannot override deterministic risk controls.** Risk is
   upstream and independent. If risk and policy disagree, risk wins — always, with
   no appeal path in code.
6. **Autonomy progresses only through the approved validation ladder:** documented
   strategy → backtest → out-of-sample validation → paper account → governance dry
   run → Pedro's explicit funded-account authorization → monitored limited
   autonomy → expansion only through new approval. No stage may be skipped, and
   each is a separate approval.

---

## 3. What the retirement guard does and does not prove

An earlier draft claimed the guard "enforces invariants #1 and #4 mechanically."
**That claim was too broad and is corrected here.**

What the installed guard (`.claude/hooks/nova_guard_hook.py`) actually enforces is
narrow and specific:

- the **retired-subsystem boundary** — protected files cannot be modified by any
  tool or shell command;
- **kill-switch integrity** in `main.py` and `monitor.py` — edits touching
  retirement-guard text, whole-file replacement, and shell mutation are blocked;
- **activation flags** — `NOVA_TRADING_SUBSYSTEM_ENABLED` and `NOVA_AUTO_EXECUTE`
  cannot be set to an enabling value through any assignment form it recognizes.

That is a boundary guard, not a general prohibition on influence. It does **not**
by itself guarantee that Claude can never influence trading elsewhere. It cannot:
it inspects tool calls against a fixed path and flag list, so it says nothing
about new code in unguarded paths, a strategy parameter changed in a file it does
not protect, advice given in prose, or a future system that reads Claude's output.

The broader invariant is enforced by a layered arrangement, of which the guard is
only the innermost mechanical layer:

1. **Approval policy** — every mutation names its exact targets; no standing
   approvals; the FA/AR/AAM/AM classification governs what may run unattended.
2. **Worktree separation** — Claude tooling, application development, and research
   occupy separate worktrees with disjoint file domains.
3. **Ownership boundaries** — strategy specs, risk limits, and rule promotion
   belong to Pedro alone; automation may propose, never promote.
4. **Deterministic risk and execution design** — the order path contains no LLM.
   Risk is upstream of policy and independent of it.
5. **Future architecture controls** — the Brain → policy → risk → execution
   interface must be designed so analysis cannot become an instruction without
   passing a deterministic, auditable gate.

**No single mechanism carries this invariant.** Any claim that "the hook makes it
safe" is a category error: the hook makes a specific, verifiable subset safe, and
that subset is worth exactly what its test suite demonstrates — no more.

---

## 4. Standing prohibitions

No approval, standing or otherwise, authorizes any automation to:

- push, merge, deploy, rebase, `reset --hard`, `restore`, or `clean`;
- edit a protected file or weaken the test fixtures that enforce the retirement;
- set `NOVA_TRADING_SUBSYSTEM_ENABLED` or `NOVA_AUTO_EXECUTE` to an enabling value;
- promote research to a NOVA rule;
- print a credential value;
- claim a test result it did not measure;
- submit or cancel a broker order;
- activate, merge, or advance archived Execution Bot Phase 8 as approved
  trading-bot development;
- grant itself a permanent permission approval.

---

## 5. Current authorization state

**Nothing in this repository authorizes autonomous or funded trading.** There is
no approved strategy, no active execution capability, and no completed stage of
the validation ladder. The trading subsystem is retired, its kill switch defaults
to off, and the guard blocks re-enablement.

This contract describes boundaries. It grants no permission.
