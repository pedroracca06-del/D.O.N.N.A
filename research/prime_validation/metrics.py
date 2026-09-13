"""Honest outcome metrics over provenance-complete, finalized historical records.

Every metric here is descriptive arithmetic over records that are already
labeled and finalized. Nothing in this module optimizes, ranks, grades, or
recommends, and no number it returns is a profitability claim: see
``docs/PRIME_EMOTIONLESS_VALIDATION.md``.

The design priority is *not being misleading*:

* an empty sample returns ``None`` for every rate, never ``0.0``;
* a sample below the caller's declared minimum withholds rate metrics entirely
  rather than printing a confident-looking fraction of four trades;
* profit factor with zero losses is ``None`` with an explicit
  ``undefined_no_losses`` state — never ``inf``, never a huge number;
* aggregation is permitted only over provenance-complete records, so a metric
  can always be traced back to a source id and a content hash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from research.prime_validation.schema import (
    OUTCOME_BREAKEVEN,
    OUTCOME_LOSS,
    OUTCOME_WIN,
    PrimeValidationError,
    ValidatedCandidate,
    coerce_records,
    find_integrity_issues,
    sort_chronologically,
)

SCOPE_COMBINED_POLICY = "combined-policy"

DATA_STATE_EMPTY = "empty"
DATA_STATE_BELOW_MINIMUM = "below_minimum"
DATA_STATE_COMPLETE = "complete"

PF_DEFINED = "defined"
PF_UNDEFINED_NO_SAMPLE = "undefined_no_sample"
PF_UNDEFINED_BELOW_MINIMUM = "undefined_below_minimum"
PF_UNDEFINED_NO_LOSSES = "undefined_no_losses"

#: The R threshold for the "2R or better" hit rate. A reporting threshold, not a
#: target and not a rule.
TARGET_R_THRESHOLD = 2.0

NO_PROFITABILITY_CLAIM_NOTE = (
    "descriptive historical arithmetic only; this is not a profitability claim "
    "and authorizes nothing"
)


class MetricsValidationError(PrimeValidationError):
    """Metrics were refused. No partial or approximate report is returned."""


@dataclass(frozen=True, slots=True)
class MetricsReport:
    """A frozen, self-describing metrics report.

    Rate-style fields are ``None`` whenever the sample does not honestly support
    them. ``data_state``, ``profit_factor_state``, and ``notes`` say why, so a
    reader never has to guess whether a missing number means zero.
    """

    scope: str
    sample_count: int
    wins: int
    losses: int
    breakevens: int
    win_rate: float | None
    expectancy_r: float | None
    profit_factor: float | None
    profit_factor_state: str
    max_drawdown_r: float | None
    longest_win_streak: int
    longest_loss_streak: int
    hit_rate_2r_or_better: float | None
    gross_profit_r: float
    gross_loss_r: float
    total_r: float
    minimum_sample: int
    data_state: str
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_rate_metrics(self) -> bool:
        return self.win_rate is not None

    def to_mapping(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "scope": self.scope,
                "sample_count": self.sample_count,
                "wins": self.wins,
                "losses": self.losses,
                "breakevens": self.breakevens,
                "win_rate": self.win_rate,
                "expectancy_r": self.expectancy_r,
                "profit_factor": self.profit_factor,
                "profit_factor_state": self.profit_factor_state,
                "max_drawdown_r": self.max_drawdown_r,
                "longest_win_streak": self.longest_win_streak,
                "longest_loss_streak": self.longest_loss_streak,
                "hit_rate_2r_or_better": self.hit_rate_2r_or_better,
                "gross_profit_r": self.gross_profit_r,
                "gross_loss_r": self.gross_loss_r,
                "total_r": self.total_r,
                "minimum_sample": self.minimum_sample,
                "data_state": self.data_state,
                "notes": self.notes,
            }
        )


def _require_provenance_complete(
    records: Sequence[ValidatedCandidate], scope: str
) -> None:
    issues = find_integrity_issues(records)
    if issues:
        first = issues[0]
        raise MetricsValidationError(
            first.code,
            f"{first.message} ({len(issues)} integrity issue(s) total); metrics are "
            f"permitted only over provenance-complete records (scope {scope!r})",
            candidate_id=first.candidate_id,
        )


def compute_metrics(
    items: Iterable[ValidatedCandidate | Mapping[str, Any]],
    *,
    scope: str = SCOPE_COMBINED_POLICY,
    minimum_sample: int = 0,
) -> MetricsReport:
    """Compute descriptive metrics over one provenance-complete finalized sample.

    ``minimum_sample`` is the caller's declared threshold for treating rate
    metrics as reportable. It defaults to ``0``, which asserts no minimum — the
    report then says so in its notes rather than implying that a three-record
    win rate means something.
    """
    if isinstance(minimum_sample, bool) or not isinstance(minimum_sample, int):
        raise MetricsValidationError(
            "MINIMUM_SAMPLE_TYPE",
            f"minimum_sample must be an int, got {type(minimum_sample).__name__}",
        )
    if minimum_sample < 0:
        raise MetricsValidationError(
            "MINIMUM_SAMPLE_RANGE",
            f"minimum_sample must be non-negative, got {minimum_sample}",
        )

    records = coerce_records(items)
    _require_provenance_complete(records, scope)
    ordered = sort_chronologically(records)

    sample_count = len(ordered)
    wins = sum(1 for record in ordered if record.outcome == OUTCOME_WIN)
    losses = sum(1 for record in ordered if record.outcome == OUTCOME_LOSS)
    breakevens = sum(1 for record in ordered if record.outcome == OUTCOME_BREAKEVEN)

    r_series = [record.r_multiple for record in ordered]
    gross_profit = sum(value for value in r_series if value > 0.0)
    gross_loss = -sum(value for value in r_series if value < 0.0)
    total_r = sum(r_series)

    notes: list[str] = [NO_PROFITABILITY_CLAIM_NOTE]

    if sample_count == 0:
        return MetricsReport(
            scope=scope,
            sample_count=0,
            wins=0,
            losses=0,
            breakevens=0,
            win_rate=None,
            expectancy_r=None,
            profit_factor=None,
            profit_factor_state=PF_UNDEFINED_NO_SAMPLE,
            max_drawdown_r=None,
            longest_win_streak=0,
            longest_loss_streak=0,
            hit_rate_2r_or_better=None,
            gross_profit_r=0.0,
            gross_loss_r=0.0,
            total_r=0.0,
            minimum_sample=minimum_sample,
            data_state=DATA_STATE_EMPTY,
            notes=tuple(
                notes
                + [
                    "empty sample: every rate is undefined and is reported as None, "
                    "not as zero"
                ]
            ),
        )

    max_drawdown_r = _max_drawdown_r(r_series)
    longest_win_streak = _longest_streak(ordered, OUTCOME_WIN)
    longest_loss_streak = _longest_streak(ordered, OUTCOME_LOSS)

    if sample_count < minimum_sample:
        notes.append(
            f"sample of {sample_count} is below the caller's declared minimum of "
            f"{minimum_sample}: win rate, expectancy, profit factor, and the "
            f"{TARGET_R_THRESHOLD:g}R hit rate are withheld rather than reported "
            "from too little data"
        )
        return MetricsReport(
            scope=scope,
            sample_count=sample_count,
            wins=wins,
            losses=losses,
            breakevens=breakevens,
            win_rate=None,
            expectancy_r=None,
            profit_factor=None,
            profit_factor_state=PF_UNDEFINED_BELOW_MINIMUM,
            max_drawdown_r=max_drawdown_r,
            longest_win_streak=longest_win_streak,
            longest_loss_streak=longest_loss_streak,
            hit_rate_2r_or_better=None,
            gross_profit_r=gross_profit,
            gross_loss_r=gross_loss,
            total_r=total_r,
            minimum_sample=minimum_sample,
            data_state=DATA_STATE_BELOW_MINIMUM,
            notes=tuple(notes),
        )

    if minimum_sample == 0:
        notes.append(
            "caller declared no minimum sample; sample size is not evidence of "
            "anything by itself"
        )

    if gross_loss == 0.0:
        profit_factor: float | None = None
        profit_factor_state = PF_UNDEFINED_NO_LOSSES
        notes.append(
            "profit factor is undefined: the sample contains no losing record, so "
            "the ratio has a zero denominator and is reported as None rather than "
            "as an infinite or flattering number"
        )
    else:
        profit_factor = gross_profit / gross_loss
        profit_factor_state = PF_DEFINED

    return MetricsReport(
        scope=scope,
        sample_count=sample_count,
        wins=wins,
        losses=losses,
        breakevens=breakevens,
        win_rate=wins / sample_count,
        expectancy_r=total_r / sample_count,
        profit_factor=profit_factor,
        profit_factor_state=profit_factor_state,
        max_drawdown_r=max_drawdown_r,
        longest_win_streak=longest_win_streak,
        longest_loss_streak=longest_loss_streak,
        hit_rate_2r_or_better=sum(
            1 for value in r_series if value >= TARGET_R_THRESHOLD
        )
        / sample_count,
        gross_profit_r=gross_profit,
        gross_loss_r=gross_loss,
        total_r=total_r,
        minimum_sample=minimum_sample,
        data_state=DATA_STATE_COMPLETE,
        notes=tuple(notes),
    )


def _max_drawdown_r(r_series: Sequence[float]) -> float:
    """Largest peak-to-trough decline of the cumulative R curve, as a magnitude.

    Zero means the curve never traded below a prior peak. It is reported as a
    non-negative magnitude so a larger number always means a worse drawdown.
    """
    cumulative = 0.0
    peak = 0.0
    worst = 0.0
    for value in r_series:
        cumulative += value
        peak = max(peak, cumulative)
        worst = max(worst, peak - cumulative)
    return worst


def _longest_streak(records: Sequence[ValidatedCandidate], outcome: str) -> int:
    """Longest run of consecutive ``outcome`` records in chronological order.

    Any other finalized outcome ends the run, including a breakeven: a scratch is
    not a win and not a loss, and treating it as transparent would silently merge
    two separate runs into one longer-looking streak.
    """
    longest = 0
    current = 0
    for record in records:
        if record.outcome == outcome:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def metrics_by_model(
    items: Iterable[ValidatedCandidate | Mapping[str, Any]],
    *,
    minimum_sample: int = 0,
) -> Mapping[str, MetricsReport]:
    """Per-model reports for the models actually present in the sample.

    Models absent from the input are absent from the output. Emitting an empty
    report for a model that was never observed would invite reading its zeros as
    measurements.
    """
    records = coerce_records(items)
    _require_provenance_complete(records, "per-model")

    grouped: dict[str, list[ValidatedCandidate]] = {}
    for record in records:
        grouped.setdefault(record.model, []).append(record)

    return MappingProxyType(
        {
            model: compute_metrics(
                bucket, scope=f"model:{model}", minimum_sample=minimum_sample
            )
            for model, bucket in sorted(grouped.items())
        }
    )


def combined_policy_metrics(
    items: Iterable[ValidatedCandidate | Mapping[str, Any]],
    *,
    minimum_sample: int = 0,
) -> MetricsReport:
    """One report over the whole provenance-complete sample, across all models."""
    return compute_metrics(
        items, scope=SCOPE_COMBINED_POLICY, minimum_sample=minimum_sample
    )


__all__ = [
    "DATA_STATE_BELOW_MINIMUM",
    "DATA_STATE_COMPLETE",
    "DATA_STATE_EMPTY",
    "NO_PROFITABILITY_CLAIM_NOTE",
    "PF_DEFINED",
    "PF_UNDEFINED_BELOW_MINIMUM",
    "PF_UNDEFINED_NO_LOSSES",
    "PF_UNDEFINED_NO_SAMPLE",
    "SCOPE_COMBINED_POLICY",
    "TARGET_R_THRESHOLD",
    "MetricsReport",
    "MetricsValidationError",
    "combined_policy_metrics",
    "compute_metrics",
    "metrics_by_model",
]
