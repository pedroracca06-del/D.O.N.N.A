"""Read-only selection engine: at most one candidate per session, caller-keyed.

The engine does exactly one mechanical thing: given candidates that an upstream
human or separately approved deterministic process has **already** marked
eligible, it applies a **caller-supplied** deterministic ordering key and records
which candidate that key selects in each session.

What it refuses to do, by construction:

* it does not detect, scan for, or infer a setup — ``already_eligible`` must
  already be true, and a non-eligible record is a rejection, not a candidate;
* it holds **no** built-in strategy priority. There is no table here ranking
  Strict OTE above ORB or vice versa. If the caller supplies no key, nothing is
  selected, because inventing one would be the engine deciding a trade;
* it does not grade, score, size, execute, or notify anything;
* it resolves no tie by itself. Two candidates the caller's key ranks equally are
  an explicit ``AMBIGUOUS_TIE`` rejection;
* it never hands a caller-supplied key the outcome. ``selection_key`` and
  ``session_key`` each receive a fresh :class:`SelectionView` holding only what
  was knowable at the candidate instant — no exit price, outcome, realised R,
  or actual trade state — so a key cannot pick winners by accident. The
  finalized record is joined back to the evidence only after the key has run.

Everything the engine returns is **evidence**: a neutral description of what the
caller's own key would have selected, what it would have skipped, and what was
actually taken, missed, or deviated from. None of it is an instruction, a
recommendation, or a performance claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Hashable, Iterable, Mapping

from research.prime_validation.schema import (
    ACTUAL_MISSED,
    ACTUAL_NOT_APPLICABLE,
    ACTUAL_RULE_DEVIATION,
    ACTUAL_TAKEN,
    PrimeValidationError,
    SelectionKeyFn,
    SessionKeyFn,
    ValidatedCandidate,
    chronological_key,
    coerce_records,
    find_integrity_issues,
    selection_view_of,
    session_date_key,
    sort_chronologically,
)

DISPOSITION_SELECTED = "selected"
DISPOSITION_SKIPPED = "skipped"
DISPOSITIONS: frozenset[str] = frozenset({DISPOSITION_SELECTED, DISPOSITION_SKIPPED})

#: Neutral descriptive labels for the (disposition, actual trade state) pairing.
#: These are observations for review, not verdicts: "skipped_but_taken" says the
#: caller's key would not have picked a candidate that was in fact traded. It
#: does not say either party was right.
COMPARISON_LABELS: Mapping[tuple[str, str], str] = MappingProxyType(
    {
        (DISPOSITION_SELECTED, ACTUAL_TAKEN): "selected_and_taken",
        (DISPOSITION_SELECTED, ACTUAL_MISSED): "selected_but_missed",
        (DISPOSITION_SELECTED, ACTUAL_RULE_DEVIATION): "selected_with_rule_deviation",
        (DISPOSITION_SELECTED, ACTUAL_NOT_APPLICABLE): "selected_no_actual_trade",
        (DISPOSITION_SKIPPED, ACTUAL_TAKEN): "skipped_but_taken",
        (DISPOSITION_SKIPPED, ACTUAL_MISSED): "skipped_and_missed",
        (DISPOSITION_SKIPPED, ACTUAL_RULE_DEVIATION): "skipped_with_rule_deviation",
        (DISPOSITION_SKIPPED, ACTUAL_NOT_APPLICABLE): "skipped_no_actual_trade",
    }
)


class EngineValidationError(PrimeValidationError):
    """The engine refused to produce evidence. Nothing partial is returned."""


@dataclass(frozen=True, slots=True)
class SelectionComparison:
    """One candidate's disposition under the caller's key, beside what happened."""

    candidate_id: str
    model: str
    symbol: str
    direction: str
    session: Hashable
    disposition: str
    actual_trade_state: str
    outcome: str
    r_multiple: float
    selection_key: tuple[Any, ...]
    label: str

    def to_mapping(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "candidate_id": self.candidate_id,
                "model": self.model,
                "symbol": self.symbol,
                "direction": self.direction,
                "session": str(self.session),
                "disposition": self.disposition,
                "actual_trade_state": self.actual_trade_state,
                "outcome": self.outcome,
                "r_multiple": self.r_multiple,
                "label": self.label,
            }
        )


@dataclass(frozen=True, slots=True)
class SessionSelection:
    """The single selected candidate for one session, plus everything skipped."""

    session: Hashable
    selected: ValidatedCandidate
    selected_key: tuple[Any, ...]
    skipped: tuple[ValidatedCandidate, ...]
    comparisons: tuple[SelectionComparison, ...]

    @property
    def considered_count(self) -> int:
        return 1 + len(self.skipped)


@dataclass(frozen=True, slots=True)
class SelectionEvidence:
    """Frozen evidence for a whole run. Read it; do not act on it."""

    selections: tuple[SessionSelection, ...]

    @property
    def session_count(self) -> int:
        return len(self.selections)

    @property
    def selected(self) -> tuple[ValidatedCandidate, ...]:
        return tuple(selection.selected for selection in self.selections)

    @property
    def skipped(self) -> tuple[ValidatedCandidate, ...]:
        return tuple(
            record for selection in self.selections for record in selection.skipped
        )

    @property
    def comparisons(self) -> tuple[SelectionComparison, ...]:
        return tuple(
            comparison
            for selection in self.selections
            for comparison in selection.comparisons
        )

    def comparisons_by_label(self) -> Mapping[str, int]:
        """How many comparisons carry each descriptive label."""
        counts: dict[str, int] = {}
        for comparison in self.comparisons:
            counts[comparison.label] = counts.get(comparison.label, 0) + 1
        return MappingProxyType(dict(sorted(counts.items())))


def select_one_per_session(
    items: Iterable[ValidatedCandidate | Mapping[str, Any]],
    *,
    selection_key: SelectionKeyFn,
    session_key: SessionKeyFn = session_date_key,
) -> SelectionEvidence:
    """Select at most one already-eligible candidate per session and return evidence.

    ``selection_key`` is mandatory and belongs to the caller. It must return a
    tuple, and the lowest tuple in a session wins — so the caller encodes its own
    preference order explicitly, in its own code, where it can be reviewed. The
    engine supplies no fallback ordering: an unresolved tie is rejected rather
    than broken by an arbitrary rule the engine would have had to invent.

    Both keys receive a :class:`~research.prime_validation.schema.SelectionView`
    and nothing else. The default ``session_key`` groups by the view's
    ``session_date``.
    """
    if not callable(selection_key):
        raise EngineValidationError(
            "SELECTION_KEY_REQUIRED",
            "selection_key must be a callable supplied by the caller; the engine "
            "holds no built-in strategy priority",
        )
    if not callable(session_key):
        raise EngineValidationError(
            "SESSION_KEY_INVALID",
            f"session_key must be callable, got {type(session_key).__name__}",
        )

    records = coerce_records(items)

    issues = find_integrity_issues(records)
    if issues:
        first = issues[0]
        raise EngineValidationError(
            first.code,
            f"{first.message} ({len(issues)} integrity issue(s) total); a "
            "contaminated set cannot produce evidence",
            candidate_id=first.candidate_id,
        )

    for record in records:
        if not record.already_eligible:
            raise EngineValidationError(
                "NOT_ELIGIBLE",
                "the engine accepts already-eligible candidates only; it does not "
                "detect setups or decide eligibility",
                candidate_id=record.candidate_id,
            )

    # The session key sees a detached pre-decision view. The finalized record
    # stays inside the engine and is only bucketed under the returned key.
    groups: dict[Hashable, list[ValidatedCandidate]] = {}
    for record in sort_chronologically(records):
        group = session_key(selection_view_of(record))
        try:
            bucket = groups.setdefault(group, [])
        except TypeError as exc:
            raise EngineValidationError(
                "SESSION_KEY_UNHASHABLE",
                f"session_key returned an unhashable value {group!r}",
                candidate_id=record.candidate_id,
            ) from exc
        bucket.append(record)

    selections = [
        _select_within_session(group, tuple(bucket), selection_key)
        for group, bucket in groups.items()
    ]
    selections.sort(key=lambda selection: chronological_key(selection.selected))
    return SelectionEvidence(selections=tuple(selections))


def _select_within_session(
    session: Hashable,
    bucket: tuple[ValidatedCandidate, ...],
    selection_key: SelectionKeyFn,
) -> SessionSelection:
    # The selection key ranks detached pre-decision views only; each key is
    # paired back to its finalized record here, after the key has been computed.
    keyed: list[tuple[tuple[Any, ...], ValidatedCandidate]] = []
    for record in bucket:
        key = selection_key(selection_view_of(record))
        if not isinstance(key, tuple):
            raise EngineValidationError(
                "SELECTION_KEY_INVALID",
                f"selection_key must return a tuple, got {type(key).__name__}",
                candidate_id=record.candidate_id,
            )
        keyed.append((key, record))

    try:
        best_key = min(key for key, _ in keyed)
    except TypeError as exc:
        raise EngineValidationError(
            "SELECTION_KEY_INCOMPARABLE",
            f"selection_key produced mutually incomparable keys within session "
            f"{session!r}: {exc}",
            candidate_id=bucket[0].candidate_id,
        ) from exc

    tied = [record for key, record in keyed if key == best_key]
    if len(tied) > 1:
        tied_ids = sorted(record.candidate_id for record in tied)
        raise EngineValidationError(
            "AMBIGUOUS_TIE",
            f"selection_key does not fully resolve session {session!r}: candidates "
            f"{tied_ids} share the winning key {best_key!r}. Extend the caller's key "
            "rather than letting the engine pick",
            candidate_id=tied_ids[0],
        )

    selected = tied[0]
    skipped = tuple(record for record in bucket if record is not selected)

    comparisons = [
        _comparison(session, selected, best_key, DISPOSITION_SELECTED)
    ]
    key_by_id = {record.candidate_id: key for key, record in keyed}
    comparisons.extend(
        _comparison(
            session, record, key_by_id[record.candidate_id], DISPOSITION_SKIPPED
        )
        for record in skipped
    )

    return SessionSelection(
        session=session,
        selected=selected,
        selected_key=best_key,
        skipped=skipped,
        comparisons=tuple(comparisons),
    )


def _comparison(
    session: Hashable,
    record: ValidatedCandidate,
    key: tuple[Any, ...],
    disposition: str,
) -> SelectionComparison:
    return SelectionComparison(
        candidate_id=record.candidate_id,
        model=record.model,
        symbol=record.symbol,
        direction=record.direction,
        session=session,
        disposition=disposition,
        actual_trade_state=record.actual_trade_state,
        outcome=record.outcome,
        r_multiple=record.r_multiple,
        selection_key=key,
        label=COMPARISON_LABELS[(disposition, record.actual_trade_state)],
    )


__all__ = [
    "COMPARISON_LABELS",
    "DISPOSITIONS",
    "DISPOSITION_SELECTED",
    "DISPOSITION_SKIPPED",
    "EngineValidationError",
    "SelectionComparison",
    "SelectionEvidence",
    "SessionSelection",
    "select_one_per_session",
]
