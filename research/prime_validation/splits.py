"""Deterministic chronological train / validation / out-of-sample partitions.

The only ordering this module knows is time. There is no shuffle, no random
seed, no stratification, and no re-balancing: a partition boundary is decided by
the chronological position of a record and nothing else, so the same input
always yields byte-identical partitions.

Everything that could let a later observation inform an earlier decision is a
hard rejection rather than a warning:

* duplicate candidate identity;
* a shared (symbol, model, instant) claimed by two identities;
* a partition boundary that two records straddle with the same instant;
* one ``source_id`` carrying two different content hashes;
* an empty partition or an invalid ratio triple;
* a missing, non-datetime, naive, or non-UTC ``as_of`` cutoff — the cutoff is
  never taken from the wall clock;
* any record dated after the declared ``as_of`` cutoff.

This module is read-only: it partitions records in memory and returns frozen
tuples. It writes nothing, fetches nothing, and grades nothing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from research.prime_validation.schema import (
    PrimeValidationError,
    ValidatedCandidate,
    coerce_records,
    find_integrity_issues,
    parse_utc_timestamp,
    sort_chronologically,
)

PARTITION_TRAIN = "train"
PARTITION_VALIDATION = "validation"
PARTITION_OUT_OF_SAMPLE = "out_of_sample"
PARTITION_NAMES: tuple[str, ...] = (
    PARTITION_TRAIN,
    PARTITION_VALIDATION,
    PARTITION_OUT_OF_SAMPLE,
)

#: Ratio arithmetic tolerance, for binary floating point only.
RATIO_SUM_TOLERANCE = 1e-9


class SplitValidationError(PrimeValidationError):
    """A partitioning request was rejected. Nothing partial is returned."""


@dataclass(frozen=True, slots=True)
class SplitRatios:
    """Three strictly positive fractions summing to one."""

    train: float
    validation: float
    out_of_sample: float

    def __post_init__(self) -> None:
        for name in PARTITION_NAMES:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SplitValidationError(
                    "RATIO_TYPE",
                    f"{name} ratio must be a real number, got {type(value).__name__}",
                )
            numeric = float(value)
            if not math.isfinite(numeric) or numeric <= 0.0 or numeric >= 1.0:
                raise SplitValidationError(
                    "RATIO_RANGE",
                    f"{name} ratio must be a finite fraction strictly between 0 and 1, "
                    f"got {value!r}",
                )
            object.__setattr__(self, name, numeric)
        total = self.train + self.validation + self.out_of_sample
        if abs(total - 1.0) > RATIO_SUM_TOLERANCE:
            raise SplitValidationError(
                "RATIO_SUM",
                f"ratios must sum to 1.0, got {total!r}",
            )

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.train, self.validation, self.out_of_sample)


#: A conventional starting point. It is a default argument, not an approved
#: methodology: the caller owns the choice and should state it explicitly.
DEFAULT_RATIOS = SplitRatios(0.6, 0.2, 0.2)


@dataclass(frozen=True, slots=True)
class DatasetSplit:
    """Frozen chronological partitions plus the provenance of the cut itself."""

    ratios: SplitRatios
    as_of: datetime
    train: tuple[ValidatedCandidate, ...]
    validation: tuple[ValidatedCandidate, ...]
    out_of_sample: tuple[ValidatedCandidate, ...]

    @property
    def partitions(self) -> Mapping[str, tuple[ValidatedCandidate, ...]]:
        return {
            PARTITION_TRAIN: self.train,
            PARTITION_VALIDATION: self.validation,
            PARTITION_OUT_OF_SAMPLE: self.out_of_sample,
        }

    @property
    def sample_count(self) -> int:
        return len(self.train) + len(self.validation) + len(self.out_of_sample)

    @property
    def all_records(self) -> tuple[ValidatedCandidate, ...]:
        return self.train + self.validation + self.out_of_sample

    def partition_of(self, candidate_id: str) -> str | None:
        """Which partition holds this candidate, or ``None`` if it is absent."""
        for name, records in self.partitions.items():
            if any(record.candidate_id == candidate_id for record in records):
                return name
        return None

    def boundaries(self) -> Mapping[str, tuple[str, str]]:
        """First and last instant of each partition, as ISO-8601 strings."""
        return {
            name: (
                records[0].candidate_timestamp_utc.isoformat(),
                records[-1].candidate_timestamp_utc.isoformat(),
            )
            for name, records in self.partitions.items()
        }


def _require_as_of(as_of: Any) -> datetime:
    """Return the caller's explicit UTC cutoff, or fail closed.

    There is no default. A cutoff taken from the wall clock would make the same
    input produce a different frozen split on a different day, so omission is a
    rejection (``AS_OF_REQUIRED``), not a convenience.
    """
    if as_of is None:
        raise SplitValidationError(
            "AS_OF_REQUIRED",
            "an explicit timezone-aware UTC as_of cutoff is required; a frozen "
            "research split never takes its cutoff from the wall clock",
        )
    if not isinstance(as_of, datetime):
        raise SplitValidationError(
            "AS_OF_TYPE",
            f"as_of must be a timezone-aware UTC datetime, got {type(as_of).__name__}",
        )
    return parse_utc_timestamp(as_of, field_name="as_of")


def assert_no_future_leakage(
    records: Sequence[ValidatedCandidate], as_of: datetime
) -> None:
    """Reject any record whose instant is after the declared, explicit cutoff."""
    cutoff = _require_as_of(as_of)
    for record in records:
        if record.candidate_timestamp_utc > cutoff:
            raise SplitValidationError(
                "FUTURE_LEAKAGE",
                f"candidate instant {record.candidate_timestamp_utc.isoformat()} is "
                f"after the as_of cutoff {cutoff.isoformat()}",
                candidate_id=record.candidate_id,
            )


def make_chronological_splits(
    items: Iterable[ValidatedCandidate | Mapping[str, Any]],
    *,
    ratios: SplitRatios = DEFAULT_RATIOS,
    as_of: datetime | None = None,
) -> DatasetSplit:
    """Partition records into frozen chronological train/validation/out-of-sample sets.

    ``as_of`` is required: the caller's explicit, timezone-aware UTC knowledge
    cutoff. Omitting it, or passing ``None``, is an ``AS_OF_REQUIRED`` rejection.
    The ``None`` default exists only so that omission fails with that stable
    code instead of a bare ``TypeError``; it is never replaced by the clock.
    """
    if not isinstance(ratios, SplitRatios):
        raise SplitValidationError(
            "RATIO_TYPE",
            f"ratios must be a SplitRatios, got {type(ratios).__name__}",
        )

    cutoff = _require_as_of(as_of)

    records = coerce_records(items)

    issues = find_integrity_issues(records)
    if issues:
        first = issues[0]
        raise SplitValidationError(
            first.code,
            f"{first.message} ({len(issues)} integrity issue(s) total); a "
            "contaminated set cannot be partitioned",
            candidate_id=first.candidate_id,
        )

    assert_no_future_leakage(records, cutoff)

    ordered = sort_chronologically(records)
    total = len(ordered)

    n_train = int(total * ratios.train)
    n_validation = int(total * ratios.validation)
    n_out_of_sample = total - n_train - n_validation
    if min(n_train, n_validation, n_out_of_sample) < 1:
        raise SplitValidationError(
            "EMPTY_PARTITION",
            f"{total} record(s) at ratios {ratios.as_tuple()} produce partition sizes "
            f"{(n_train, n_validation, n_out_of_sample)}; every partition must hold at "
            "least one record",
        )

    train = ordered[:n_train]
    validation = ordered[n_train : n_train + n_validation]
    out_of_sample = ordered[n_train + n_validation :]

    _assert_strict_boundary(train, validation, PARTITION_TRAIN, PARTITION_VALIDATION)
    _assert_strict_boundary(
        validation, out_of_sample, PARTITION_VALIDATION, PARTITION_OUT_OF_SAMPLE
    )

    return DatasetSplit(
        ratios=ratios,
        as_of=cutoff,
        train=train,
        validation=validation,
        out_of_sample=out_of_sample,
    )


def _assert_strict_boundary(
    earlier: Sequence[ValidatedCandidate],
    later: Sequence[ValidatedCandidate],
    earlier_name: str,
    later_name: str,
) -> None:
    """Require every instant in ``earlier`` to precede every instant in ``later``.

    Because the input is chronologically ordered, only an exact timestamp tie can
    straddle the cut. Silently nudging the boundary to absorb the tie would hide
    the fact that two records share an instant, so it is rejected instead.
    """
    last = earlier[-1].candidate_timestamp_utc
    first = later[0].candidate_timestamp_utc
    if last >= first:
        raise SplitValidationError(
            "PARTITION_BOUNDARY_OVERLAP",
            f"{earlier_name} ends at {last.isoformat()} and {later_name} begins at "
            f"{first.isoformat()}; partitions must not share or cross an instant",
            candidate_id=later[0].candidate_id,
        )


__all__ = [
    "DEFAULT_RATIOS",
    "PARTITION_NAMES",
    "PARTITION_OUT_OF_SAMPLE",
    "PARTITION_TRAIN",
    "PARTITION_VALIDATION",
    "RATIO_SUM_TOLERANCE",
    "DatasetSplit",
    "SplitRatios",
    "SplitValidationError",
    "assert_no_future_leakage",
    "make_chronological_splits",
]
