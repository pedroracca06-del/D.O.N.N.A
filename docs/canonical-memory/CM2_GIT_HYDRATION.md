# CM-2 Git-only compact hydration

CM-2 is an offline, standard-library-only prototype over the verified CM-1 Git mirror.
It is not wired into the Assistant, runtime state, Obsidian, a database, a model call,
broker execution, or any trading surface.

## Pin and boundary

- Base commit: `00024ccf1d6ef7f373cb400b52b9d85921ead33a`.
- Verified tree: `cd857fe1faf425a58ec1b3c8450b8c759900a634`.
- Currentness model: `bound_commit_only`.
- Budget estimator: `utf8-bytes-v1`; units are `utf8_bytes`, never claimed tokens.
- Exactly three PRIME models remain locked: Strict OTE, 10AM Key Level Open, ORB.
- FVG, OB, SMT, and STDV are context/confluence only. PROS remains superseded.

## Contract

`hydrate(snapshot, mission, agent_id, budget)` returns an immutable packet or a
closed refusal. Mission free text affects token overlap for T4-T7 only and is never
rendered. Structured scope and the closed agent projection decide eligibility.
All evaluated records are included or receive exactly one exclusion reason.

The mandatory Git-bootstrap core is the versioned literal in `constants.py`. It
contains only records representable by CM-1; it never names guarded flags. Missing,
conflicted, or otherwise inadmissible mandatory records refuse closed.

## Bootstrap adaptations

CM-1 persists no validity windows or relationship graph. Therefore F4 is disclosed
as bound-commit-only. The real Git snapshot has no relationship notices; injected
immutable snapshots exercise conflict and stale paths. G8a proves commit mismatch
and packet freshness without mutating Git. Write-path stale-proposal rejection is
deferred to CM-3.

## Evidence

G0/G1/G2/G4/G6/G7/G8a/G10/G11 are covered by separate focused modules. G3/G5/G9/G12
are not applicable because CM-2 has no database, write path, billed model call, or
deployment. Cross-platform evidence is reported only when a second safe platform is
actually measured. G11 compares deterministic repository-resident baselines and
excludes conversation history explicitly.

Nothing here grants execution authority or changes strategy, risk, or trading behavior.
