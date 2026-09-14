"""Adversarial tests for the PRIME validation schema and chronological splits.

These tests try to get bad data *in*. Every case below is something that, if it
were silently accepted, would produce a metric nobody could trust: a fourth
execution model, an ES row, a naive timestamp, a mislabeled outcome, a dataset
whose content hash changed under a stable name, a zero or negative futures price,
a validation set that peeked at its own future, or a split whose cutoff was
quietly taken from the wall clock.

No dataset is bundled here. Every record is a synthetic fixture built in-test.
"""

from __future__ import annotations

import ast
import dataclasses
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.prime_validation import schema, splits  # noqa: E402
from research.prime_validation.schema import (  # noqa: E402
    MODEL_KEY_LEVEL_OPEN_10AM,
    MODEL_ORB,
    MODEL_STRICT_OTE,
    PRIME_MODELS,
    PRIME_SYMBOLS,
    RecordValidationError,
    ValidatedCandidate,
)
from research.prime_validation.splits import (  # noqa: E402
    SplitRatios,
    SplitValidationError,
    make_chronological_splits,
)

HASH_A = "a" * 64
HASH_B = "b" * 64

BASE_TS = datetime(2026, 1, 5, 14, 35, tzinfo=timezone.utc)
FAR_FUTURE = datetime(2099, 1, 1, tzinfo=timezone.utc)


def record(candidate_id: str = "c1", *, ts: datetime | None = None, **overrides):
    """Build one valid record, overriding any field for the case under test."""
    timestamp = BASE_TS if ts is None else ts
    fields = {
        "candidate_id": candidate_id,
        "model": MODEL_ORB,
        "symbol": "NQ",
        "direction": "long",
        "candidate_timestamp_utc": timestamp,
        "session_date": timestamp.date(),
        "source_id": "dataset-a",
        "source_sha256": HASH_A,
        "label_method": "deterministic",
        "entry_price": 100.0,
        "exit_price": 102.0,
        "structural_risk_points": 1.0,
        "already_eligible": True,
        "outcome": "W",
        "actual_trade_state": "taken",
    }
    fields.update(overrides)
    if "candidate_timestamp_utc" in overrides and "session_date" not in overrides:
        stamp = overrides["candidate_timestamp_utc"]
        if isinstance(stamp, datetime):
            fields["session_date"] = stamp.date()
    return ValidatedCandidate(**fields)


def mapping(candidate_id: str = "c1", **overrides) -> dict:
    """The same fixture as a raw mapping, for ``from_mapping`` cases."""
    base = {
        "candidate_id": candidate_id,
        "model": MODEL_ORB,
        "symbol": "NQ",
        "direction": "long",
        "candidate_timestamp_utc": "2026-01-05T14:35:00+00:00",
        "session_date": "2026-01-05",
        "source_id": "dataset-a",
        "source_sha256": HASH_A,
        "label_method": "deterministic",
        "entry_price": 100.0,
        "exit_price": 102.0,
        "structural_risk_points": 1.0,
        "already_eligible": True,
        "outcome": "W",
        "actual_trade_state": "taken",
    }
    base.update(overrides)
    return base


def _code(excinfo) -> str:
    return excinfo.value.code


# ---------------------------------------------------------------------------
# The locked universe
# ---------------------------------------------------------------------------


def test_model_set_is_exactly_the_three_prime_models():
    assert PRIME_MODELS == frozenset(
        {MODEL_STRICT_OTE, MODEL_KEY_LEVEL_OPEN_10AM, MODEL_ORB}
    )
    assert len(PRIME_MODELS) == 3
    assert set(schema.MODEL_DISPLAY_NAMES) == PRIME_MODELS
    assert sorted(schema.MODEL_DISPLAY_NAMES.values()) == [
        "10AM Key Level Open",
        "ORB",
        "Strict OTE",
    ]


def test_symbols_and_directions_are_locked():
    assert PRIME_SYMBOLS == frozenset({"NQ", "MNQ"})
    assert schema.DIRECTIONS == frozenset({"long", "short"})
    assert schema.OUTCOMES == frozenset({"W", "L", "BE"})
    assert schema.ACTUAL_TRADE_STATES == frozenset(
        {"taken", "missed", "rule-deviation", "not-applicable"}
    )
    assert schema.LABEL_METHODS == frozenset({"deterministic", "human-confirmed"})


@pytest.mark.parametrize(
    "rejected_model",
    [
        "fvg",
        "standard_deviation",
        "stdv",
        "pros",
        "bounce_rejection",
        "signal_score",
        "harvey",
        "market_reality",
        "ote",
        "ORB",
        "",
        None,
    ],
)
def test_no_fourth_model_and_no_legacy_pros_logic(rejected_model):
    with pytest.raises(RecordValidationError) as excinfo:
        record(model=rejected_model)
    assert _code(excinfo) == "MODEL"


@pytest.mark.parametrize("bad_symbol", ["ES", "MES", "SPY", "nq", "NQ1!", "", None])
def test_invalid_symbols_rejected(bad_symbol):
    with pytest.raises(RecordValidationError) as excinfo:
        record(symbol=bad_symbol)
    assert _code(excinfo) == "SYMBOL"


@pytest.mark.parametrize("bad_direction", ["flat", "buy", "sell", "Long", "", None])
def test_invalid_directions_rejected(bad_direction):
    with pytest.raises(RecordValidationError) as excinfo:
        record(direction=bad_direction)
    assert _code(excinfo) == "DIRECTION"


def test_fvg_is_confluence_metadata_only_and_does_not_change_r():
    plain = record("c1", fvg_confluence=False)
    with_fvg = record("c2", fvg_confluence=True)
    assert with_fvg.fvg_confluence is True
    assert with_fvg.r_multiple == plain.r_multiple


def test_fvg_confluence_must_be_a_bool():
    with pytest.raises(RecordValidationError) as excinfo:
        record(fvg_confluence="yes")
    assert _code(excinfo) == "FVG_CONFLUENCE"


def test_standard_deviation_is_an_ote_companion_read_only():
    ote = record("c1", model=MODEL_STRICT_OTE, ote_standard_deviation_context="+2 STDV")
    assert ote.ote_standard_deviation_context == "+2 STDV"

    for model in (MODEL_ORB, MODEL_KEY_LEVEL_OPEN_10AM):
        with pytest.raises(RecordValidationError) as excinfo:
            record(model=model, ote_standard_deviation_context="+2 STDV")
        assert _code(excinfo) == "STDV_SCOPE"


# ---------------------------------------------------------------------------
# Timestamps and session dates
# ---------------------------------------------------------------------------


def test_naive_timestamp_rejected():
    with pytest.raises(RecordValidationError) as excinfo:
        record(candidate_timestamp_utc=datetime(2026, 1, 5, 14, 35))
    assert _code(excinfo) == "TIMESTAMP_NAIVE"


def test_non_utc_offset_rejected():
    eastern = timezone(timedelta(hours=-5))
    with pytest.raises(RecordValidationError) as excinfo:
        record(candidate_timestamp_utc=datetime(2026, 1, 5, 9, 35, tzinfo=eastern))
    assert _code(excinfo) == "TIMESTAMP_NOT_UTC"


@pytest.mark.parametrize("bad", ["not-a-timestamp", "2026-13-01T00:00:00+00:00", ""])
def test_unparseable_timestamp_string_rejected(bad):
    with pytest.raises(RecordValidationError) as excinfo:
        record(candidate_timestamp_utc=bad, session_date=date(2026, 1, 5))
    assert _code(excinfo) == "TIMESTAMP_UNPARSEABLE"


@pytest.mark.parametrize("bad", [None, 1767623700, 1767623700.0, object()])
def test_non_datetime_timestamp_rejected(bad):
    with pytest.raises(RecordValidationError) as excinfo:
        record(candidate_timestamp_utc=bad, session_date=date(2026, 1, 5))
    assert _code(excinfo) == "TIMESTAMP_TYPE"


def test_zulu_suffix_is_accepted_and_normalized_to_utc():
    built = ValidatedCandidate.from_mapping(
        mapping(candidate_timestamp_utc="2026-01-05T14:35:00Z")
    )
    assert built.candidate_timestamp_utc == BASE_TS
    assert built.candidate_timestamp_utc.tzinfo is timezone.utc


def test_session_date_must_match_the_candidate_timestamp():
    with pytest.raises(RecordValidationError) as excinfo:
        record(
            candidate_timestamp_utc=BASE_TS,
            session_date=date(2026, 1, 6),
        )
    assert _code(excinfo) == "SESSION_DATE_MISMATCH"


def test_session_date_must_be_a_plain_date_not_a_datetime():
    with pytest.raises(RecordValidationError) as excinfo:
        record(session_date=BASE_TS)
    assert _code(excinfo) == "SESSION_DATE_TYPE"


def test_unparseable_session_date_string_rejected():
    with pytest.raises(RecordValidationError) as excinfo:
        ValidatedCandidate.from_mapping(mapping(session_date="05/01/2026"))
    assert _code(excinfo) == "SESSION_DATE_TYPE"


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_hash",
    [
        "A" * 64,  # uppercase is not the canonical form
        "a" * 63,  # too short
        "a" * 65,  # too long
        "g" * 64,  # not hexadecimal
        "",
        None,
        12345,
    ],
)
def test_source_hash_must_be_lowercase_64_char_sha256(bad_hash):
    with pytest.raises(RecordValidationError) as excinfo:
        record(source_sha256=bad_hash)
    assert _code(excinfo) == "SOURCE_SHA256"


@pytest.mark.parametrize("bad_source", ["", "  ", " dataset-a", None, 7])
def test_source_id_must_be_present_and_clean(bad_source):
    with pytest.raises(RecordValidationError) as excinfo:
        record(source_id=bad_source)
    assert _code(excinfo) == "SOURCE_ID"


@pytest.mark.parametrize("bad_method", ["inferred", "guessed", "auto", "", None])
def test_label_method_must_be_deterministic_or_human_confirmed(bad_method):
    with pytest.raises(RecordValidationError) as excinfo:
        record(label_method=bad_method)
    assert _code(excinfo) == "LABEL_METHOD"


@pytest.mark.parametrize("bad_id", ["", "  ", " c1", "c1 ", None, 1])
def test_candidate_id_must_be_present_and_clean(bad_id):
    with pytest.raises(RecordValidationError) as excinfo:
        record(bad_id)
    assert _code(excinfo) == "CANDIDATE_ID"


def test_incomplete_record_is_rejected_field_by_field():
    for missing in schema.REQUIRED_FIELDS:
        payload = mapping()
        payload.pop(missing)
        with pytest.raises(RecordValidationError) as excinfo:
            ValidatedCandidate.from_mapping(payload)
        assert _code(excinfo) == "MISSING_FIELD"
        assert missing in str(excinfo.value)


def test_unknown_field_is_rejected_because_a_dropped_column_looks_like_missing_data():
    with pytest.raises(RecordValidationError) as excinfo:
        ValidatedCandidate.from_mapping(mapping(grade="A"))
    assert _code(excinfo) == "UNKNOWN_FIELD"
    assert "grade" in str(excinfo.value)


def test_non_mapping_record_rejected():
    with pytest.raises(RecordValidationError) as excinfo:
        ValidatedCandidate.from_mapping(["c1", "orb"])
    assert _code(excinfo) == "RECORD_TYPE"


def test_from_mapping_normalizes_case_and_whitespace_only():
    built = ValidatedCandidate.from_mapping(
        mapping(
            candidate_id="  c9  ",
            model="  ORB ",
            symbol=" nq ",
            direction=" LONG ",
            outcome=" w ",
            actual_trade_state=" TAKEN ",
            label_method=" Deterministic ",
            source_sha256=("A" * 64),
        )
    )
    assert built.candidate_id == "c9"
    assert built.model == MODEL_ORB
    assert built.symbol == "NQ"
    assert built.direction == "long"
    assert built.outcome == "W"
    assert built.actual_trade_state == "taken"
    assert built.label_method == "deterministic"
    assert built.source_sha256 == HASH_A


# ---------------------------------------------------------------------------
# Prices, risk, and derived R
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_risk", [0, 0.0, -1.0, -0.0001])
def test_structural_risk_must_be_strictly_positive(bad_risk):
    with pytest.raises(RecordValidationError) as excinfo:
        record(structural_risk_points=bad_risk)
    assert _code(excinfo) == "STRUCTURAL_RISK"


@pytest.mark.parametrize(
    "bad_risk", [float("nan"), float("inf"), float("-inf"), "5", None, True]
)
def test_structural_risk_must_be_a_finite_number(bad_risk):
    with pytest.raises(RecordValidationError) as excinfo:
        record(structural_risk_points=bad_risk)
    assert _code(excinfo) == "STRUCTURAL_RISK"


@pytest.mark.parametrize("field_name", ["entry_price", "exit_price"])
@pytest.mark.parametrize(
    "bad_price", [float("nan"), float("inf"), float("-inf"), "100", None, True]
)
def test_prices_must_be_finite_numbers(field_name, bad_price):
    with pytest.raises(RecordValidationError) as excinfo:
        record(**{field_name: bad_price})
    assert _code(excinfo) == field_name.upper()


@pytest.mark.parametrize("field_name", ["entry_price", "exit_price"])
@pytest.mark.parametrize("bad_price", [0, 0.0, -0.0, -1.0, -0.25, -21500.0])
def test_zero_and_negative_prices_are_rejected_for_nq_and_mnq(field_name, bad_price):
    """A non-positive futures price is a corrupt row, even if R would still compute."""
    for symbol in ("NQ", "MNQ"):
        with pytest.raises(RecordValidationError) as excinfo:
            record(symbol=symbol, **{field_name: bad_price})
        assert _code(excinfo) == field_name.upper()
        assert excinfo.value.field_name == field_name


def test_price_positivity_is_checked_before_the_outcome_label():
    """A zero exit on a W row reports the corrupt price, not a label mismatch."""
    with pytest.raises(RecordValidationError) as excinfo:
        record(exit_price=0.0, outcome="W")
    assert _code(excinfo) == "EXIT_PRICE"


def test_small_positive_prices_are_accepted_and_r_is_unchanged():
    short_win = record(
        "tiny",
        direction="short",
        entry_price=0.5,
        exit_price=0.25,
        structural_risk_points=0.25,
        outcome="W",
    )
    assert short_win.r_multiple == pytest.approx(1.0)


def test_long_r_is_exit_minus_entry_over_risk():
    winner = record("long-w", direction="long", entry_price=100.0, exit_price=110.0,
                    structural_risk_points=5.0, outcome="W")
    assert winner.r_multiple == pytest.approx(2.0)

    loser = record("long-l", direction="long", entry_price=100.0, exit_price=95.0,
                   structural_risk_points=5.0, outcome="L")
    assert loser.r_multiple == pytest.approx(-1.0)


def test_short_r_is_entry_minus_exit_over_risk():
    winner = record("short-w", direction="short", entry_price=100.0, exit_price=90.0,
                    structural_risk_points=5.0, outcome="W")
    assert winner.r_multiple == pytest.approx(2.0)

    loser = record("short-l", direction="short", entry_price=100.0, exit_price=105.0,
                   structural_risk_points=5.0, outcome="L")
    assert loser.r_multiple == pytest.approx(-1.0)


def test_a_short_is_not_silently_scored_as_a_long():
    """The same prices must produce opposite R for the two directions."""
    long_side = record("l", direction="long", entry_price=100.0, exit_price=110.0,
                       structural_risk_points=5.0, outcome="W")
    short_side = record("s", direction="short", entry_price=100.0, exit_price=110.0,
                        structural_risk_points=5.0, outcome="L")
    assert long_side.r_multiple == pytest.approx(-short_side.r_multiple)


def test_breakeven_requires_a_scratch_at_entry():
    scratch = record("be", entry_price=100.0, exit_price=100.0, outcome="BE")
    assert scratch.r_multiple == 0.0


@pytest.mark.parametrize(
    ("outcome", "exit_price"),
    [
        ("W", 95.0),  # labeled a win, priced as a loss
        ("W", 100.0),  # labeled a win, priced as a scratch
        ("L", 110.0),  # labeled a loss, priced as a win
        ("L", 100.0),
        ("BE", 110.0),  # labeled a scratch, priced as a win
        ("BE", 95.0),
    ],
)
def test_outcome_label_contradicting_its_own_prices_is_rejected(outcome, exit_price):
    with pytest.raises(RecordValidationError) as excinfo:
        record(outcome=outcome, exit_price=exit_price, structural_risk_points=5.0)
    assert _code(excinfo) == "OUTCOME_R_MISMATCH"


@pytest.mark.parametrize("bad_outcome", ["win", "WIN", "w", "B/E", "pending", "", None])
def test_unfinalized_or_unknown_outcome_rejected(bad_outcome):
    with pytest.raises(RecordValidationError) as excinfo:
        record(outcome=bad_outcome)
    assert _code(excinfo) == "OUTCOME"


@pytest.mark.parametrize(
    "bad_state", ["open", "pending", "TAKEN", "rule deviation", "", None]
)
def test_unknown_actual_trade_state_rejected(bad_state):
    with pytest.raises(RecordValidationError) as excinfo:
        record(actual_trade_state=bad_state)
    assert _code(excinfo) == "ACTUAL_TRADE_STATE"


def test_all_four_actual_trade_states_are_accepted():
    for index, state in enumerate(sorted(schema.ACTUAL_TRADE_STATES)):
        built = record(f"c{index}", actual_trade_state=state)
        assert built.actual_trade_state == state


@pytest.mark.parametrize("bad_flag", [0, 1, "true", "yes", None])
def test_already_eligible_must_be_a_real_bool(bad_flag):
    with pytest.raises(RecordValidationError) as excinfo:
        record(already_eligible=bad_flag)
    assert _code(excinfo) == "ELIGIBILITY_FLAG"


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("outcome", "L"),
        ("exit_price", 500.0),
        ("structural_risk_points", 0.1),
        ("model", MODEL_STRICT_OTE),
        ("already_eligible", False),
    ],
)
def test_validated_records_are_immutable(field_name, value):
    built = record()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(built, field_name, value)


def test_evidence_mapping_is_read_only():
    view = record().to_mapping()
    assert view["r_multiple"] == pytest.approx(2.0)
    with pytest.raises(TypeError):
        view["outcome"] = "L"  # type: ignore[index]


# ---------------------------------------------------------------------------
# Set-level integrity: duplicates, contamination, mixed provenance
# ---------------------------------------------------------------------------


def test_duplicate_candidate_identity_is_reported_and_raised():
    records = [record("dup", ts=BASE_TS), record("dup", ts=BASE_TS + timedelta(days=1))]
    codes = [issue.code for issue in schema.find_integrity_issues(records)]
    assert "DUPLICATE_CANDIDATE_ID" in codes
    with pytest.raises(RecordValidationError) as excinfo:
        schema.assert_integrity(records)
    assert _code(excinfo) == "DUPLICATE_CANDIDATE_ID"


def test_one_source_id_with_two_content_hashes_is_mixed_provenance():
    records = [
        record("c1", ts=BASE_TS, source_id="dataset-a", source_sha256=HASH_A),
        record(
            "c2",
            ts=BASE_TS + timedelta(days=1),
            source_id="dataset-a",
            source_sha256=HASH_B,
        ),
    ]
    with pytest.raises(RecordValidationError) as excinfo:
        schema.assert_integrity(records)
    assert _code(excinfo) == "MIXED_PROVENANCE"


def test_distinct_source_ids_may_carry_distinct_hashes():
    records = [
        record("c1", ts=BASE_TS, source_id="dataset-a", source_sha256=HASH_A),
        record(
            "c2",
            ts=BASE_TS + timedelta(days=1),
            source_id="dataset-b",
            source_sha256=HASH_B,
        ),
    ]
    assert schema.find_integrity_issues(records) == ()


def test_the_same_event_claimed_by_two_identities_is_contamination():
    records = [
        record("c1", ts=BASE_TS, model=MODEL_ORB, symbol="NQ"),
        record("c2", ts=BASE_TS, model=MODEL_ORB, symbol="NQ"),
    ]
    with pytest.raises(RecordValidationError) as excinfo:
        schema.assert_integrity(records)
    assert _code(excinfo) == "DUPLICATE_OBSERVATION"


def test_two_models_or_two_symbols_may_share_an_instant():
    records = [
        record("c1", ts=BASE_TS, model=MODEL_ORB, symbol="NQ"),
        record("c2", ts=BASE_TS, model=MODEL_STRICT_OTE, symbol="NQ"),
        record("c3", ts=BASE_TS, model=MODEL_ORB, symbol="MNQ"),
    ]
    assert schema.find_integrity_issues(records) == ()


def test_validate_records_returns_a_chronologically_ordered_tuple():
    ordered = schema.validate_records(
        [
            record("c3", ts=BASE_TS + timedelta(days=2)),
            record("c1", ts=BASE_TS),
            record("c2", ts=BASE_TS + timedelta(days=1)),
        ]
    )
    assert isinstance(ordered, tuple)
    assert [r.candidate_id for r in ordered] == ["c1", "c2", "c3"]


# ---------------------------------------------------------------------------
# Splits: ratios
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ratios",
    [
        (0.6, 0.2, 0.3),  # sums above one
        (0.5, 0.2, 0.2),  # sums below one
        (0.8, 0.2, 0.0),  # a zero partition share
        (1.0, 0.0, 0.0),
        (-0.2, 0.6, 0.6),  # negative share
        (1.5, -0.25, -0.25),
    ],
)
def test_invalid_ratio_triples_rejected(ratios):
    with pytest.raises(SplitValidationError) as excinfo:
        SplitRatios(*ratios)
    assert _code(excinfo) in {"RATIO_RANGE", "RATIO_SUM"}


@pytest.mark.parametrize("bad", ["0.6", None, True])
def test_ratio_must_be_a_real_number(bad):
    with pytest.raises(SplitValidationError) as excinfo:
        SplitRatios(bad, 0.2, 0.2)
    assert _code(excinfo) == "RATIO_TYPE"


def test_ratios_argument_must_be_a_split_ratios_instance():
    records = [record(f"c{i}", ts=BASE_TS + timedelta(days=i)) for i in range(10)]
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits(records, ratios=(0.6, 0.2, 0.2), as_of=FAR_FUTURE)
    assert _code(excinfo) == "RATIO_TYPE"


def test_default_ratios_are_a_valid_sixty_twenty_twenty_triple():
    assert splits.DEFAULT_RATIOS.as_tuple() == (0.6, 0.2, 0.2)


# ---------------------------------------------------------------------------
# Splits: chronology, leakage, determinism
# ---------------------------------------------------------------------------


def _ten_records() -> list[ValidatedCandidate]:
    return [record(f"c{i:02d}", ts=BASE_TS + timedelta(days=i)) for i in range(10)]


def test_partitions_are_chronological_frozen_and_non_overlapping():
    split = make_chronological_splits(_ten_records(), as_of=FAR_FUTURE)

    assert len(split.train) == 6
    assert len(split.validation) == 2
    assert len(split.out_of_sample) == 2
    assert split.sample_count == 10

    for partition in (split.train, split.validation, split.out_of_sample):
        assert isinstance(partition, tuple)

    assert [r.candidate_id for r in split.train] == [f"c{i:02d}" for i in range(6)]
    assert [r.candidate_id for r in split.validation] == ["c06", "c07"]
    assert [r.candidate_id for r in split.out_of_sample] == ["c08", "c09"]

    assert (
        split.train[-1].candidate_timestamp_utc
        < split.validation[0].candidate_timestamp_utc
        < split.validation[-1].candidate_timestamp_utc
        < split.out_of_sample[0].candidate_timestamp_utc
    )


def test_split_result_is_immutable():
    split = make_chronological_splits(_ten_records(), as_of=FAR_FUTURE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        split.train = ()


def test_splits_are_deterministic_and_input_order_independent():
    records = _ten_records()
    forward = make_chronological_splits(records, as_of=FAR_FUTURE)
    reversed_input = make_chronological_splits(
        list(reversed(records)), as_of=FAR_FUTURE
    )
    shuffled_input = make_chronological_splits(
        [records[i] for i in (4, 9, 0, 7, 2, 5, 1, 8, 3, 6)], as_of=FAR_FUTURE
    )

    def ids(split):
        return {
            name: [r.candidate_id for r in part]
            for name, part in split.partitions.items()
        }

    assert ids(forward) == ids(reversed_input) == ids(shuffled_input)


def test_repeated_splits_of_the_same_input_are_identical():
    records = _ten_records()
    first = make_chronological_splits(records, as_of=FAR_FUTURE)
    second = make_chronological_splits(records, as_of=FAR_FUTURE)
    assert first == second


def test_future_leakage_is_rejected():
    records = _ten_records()
    cutoff = BASE_TS + timedelta(days=5)
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits(records, as_of=cutoff)
    assert _code(excinfo) == "FUTURE_LEAKAGE"


def test_as_of_cutoff_must_itself_be_utc_aware():
    with pytest.raises(RecordValidationError) as excinfo:
        make_chronological_splits(_ten_records(), as_of=datetime(2099, 1, 1))
    assert _code(excinfo) == "TIMESTAMP_NAIVE"
    assert excinfo.value.field_name == "as_of"


def test_as_of_cutoff_must_be_utc_not_merely_aware():
    eastern = timezone(timedelta(hours=-5))
    with pytest.raises(RecordValidationError) as excinfo:
        make_chronological_splits(
            _ten_records(), as_of=datetime(2099, 1, 1, tzinfo=eastern)
        )
    assert _code(excinfo) == "TIMESTAMP_NOT_UTC"
    assert excinfo.value.field_name == "as_of"


def test_omitting_as_of_fails_closed_instead_of_reading_the_clock():
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits(_ten_records())
    assert _code(excinfo) == "AS_OF_REQUIRED"


def test_explicit_none_as_of_fails_closed():
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits(_ten_records(), as_of=None)
    assert _code(excinfo) == "AS_OF_REQUIRED"


def test_as_of_is_required_before_the_records_are_even_considered():
    """An empty input must not mask a missing cutoff as an empty-partition error."""
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits([])
    assert _code(excinfo) == "AS_OF_REQUIRED"


@pytest.mark.parametrize(
    "bad_as_of",
    ["2099-01-01T00:00:00+00:00", date(2099, 1, 1), 4070908800, 4070908800.0],
)
def test_as_of_must_be_a_datetime_not_a_string_date_or_epoch(bad_as_of):
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits(_ten_records(), as_of=bad_as_of)
    assert _code(excinfo) == "AS_OF_TYPE"


def test_standalone_leakage_check_also_requires_an_explicit_cutoff():
    with pytest.raises(SplitValidationError) as excinfo:
        splits.assert_no_future_leakage(_ten_records(), None)
    assert _code(excinfo) == "AS_OF_REQUIRED"


def test_the_split_records_the_exact_cutoff_it_was_given():
    split = make_chronological_splits(_ten_records(), as_of=FAR_FUTURE)
    assert split.as_of == FAR_FUTURE
    assert split.as_of.tzinfo is timezone.utc


def test_records_exactly_at_the_cutoff_are_allowed():
    records = _ten_records()
    cutoff = records[-1].candidate_timestamp_utc
    split = make_chronological_splits(records, as_of=cutoff)
    assert split.sample_count == 10


def test_a_boundary_straddling_instant_is_rejected_rather_than_absorbed():
    """Two records sharing the cut instant would put one session on both sides."""
    records = _ten_records()
    shared = records[6].candidate_timestamp_utc
    records[5] = record("c05", ts=shared, symbol="MNQ")
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits(records, as_of=FAR_FUTURE)
    assert _code(excinfo) == "PARTITION_BOUNDARY_OVERLAP"


def test_duplicate_identity_blocks_partitioning():
    records = _ten_records()
    records[3] = record("c00", ts=BASE_TS + timedelta(days=3))
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits(records, as_of=FAR_FUTURE)
    assert _code(excinfo) == "DUPLICATE_CANDIDATE_ID"


def test_mixed_provenance_blocks_partitioning():
    records = _ten_records()
    records[4] = record(
        "c04",
        ts=BASE_TS + timedelta(days=4),
        source_id="dataset-a",
        source_sha256=HASH_B,
    )
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits(records, as_of=FAR_FUTURE)
    assert _code(excinfo) == "MIXED_PROVENANCE"


def test_duplicate_observation_blocks_partitioning():
    records = _ten_records()
    records.append(record("c10", ts=records[0].candidate_timestamp_utc))
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits(records, as_of=FAR_FUTURE)
    assert _code(excinfo) == "DUPLICATE_OBSERVATION"


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
def test_too_few_records_for_three_partitions_is_rejected(count):
    records = [record(f"c{i:02d}", ts=BASE_TS + timedelta(days=i)) for i in range(count)]
    with pytest.raises(SplitValidationError) as excinfo:
        make_chronological_splits(records, as_of=FAR_FUTURE)
    assert _code(excinfo) == "EMPTY_PARTITION"


def test_five_records_is_the_smallest_sixty_twenty_twenty_split():
    records = [record(f"c{i:02d}", ts=BASE_TS + timedelta(days=i)) for i in range(5)]
    split = make_chronological_splits(records, as_of=FAR_FUTURE)
    assert (len(split.train), len(split.validation), len(split.out_of_sample)) == (
        3,
        1,
        1,
    )


def test_partition_lookup_and_boundaries_describe_the_cut():
    split = make_chronological_splits(_ten_records(), as_of=FAR_FUTURE)
    assert split.partition_of("c00") == splits.PARTITION_TRAIN
    assert split.partition_of("c06") == splits.PARTITION_VALIDATION
    assert split.partition_of("c09") == splits.PARTITION_OUT_OF_SAMPLE
    assert split.partition_of("nope") is None

    bounds = split.boundaries()
    assert set(bounds) == set(splits.PARTITION_NAMES)
    assert bounds[splits.PARTITION_TRAIN][0] == BASE_TS.isoformat()


def test_assert_no_future_leakage_is_usable_on_its_own():
    records = _ten_records()
    splits.assert_no_future_leakage(records, FAR_FUTURE)
    with pytest.raises(SplitValidationError):
        splits.assert_no_future_leakage(records, BASE_TS)


def test_splits_accept_raw_mappings_and_validate_them():
    payloads = []
    for i in range(5):
        stamp = BASE_TS + timedelta(days=i)
        payloads.append(
            mapping(
                f"m{i}",
                candidate_timestamp_utc=stamp.isoformat(),
                session_date=stamp.date().isoformat(),
            )
        )
    split = make_chronological_splits(payloads, as_of=FAR_FUTURE)
    assert split.sample_count == 5
    assert all(isinstance(r, ValidatedCandidate) for r in split.all_records)


# ---------------------------------------------------------------------------
# The package stays standard-library-only, read-only, and side-effect free
# ---------------------------------------------------------------------------

_ALLOWED_IMPORT_ROOTS = frozenset(
    {"__future__", "dataclasses", "datetime", "math", "re", "types", "typing"}
)
_FORBIDDEN_CALLS = frozenset({"open", "eval", "exec", "compile", "__import__", "input", "print"})


def _package_sources() -> list[Path]:
    package_dir = Path(schema.__file__).resolve().parent
    sources = sorted(package_dir.glob("*.py"))
    assert [path.name for path in sources] == [
        "__init__.py",
        "engine.py",
        "metrics.py",
        "schema.py",
        "splits.py",
    ]
    return sources


def test_package_imports_only_the_standard_library_it_declares():
    for path in _package_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                roots = {(node.module or "").split(".")[0]}
            else:
                continue
            unexpected = roots - _ALLOWED_IMPORT_ROOTS - {"research"}
            assert not unexpected, f"{path.name} imports {sorted(unexpected)}"


def test_package_performs_no_io_no_eval_and_no_printing():
    for path in _package_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert (
                    node.func.id not in _FORBIDDEN_CALLS
                ), f"{path.name} calls {node.func.id}()"


_CLOCK_ATTRIBUTES = frozenset({"now", "utcnow", "today"})


def test_package_never_reads_the_wall_clock():
    """A reproducible split or report cannot depend on when it was run."""
    for path in _package_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert (
                    node.attr not in _CLOCK_ATTRIBUTES
                ), f"{path.name} references .{node.attr}"


def test_split_signature_documents_no_clock_default():
    import inspect

    parameter = inspect.signature(make_chronological_splits).parameters["as_of"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is None


def test_package_declares_its_lack_of_authorization():
    import research.prime_validation as package

    notice = package.AUTHORIZATION_NOTICE.lower()
    assert "no profitability claim can be made" in notice
    assert "no dataset is included" in notice
    assert "nothing here authorizes autonomous or funded trading" in notice
    assert "execution remains disabled" in notice
    assert "does not, and must not be extended to" in (package.__doc__ or "")
