"""Immutable validated-candidate schema for the PRIME emotionless validation foundation.

This module is standard-library only and read-only. It performs **no** file I/O,
no network access, no environment mutation, and no flag toggling. It consumes
records that are *already* labeled and finalized by a human or by a separately
approved deterministic upstream process, and it either accepts them as immutable
validated records or fails closed.

What this module deliberately does NOT do:

* it does not detect, scan for, or infer a setup;
* it does not invent, tune, rank, or optimize a rule;
* it does not assign model priority, grade, or score;
* it does not size, execute, or contact a broker or webhook;
* it does not promote anything into current PRIME authority.

Locked universe (see ``nova_knowledge_core/CURRENT/PRIME/EXECUTION_MODELS.md``):
exactly three execution models, symbols NQ and MNQ, directions long and short.
FVG is confluence metadata only. Standard deviation is a Strict-OTE companion
read only. There is no fourth model and no legacy PROS logic here.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Callable, Hashable, Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Locked universe
# ---------------------------------------------------------------------------

MODEL_STRICT_OTE = "strict_ote"
MODEL_KEY_LEVEL_OPEN_10AM = "10am_key_level_open"
MODEL_ORB = "orb"

#: The exact, closed set of PRIME execution models. A fourth entry here would be
#: an unapproved system change, not a code change.
PRIME_MODELS: frozenset[str] = frozenset(
    {MODEL_STRICT_OTE, MODEL_KEY_LEVEL_OPEN_10AM, MODEL_ORB}
)

MODEL_DISPLAY_NAMES: Mapping[str, str] = MappingProxyType(
    {
        MODEL_STRICT_OTE: "Strict OTE",
        MODEL_KEY_LEVEL_OPEN_10AM: "10AM Key Level Open",
        MODEL_ORB: "ORB",
    }
)

SYMBOL_NQ = "NQ"
SYMBOL_MNQ = "MNQ"
PRIME_SYMBOLS: frozenset[str] = frozenset({SYMBOL_NQ, SYMBOL_MNQ})

DIRECTION_LONG = "long"
DIRECTION_SHORT = "short"
DIRECTIONS: frozenset[str] = frozenset({DIRECTION_LONG, DIRECTION_SHORT})

LABEL_METHOD_DETERMINISTIC = "deterministic"
LABEL_METHOD_HUMAN_CONFIRMED = "human-confirmed"
LABEL_METHODS: frozenset[str] = frozenset(
    {LABEL_METHOD_DETERMINISTIC, LABEL_METHOD_HUMAN_CONFIRMED}
)

OUTCOME_WIN = "W"
OUTCOME_LOSS = "L"
OUTCOME_BREAKEVEN = "BE"
OUTCOMES: frozenset[str] = frozenset({OUTCOME_WIN, OUTCOME_LOSS, OUTCOME_BREAKEVEN})

ACTUAL_TAKEN = "taken"
ACTUAL_MISSED = "missed"
ACTUAL_RULE_DEVIATION = "rule-deviation"
ACTUAL_NOT_APPLICABLE = "not-applicable"
ACTUAL_TRADE_STATES: frozenset[str] = frozenset(
    {ACTUAL_TAKEN, ACTUAL_MISSED, ACTUAL_RULE_DEVIATION, ACTUAL_NOT_APPLICABLE}
)

#: A breakeven record is a scratch at the entry price. The tolerance exists only
#: to absorb binary floating-point representation, not to define a policy band.
BREAKEVEN_R_TOLERANCE = 1e-9

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_ZERO_OFFSET = timedelta(0)

REQUIRED_FIELDS: tuple[str, ...] = (
    "candidate_id",
    "model",
    "symbol",
    "direction",
    "candidate_timestamp_utc",
    "session_date",
    "source_id",
    "source_sha256",
    "label_method",
    "entry_price",
    "exit_price",
    "structural_risk_points",
    "already_eligible",
    "outcome",
    "actual_trade_state",
)

OPTIONAL_FIELDS: tuple[str, ...] = (
    "fvg_confluence",
    "ote_standard_deviation_context",
)

ALL_FIELDS: tuple[str, ...] = REQUIRED_FIELDS + OPTIONAL_FIELDS


# ---------------------------------------------------------------------------
# Errors — every rejection carries a stable machine-readable code
# ---------------------------------------------------------------------------


class PrimeValidationError(ValueError):
    """Base class for every fail-closed rejection in this package."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        candidate_id: str | None = None,
        field_name: str | None = None,
    ) -> None:
        parts = [f"[{code}]"]
        if candidate_id:
            parts.append(f"candidate={candidate_id!r}")
        if field_name:
            parts.append(f"field={field_name!r}")
        parts.append(message)
        super().__init__(" ".join(parts))
        self.code = code
        self.candidate_id = candidate_id
        self.field_name = field_name


class RecordValidationError(PrimeValidationError):
    """A single record, or a set of records, failed schema/provenance validation."""


@dataclass(frozen=True, slots=True)
class IntegrityIssue:
    """One set-level integrity problem found across a collection of records."""

    code: str
    message: str
    candidate_id: str | None = None


# ---------------------------------------------------------------------------
# Small validation helpers
# ---------------------------------------------------------------------------


def _require_clean_text(
    value: Any, code: str, field_name: str, candidate_id: str | None
) -> str:
    if not isinstance(value, str):
        raise RecordValidationError(
            code,
            f"must be a string, got {type(value).__name__}",
            candidate_id=candidate_id,
            field_name=field_name,
        )
    if not value or value != value.strip():
        raise RecordValidationError(
            code,
            "must be non-empty and free of surrounding whitespace",
            candidate_id=candidate_id,
            field_name=field_name,
        )
    return value


def _require_member(
    value: Any,
    allowed: frozenset[str],
    code: str,
    field_name: str,
    candidate_id: str | None,
) -> str:
    if value not in allowed:
        raise RecordValidationError(
            code,
            f"must be one of {sorted(allowed)}, got {value!r}",
            candidate_id=candidate_id,
            field_name=field_name,
        )
    return value


def _require_finite_number(
    value: Any, code: str, field_name: str, candidate_id: str | None
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecordValidationError(
            code,
            f"must be a real number, got {type(value).__name__}",
            candidate_id=candidate_id,
            field_name=field_name,
        )
    numeric = float(value)
    if not math.isfinite(numeric):
        raise RecordValidationError(
            code,
            f"must be finite, got {numeric!r}",
            candidate_id=candidate_id,
            field_name=field_name,
        )
    return numeric


def _require_positive_price(
    value: Any, code: str, field_name: str, candidate_id: str | None
) -> float:
    """An NQ/MNQ price is a strictly positive finite real number.

    A zero or negative futures price is not a market observation; it is a
    corrupt row (a missing value written as ``0``, a sign error, a spread
    leg). Accepting it would still yield an arithmetically valid R, which is
    exactly why it must be refused here rather than noticed later.
    """
    numeric = _require_finite_number(value, code, field_name, candidate_id)
    if numeric <= 0.0:
        raise RecordValidationError(
            code,
            f"{field_name} must be strictly positive for NQ/MNQ, got {numeric!r}",
            candidate_id=candidate_id,
            field_name=field_name,
        )
    return numeric


def _require_bool(
    value: Any, code: str, field_name: str, candidate_id: str | None
) -> bool:
    if not isinstance(value, bool):
        raise RecordValidationError(
            code,
            f"must be a bool, got {type(value).__name__}",
            candidate_id=candidate_id,
            field_name=field_name,
        )
    return value


def parse_utc_timestamp(
    value: Any,
    *,
    candidate_id: str | None = None,
    field_name: str = "candidate_timestamp_utc",
) -> datetime:
    """Return a timezone-aware UTC datetime, or fail closed.

    Accepts a ``datetime`` or an ISO-8601 string. A naive datetime, a non-UTC
    offset, or an unparseable string is rejected: an ambiguous instant cannot be
    ordered against another instant, and unordered records cannot be split
    without leakage. ``field_name`` names the instant being checked in the
    error, so a rejected split cutoff is not reported as a candidate field.
    """
    if isinstance(value, str):
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            value = datetime.fromisoformat(text)
        except ValueError as exc:
            raise RecordValidationError(
                "TIMESTAMP_UNPARSEABLE",
                f"{field_name} is not ISO-8601: {value!r}",
                candidate_id=candidate_id,
                field_name=field_name,
            ) from exc
    if not isinstance(value, datetime):
        raise RecordValidationError(
            "TIMESTAMP_TYPE",
            f"{field_name} must be a datetime, got {type(value).__name__}",
            candidate_id=candidate_id,
            field_name=field_name,
        )
    offset = value.utcoffset()
    if offset is None:
        raise RecordValidationError(
            "TIMESTAMP_NAIVE",
            f"{field_name} must be timezone-aware",
            candidate_id=candidate_id,
            field_name=field_name,
        )
    if offset != _ZERO_OFFSET:
        raise RecordValidationError(
            "TIMESTAMP_NOT_UTC",
            f"{field_name} must be UTC (zero offset), got offset {offset}",
            candidate_id=candidate_id,
            field_name=field_name,
        )
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# The validated record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidatedCandidate:
    """One immutable, pre-labeled, finalized historical candidate.

    Construction is validation: an instance that exists has already passed every
    check below. Nothing in this class decides whether the candidate *should*
    have been a setup — ``already_eligible`` records an upstream human or
    separately approved deterministic judgement, and this package only reads it.
    """

    candidate_id: str
    model: str
    symbol: str
    direction: str
    candidate_timestamp_utc: datetime
    session_date: date
    source_id: str
    source_sha256: str
    label_method: str
    entry_price: float
    exit_price: float
    structural_risk_points: float
    already_eligible: bool
    outcome: str
    actual_trade_state: str
    # Confluence / companion metadata. Never an entry model, never a fourth model.
    fvg_confluence: bool = False
    ote_standard_deviation_context: str | None = None

    def __post_init__(self) -> None:
        set_ = object.__setattr__

        candidate_id = _require_clean_text(
            self.candidate_id, "CANDIDATE_ID", "candidate_id", None
        )

        _require_member(self.model, PRIME_MODELS, "MODEL", "model", candidate_id)
        _require_member(self.symbol, PRIME_SYMBOLS, "SYMBOL", "symbol", candidate_id)
        _require_member(
            self.direction, DIRECTIONS, "DIRECTION", "direction", candidate_id
        )

        timestamp = parse_utc_timestamp(
            self.candidate_timestamp_utc, candidate_id=candidate_id
        )
        set_(self, "candidate_timestamp_utc", timestamp)

        # `datetime` subclasses `date`; a datetime here would silently compare
        # unequal to `timestamp.date()` for reasons unrelated to the session.
        if type(self.session_date) is not date:
            raise RecordValidationError(
                "SESSION_DATE_TYPE",
                f"session_date must be a datetime.date, got {type(self.session_date).__name__}",
                candidate_id=candidate_id,
                field_name="session_date",
            )
        if self.session_date != timestamp.date():
            raise RecordValidationError(
                "SESSION_DATE_MISMATCH",
                f"session_date {self.session_date.isoformat()} does not match the UTC "
                f"candidate timestamp date {timestamp.date().isoformat()}",
                candidate_id=candidate_id,
                field_name="session_date",
            )

        _require_clean_text(self.source_id, "SOURCE_ID", "source_id", candidate_id)
        if not isinstance(self.source_sha256, str) or not _SHA256_RE.match(
            self.source_sha256
        ):
            raise RecordValidationError(
                "SOURCE_SHA256",
                "source_sha256 must be exactly 64 lowercase hexadecimal characters",
                candidate_id=candidate_id,
                field_name="source_sha256",
            )
        _require_member(
            self.label_method,
            LABEL_METHODS,
            "LABEL_METHOD",
            "label_method",
            candidate_id,
        )

        set_(
            self,
            "entry_price",
            _require_positive_price(
                self.entry_price, "ENTRY_PRICE", "entry_price", candidate_id
            ),
        )
        set_(
            self,
            "exit_price",
            _require_positive_price(
                self.exit_price, "EXIT_PRICE", "exit_price", candidate_id
            ),
        )
        risk = _require_finite_number(
            self.structural_risk_points,
            "STRUCTURAL_RISK",
            "structural_risk_points",
            candidate_id,
        )
        if risk <= 0.0:
            raise RecordValidationError(
                "STRUCTURAL_RISK",
                f"structural_risk_points must be strictly positive, got {risk!r}",
                candidate_id=candidate_id,
                field_name="structural_risk_points",
            )
        set_(self, "structural_risk_points", risk)

        _require_bool(
            self.already_eligible, "ELIGIBILITY_FLAG", "already_eligible", candidate_id
        )
        _require_member(self.outcome, OUTCOMES, "OUTCOME", "outcome", candidate_id)
        _require_member(
            self.actual_trade_state,
            ACTUAL_TRADE_STATES,
            "ACTUAL_TRADE_STATE",
            "actual_trade_state",
            candidate_id,
        )
        _require_bool(
            self.fvg_confluence, "FVG_CONFLUENCE", "fvg_confluence", candidate_id
        )

        if self.ote_standard_deviation_context is not None:
            _require_clean_text(
                self.ote_standard_deviation_context,
                "STDV_CONTEXT",
                "ote_standard_deviation_context",
                candidate_id,
            )
            if self.model != MODEL_STRICT_OTE:
                raise RecordValidationError(
                    "STDV_SCOPE",
                    "standard-deviation context is a Strict OTE companion read only; "
                    f"it cannot be attached to model {self.model!r}",
                    candidate_id=candidate_id,
                    field_name="ote_standard_deviation_context",
                )

        self._assert_outcome_matches_r()

    def _assert_outcome_matches_r(self) -> None:
        """Reject a finalized label that contradicts its own prices.

        This is a provenance-integrity check, not a grade: a record labeled W
        whose exit is adverse means the row is wrong, and a wrong row silently
        poisons every metric downstream.
        """
        realised = self.r_multiple
        if self.outcome == OUTCOME_WIN:
            valid = realised > BREAKEVEN_R_TOLERANCE
        elif self.outcome == OUTCOME_LOSS:
            valid = realised < -BREAKEVEN_R_TOLERANCE
        else:
            valid = abs(realised) <= BREAKEVEN_R_TOLERANCE
        if not valid:
            raise RecordValidationError(
                "OUTCOME_R_MISMATCH",
                f"outcome {self.outcome!r} contradicts the direction-aware realised "
                f"R of {realised!r} implied by entry/exit/risk",
                candidate_id=self.candidate_id,
                field_name="outcome",
            )

    # -- derived, never stored -------------------------------------------------

    @property
    def r_multiple(self) -> float:
        """Direction-aware realised R: signed exit movement over structural risk."""
        movement = self.exit_price - self.entry_price
        if self.direction == DIRECTION_SHORT:
            movement = -movement
        return movement / self.structural_risk_points

    @property
    def model_display_name(self) -> str:
        return MODEL_DISPLAY_NAMES[self.model]

    def to_mapping(self) -> Mapping[str, Any]:
        """A read-only view of this record plus its derived R, for evidence output."""
        return MappingProxyType(
            {
                "candidate_id": self.candidate_id,
                "model": self.model,
                "symbol": self.symbol,
                "direction": self.direction,
                "candidate_timestamp_utc": self.candidate_timestamp_utc.isoformat(),
                "session_date": self.session_date.isoformat(),
                "source_id": self.source_id,
                "source_sha256": self.source_sha256,
                "label_method": self.label_method,
                "entry_price": self.entry_price,
                "exit_price": self.exit_price,
                "structural_risk_points": self.structural_risk_points,
                "already_eligible": self.already_eligible,
                "outcome": self.outcome,
                "actual_trade_state": self.actual_trade_state,
                "fvg_confluence": self.fvg_confluence,
                "ote_standard_deviation_context": self.ote_standard_deviation_context,
                "r_multiple": self.r_multiple,
            }
        )

    # -- construction from raw data -------------------------------------------

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ValidatedCandidate":
        """Build a record from a raw mapping, failing closed on anything unexpected.

        Normalization here is limited to case and whitespace on enumerated text
        and to parsing ISO-8601 date/timestamp strings. Nothing is defaulted,
        guessed, or repaired: a missing field is a rejection, and an unknown
        field is a rejection too, because a silently dropped column is
        indistinguishable from missing provenance.
        """
        if not isinstance(data, Mapping):
            raise RecordValidationError(
                "RECORD_TYPE",
                f"record must be a mapping, got {type(data).__name__}",
            )

        unknown = sorted(set(data) - set(ALL_FIELDS))
        if unknown:
            raise RecordValidationError(
                "UNKNOWN_FIELD",
                f"unrecognized field(s) {unknown}; the schema is closed",
                candidate_id=_safe_id(data),
            )
        missing = [name for name in REQUIRED_FIELDS if name not in data]
        if missing:
            raise RecordValidationError(
                "MISSING_FIELD",
                f"incomplete record, missing field(s) {missing}",
                candidate_id=_safe_id(data),
            )

        candidate_id = data["candidate_id"]
        if isinstance(candidate_id, str):
            candidate_id = candidate_id.strip()

        session_date = data["session_date"]
        if isinstance(session_date, str):
            try:
                session_date = date.fromisoformat(session_date.strip())
            except ValueError as exc:
                raise RecordValidationError(
                    "SESSION_DATE_TYPE",
                    f"session_date is not an ISO-8601 date: {data['session_date']!r}",
                    candidate_id=_safe_id(data),
                    field_name="session_date",
                ) from exc

        return cls(
            candidate_id=candidate_id,
            model=_normalize_enum(data["model"], lower=True),
            symbol=_normalize_enum(data["symbol"], upper=True),
            direction=_normalize_enum(data["direction"], lower=True),
            candidate_timestamp_utc=parse_utc_timestamp(
                data["candidate_timestamp_utc"], candidate_id=_safe_id(data)
            ),
            session_date=session_date,
            source_id=(
                data["source_id"].strip()
                if isinstance(data["source_id"], str)
                else data["source_id"]
            ),
            source_sha256=_normalize_enum(data["source_sha256"], lower=True),
            label_method=_normalize_enum(data["label_method"], lower=True),
            entry_price=data["entry_price"],
            exit_price=data["exit_price"],
            structural_risk_points=data["structural_risk_points"],
            already_eligible=data["already_eligible"],
            outcome=_normalize_enum(data["outcome"], upper=True),
            actual_trade_state=_normalize_enum(data["actual_trade_state"], lower=True),
            fvg_confluence=data.get("fvg_confluence", False),
            ote_standard_deviation_context=_normalize_optional_text(
                data.get("ote_standard_deviation_context")
            ),
        )


def _safe_id(data: Mapping[str, Any]) -> str | None:
    value = data.get("candidate_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _normalize_enum(value: Any, *, lower: bool = False, upper: bool = False) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if lower:
        return text.lower()
    if upper:
        return text.upper()
    return text


def _normalize_optional_text(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    return value


# ---------------------------------------------------------------------------
# Collection-level helpers
# ---------------------------------------------------------------------------


def coerce_records(
    items: Iterable[ValidatedCandidate | Mapping[str, Any]],
) -> tuple[ValidatedCandidate, ...]:
    """Coerce an iterable of records or raw mappings into validated records."""
    out: list[ValidatedCandidate] = []
    for item in items:
        if isinstance(item, ValidatedCandidate):
            out.append(item)
        else:
            out.append(ValidatedCandidate.from_mapping(item))
    return tuple(out)


def chronological_key(record: ValidatedCandidate) -> tuple[Any, ...]:
    """A total, deterministic ordering key. No randomness, no shuffling, ever."""
    return (
        record.candidate_timestamp_utc,
        record.session_date,
        record.symbol,
        record.model,
        record.candidate_id,
    )


def sort_chronologically(
    records: Iterable[ValidatedCandidate],
) -> tuple[ValidatedCandidate, ...]:
    return tuple(sorted(records, key=chronological_key))


def find_integrity_issues(
    records: Sequence[ValidatedCandidate],
) -> tuple[IntegrityIssue, ...]:
    """Report every set-level integrity problem, without raising.

    Checks, in a fixed order:

    * ``DUPLICATE_CANDIDATE_ID`` — candidate identity must be unique;
    * ``MIXED_PROVENANCE`` — one ``source_id`` must map to exactly one
      ``source_sha256``, otherwise two different datasets are wearing one name;
    * ``DUPLICATE_OBSERVATION`` — the same (symbol, model, instant) cannot appear
      twice under two identities; that is a contaminated, double-counted event.
    """
    issues: list[IntegrityIssue] = []

    seen_ids: set[str] = set()
    for record in records:
        if record.candidate_id in seen_ids:
            issues.append(
                IntegrityIssue(
                    "DUPLICATE_CANDIDATE_ID",
                    f"candidate_id {record.candidate_id!r} appears more than once",
                    record.candidate_id,
                )
            )
        seen_ids.add(record.candidate_id)

    provenance: dict[str, str] = {}
    for record in records:
        known = provenance.get(record.source_id)
        if known is None:
            provenance[record.source_id] = record.source_sha256
        elif known != record.source_sha256:
            issues.append(
                IntegrityIssue(
                    "MIXED_PROVENANCE",
                    f"source_id {record.source_id!r} carries conflicting content "
                    f"hashes {known!r} and {record.source_sha256!r}",
                    record.candidate_id,
                )
            )

    observations: dict[tuple[str, str, datetime], str] = {}
    for record in records:
        key = (record.symbol, record.model, record.candidate_timestamp_utc)
        prior = observations.get(key)
        if prior is None:
            observations[key] = record.candidate_id
        else:
            issues.append(
                IntegrityIssue(
                    "DUPLICATE_OBSERVATION",
                    f"{record.symbol}/{record.model} at "
                    f"{record.candidate_timestamp_utc.isoformat()} is claimed by both "
                    f"{prior!r} and {record.candidate_id!r}",
                    record.candidate_id,
                )
            )

    return tuple(issues)


def assert_integrity(records: Sequence[ValidatedCandidate]) -> None:
    """Raise ``RecordValidationError`` on the first set-level integrity problem."""
    issues = find_integrity_issues(records)
    if issues:
        first = issues[0]
        raise RecordValidationError(
            first.code,
            f"{first.message} ({len(issues)} integrity issue(s) total)",
            candidate_id=first.candidate_id,
        )


def validate_records(
    items: Iterable[ValidatedCandidate | Mapping[str, Any]],
) -> tuple[ValidatedCandidate, ...]:
    """Validate, integrity-check, and chronologically order a set of records."""
    records = coerce_records(items)
    assert_integrity(records)
    return sort_chronologically(records)


# ---------------------------------------------------------------------------
# Pre-decision selection view
# ---------------------------------------------------------------------------

#: The only fields a caller-supplied selection or session key may read. Each one
#: is knowable at the candidate instant. Exit price, outcome, realised R, actual
#: trade state, and source/label provenance are deliberately absent: a key that
#: could read them could pick winners, and a backtest built on such a key would
#: be measuring hindsight rather than a decision.
SELECTION_VIEW_FIELDS: tuple[str, ...] = (
    "candidate_id",
    "model",
    "symbol",
    "direction",
    "candidate_timestamp_utc",
    "session_date",
    "already_eligible",
    "fvg_confluence",
    "ote_standard_deviation_context",
)


@dataclass(frozen=True, slots=True)
class SelectionView:
    """What a candidate looked like at decision time — and nothing after it.

    This is the only object a caller-supplied ``selection_key`` or
    ``session_key`` ever receives. It is a frozen, slotted copy of the
    pre-decision fields, not a wrapper: it holds no reference to the
    :class:`ValidatedCandidate` it was copied from, has no ``__dict__``, and
    exposes no property or method that could reach exit price, outcome, R, or
    actual trade state.

    It closes the ordinary attribute path to hindsight. It is not an in-process
    sandbox: deliberate interpreter introspection, or a key that closes over the
    finalized records itself, is circumvention and a review failure, not a
    supported use.
    """

    candidate_id: str
    model: str
    symbol: str
    direction: str
    candidate_timestamp_utc: datetime
    session_date: date
    already_eligible: bool
    # Confluence / companion metadata, carried through unchanged.
    fvg_confluence: bool
    ote_standard_deviation_context: str | None


def selection_view_of(record: ValidatedCandidate) -> SelectionView:
    """Copy a validated candidate's pre-decision fields into a detached view."""
    if not isinstance(record, ValidatedCandidate):
        raise RecordValidationError(
            "RECORD_TYPE",
            f"a selection view is built from a ValidatedCandidate, got "
            f"{type(record).__name__}",
        )
    return SelectionView(
        candidate_id=record.candidate_id,
        model=record.model,
        symbol=record.symbol,
        direction=record.direction,
        candidate_timestamp_utc=record.candidate_timestamp_utc,
        session_date=record.session_date,
        already_eligible=record.already_eligible,
        fvg_confluence=record.fvg_confluence,
        ote_standard_deviation_context=record.ote_standard_deviation_context,
    )


def session_date_key(view: SelectionView) -> Hashable:
    """Default session grouping: the pre-decision view's recorded session date."""
    return view.session_date


#: Caller-supplied keys receive a :class:`SelectionView` only, never the
#: finalized :class:`ValidatedCandidate`.
SelectionKeyFn = Callable[[SelectionView], tuple[Any, ...]]
SessionKeyFn = Callable[[SelectionView], Hashable]


__all__ = [
    "ACTUAL_MISSED",
    "ACTUAL_NOT_APPLICABLE",
    "ACTUAL_RULE_DEVIATION",
    "ACTUAL_TAKEN",
    "ACTUAL_TRADE_STATES",
    "ALL_FIELDS",
    "BREAKEVEN_R_TOLERANCE",
    "DIRECTIONS",
    "DIRECTION_LONG",
    "DIRECTION_SHORT",
    "IntegrityIssue",
    "LABEL_METHODS",
    "LABEL_METHOD_DETERMINISTIC",
    "LABEL_METHOD_HUMAN_CONFIRMED",
    "MODEL_DISPLAY_NAMES",
    "MODEL_KEY_LEVEL_OPEN_10AM",
    "MODEL_ORB",
    "MODEL_STRICT_OTE",
    "OPTIONAL_FIELDS",
    "OUTCOMES",
    "OUTCOME_BREAKEVEN",
    "OUTCOME_LOSS",
    "OUTCOME_WIN",
    "PRIME_MODELS",
    "PRIME_SYMBOLS",
    "PrimeValidationError",
    "REQUIRED_FIELDS",
    "RecordValidationError",
    "SELECTION_VIEW_FIELDS",
    "SYMBOL_MNQ",
    "SYMBOL_NQ",
    "SelectionKeyFn",
    "SelectionView",
    "SessionKeyFn",
    "ValidatedCandidate",
    "assert_integrity",
    "chronological_key",
    "coerce_records",
    "find_integrity_issues",
    "parse_utc_timestamp",
    "selection_view_of",
    "session_date_key",
    "sort_chronologically",
    "validate_records",
]
