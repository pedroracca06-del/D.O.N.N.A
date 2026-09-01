# Approval Matrix

How much approval a given action needs, and what makes an approval valid.

## Classification vocabulary

| Class | Meaning | Approval |
|---|---|---|
| **FA** — fully automatic | Runs unattended. Reads state and emits reports. Mutates no tracked content and reaches nothing outside the machine. | none |
| **AR** — automatic, read-only | Runs unattended. May read any repository or state file and produce analysis. Writes nothing. | none |
| **AAM** — automatic with approval before mutation | Analyses freely; mutates only after an approval naming the exact targets. | per-action |
| **AM** — always manual | Pedro performs it, or explicitly commands it each time. No standing approval exists. | every time |

**"Allow once" is the default answer to every tool permission prompt.** A
permanent "don't ask again" approval is never selected without Pedro's explicit
instruction, because it silently converts an AAM action into an FA one.

## 1. Fully automatic (FA / AR)

- Read-only evidence formatting — turning a command's real output into a report
- Repository staleness detection — re-reading HEAD, refs, and file hashes before reporting
- Hash, count, and status reporting
- Test-result normalization — command + counts + failures, verbatim
- Read-only A7 scans — secrets, machine paths, protected files, runtime data, committed paths

These may run at any time. None of them writes to a tracked file.

## 2. Approval required before mutation (AAM)

Each requires an approval that names the literal targets before the action runs.

- File edits of any kind
- Candidate generation that writes inside a worktree
- Staging plans (`git add` by exact path)
- Local commits
- Research import into the repository
- Obsidian writes
- Branch creation and worktree creation
- Permission changes (`settings.local.json`, `settings.json`, hooks)

## 3. Always ask Pedro immediately before (AM)

These either reach another machine or destroy work. There is no standing approval
for any of them, ever.

- `push`
- `merge`
- `deploy`
- Branch deletion
- Worktree removal
- `reset`
- `restore`
- `clean`
- Secrets or credential changes
- Risk or strategy changes
- Broker or execution changes
- Promotion of research into active NOVA rules

## 4. Always prohibited for Claude/Cowork

No approval, standing or otherwise, authorizes these. If one appears necessary,
the correct response is to stop and say so.

- Submitting or cancelling broker orders
- Enabling the retired trading flags (`NOVA_TRADING_SUBSYSTEM_ENABLED`, `NOVA_AUTO_EXECUTE`)
- Bypassing, disguising, splitting, or weakening the retirement guard
- Promoting research to strategy without Pedro
- Altering risk limits or kill switches
- Placing an LLM in the live order path
- Granting a permanent permission approval without Pedro

## 5. What makes an approval valid

An approval counts only when the request states, **before** the action:

1. **Exactly which files or resources change** — literal paths, no globs.
2. **What the change is** — the diff, the message, the rule list.
3. **The inverse** — how to undo it.
4. **The blast radius** — local only, or does it reach another machine or service.

An approval is **scoped to that action**. It does not extend to the same action
later, a similar action on a different path, a retry after failure, or a broader
version of the same operation.

## 6. Escalation triggers — stop and ask

- HEAD, the index, or a target file changed since it was measured
- A protected file appears in a proposed mutation
- A guarded flag would be set to an enabling value
- An A7 gate fails on staged content
- An unclassified path is inside a proposed commit
- A test selector cannot map a changed path and full regression was declined
- Research would be written into the approved-rules layer
- Any action would reach the network, a broker, a chat service, or a deploy
- Two sessions or worktrees appear to target the same branch

## 7. Reporting discipline

- **Never claim a test result that was not measured.** Command, counts, failures.
- **Never weaken a test to make a change pass.**
- **Never print a credential value**, in output, logs, or a report.
- Report a guard block as a finding. Do not route around it.
