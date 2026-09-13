"""Adversarial tests for the PRIME one-per-session selection engine and metrics.

Three things are being pinned down here.

First, that the engine holds **no** strategy opinion: the same candidates under
two different caller-supplied keys must select two different rows, an unresolved
tie must be an error rather than a quiet pick, and a candidate that is not
already eligible must be refused outright.

Second, that no caller-supplied key can see hindsight: ``selection_key`` and
``session_key`` receive a detached pre-decision ``SelectionView`` and cannot
reach exit price, outcome, R, actual trade state, or the finalized candidate.

Third, that the metrics never flatter the data: an empty sample, a sample below
the caller's own minimum, and a sample with no losing record must each be
reported as explicitly undefined rather than as a confident number.

No dataset is bundled here. Every record is a synthetic fixture built in-test.
"""

from __future__ import annotations

import dataclasses
import gc
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.prime_validation import engine, metrics  # noqa: E402
from research.prime_validation.engine import (  # noqa: E402
    COMPARISON_LABELS,
    DISPOSITION_SELECTED,
    DISPOSITION_SKIPPED,
    EngineValidationError,
    select_one_per_session,
)
from research.prime_validation.metrics import (  # noqa: E402
    MetricsValidationError,
    combined_policy_metrics,
    compute_metrics,
    metrics_by_model,
)
from research.prime_validation.schema import (  # noqa: E402
    ACTUAL_TRADE_STATES,
    MODEL_KEY_LEVEL_OPEN_10AM,
    MODEL_ORB,
    MODEL_STRICT_OTE,
    OUTCOMES,
    SELECTION_VIEW_FIELDS,
    RecordValidationError,
    SelectionView,
    ValidatedCandidate,
    selection_view_of,
    session_date_key,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
BASE_TS = datetime(2026, 1, 5, 14, 35, tzinfo=timezone.utc)


def record(candidate_id: str = "c1", *, ts: datetime | None = None, **overrides):
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
    return ValidatedCandidate(**fields)


def outcome_record(candidate_id: str, day: int, exit_price: float, outcome: str, **kw):
    """A long record whose R equals ``exit_price - 100`` because risk is 1 point."""
    stamp = BASE_TS + timedelta(days=day)
    return record(
        candidate_id,
        ts=stamp,
        exit_price=exit_price,
        outcome=outcome,
        **kw,
    )


def _code(excinfo) -> str:
    return excinfo.value.code


def by_model_key(view: SelectionView) -> tuple:
    """A caller-owned key: alphabetical by model name. Arbitrary, and explicit."""
    return (view.model, view.candidate_id)


def earliest_key(view: SelectionView) -> tuple:
    """A caller-owned key: earliest instant wins."""
    return (view.candidate_timestamp_utc, view.candidate_id)


# ---------------------------------------------------------------------------
# One selection per session
# ---------------------------------------------------------------------------


def _three_candidates_one_session() -> list[ValidatedCandidate]:
    return [
        record("orb", ts=BASE_TS, model=MODEL_ORB),
        record("ote", ts=BASE_TS + timedelta(minutes=10), model=MODEL_STRICT_OTE),
        record(
            "klo", ts=BASE_TS + timedelta(minutes=20), model=MODEL_KEY_LEVEL_OPEN_10AM
        ),
    ]


def test_at_most_one_candidate_is_selected_per_session():
    evidence = select_one_per_session(
        _three_candidates_one_session(), selection_key=earliest_key
    )
    assert evidence.session_count == 1
    assert len(evidence.selected) == 1
    assert evidence.selected[0].candidate_id == "orb"
    assert [r.candidate_id for r in evidence.skipped] == ["ote", "klo"]


def test_each_session_gets_its_own_single_selection():
    records = []
    for day in range(3):
        stamp = BASE_TS + timedelta(days=day)
        records.append(record(f"orb-{day}", ts=stamp, model=MODEL_ORB))
        records.append(
            record(
                f"ote-{day}", ts=stamp + timedelta(minutes=5), model=MODEL_STRICT_OTE
            )
        )

    evidence = select_one_per_session(records, selection_key=earliest_key)
    assert evidence.session_count == 3
    assert [r.candidate_id for r in evidence.selected] == ["orb-0", "orb-1", "orb-2"]
    assert len(evidence.skipped) == 3

    sessions = [selection.session for selection in evidence.selections]
    assert sessions == sorted(sessions), "sessions must be emitted chronologically"


def test_a_single_candidate_session_selects_it_and_skips_nothing():
    evidence = select_one_per_session([record("solo")], selection_key=earliest_key)
    assert evidence.session_count == 1
    assert evidence.selections[0].skipped == ()
    assert evidence.selections[0].considered_count == 1


def test_no_records_yields_empty_evidence_not_an_invented_selection():
    evidence = select_one_per_session([], selection_key=earliest_key)
    assert evidence.session_count == 0
    assert evidence.selected == ()
    assert evidence.comparisons == ()


def test_caller_may_widen_the_session_scope():
    """Grouping is the caller's too: per-symbol sessions give per-symbol picks."""
    records = [
        record("nq", ts=BASE_TS, symbol="NQ"),
        record("mnq", ts=BASE_TS + timedelta(minutes=5), symbol="MNQ"),
    ]

    per_day = select_one_per_session(records, selection_key=earliest_key)
    assert per_day.session_count == 1

    per_day_symbol = select_one_per_session(
        records,
        selection_key=earliest_key,
        session_key=lambda view: (view.session_date, view.symbol),
    )
    assert per_day_symbol.session_count == 2
    assert sorted(r.candidate_id for r in per_day_symbol.selected) == ["mnq", "nq"]


# ---------------------------------------------------------------------------
# The engine invents no priority
# ---------------------------------------------------------------------------


def test_the_selection_depends_entirely_on_the_caller_supplied_key():
    records = _three_candidates_one_session()

    earliest = select_one_per_session(records, selection_key=earliest_key)
    alphabetical = select_one_per_session(records, selection_key=by_model_key)
    latest = select_one_per_session(
        records,
        selection_key=lambda view: (
            -view.candidate_timestamp_utc.timestamp(),
            view.candidate_id,
        ),
    )

    assert earliest.selected[0].candidate_id == "orb"
    assert alphabetical.selected[0].model == MODEL_KEY_LEVEL_OPEN_10AM
    assert latest.selected[0].candidate_id == "klo"


def test_there_is_no_built_in_model_priority_table():
    """No module-level mapping may rank one execution model above another."""
    for name, value in vars(engine).items():
        if name == "COMPARISON_LABELS" or name.startswith("__"):
            continue
        if isinstance(value, dict):
            assert not (
                set(value) & {MODEL_ORB, MODEL_STRICT_OTE, MODEL_KEY_LEVEL_OPEN_10AM}
            ), f"engine.{name} looks like a model priority table"


def test_a_missing_selection_key_is_refused_rather_than_defaulted():
    with pytest.raises(EngineValidationError) as excinfo:
        select_one_per_session(_three_candidates_one_session(), selection_key=None)
    assert _code(excinfo) == "SELECTION_KEY_REQUIRED"


def test_selection_key_must_return_a_tuple():
    with pytest.raises(EngineValidationError) as excinfo:
        select_one_per_session(
            _three_candidates_one_session(), selection_key=lambda view: view.candidate_id
        )
    assert _code(excinfo) == "SELECTION_KEY_INVALID"


def test_session_key_must_be_callable():
    with pytest.raises(EngineValidationError) as excinfo:
        select_one_per_session(
            _three_candidates_one_session(),
            selection_key=earliest_key,
            session_key="session_date",
        )
    assert _code(excinfo) == "SESSION_KEY_INVALID"


def test_mutually_incomparable_keys_are_rejected():
    def mixed_types(view: SelectionView) -> tuple:
        return (0,) if view.candidate_id == "orb" else ("a",)

    with pytest.raises(EngineValidationError) as excinfo:
        select_one_per_session(
            _three_candidates_one_session(), selection_key=mixed_types
        )
    assert _code(excinfo) == "SELECTION_KEY_INCOMPARABLE"


# ---------------------------------------------------------------------------
# Keys see the decision, never the outcome
# ---------------------------------------------------------------------------

#: Names that would let a key read hindsight or reach the finalized candidate.
_HINDSIGHT_NAMES = (
    "outcome",
    "exit_price",
    "r_multiple",
    "actual_trade_state",
    "source_id",
    "source_sha256",
    "label_method",
    "to_mapping",
    "model_display_name",
    "candidate",
    "record",
    "_candidate",
    "_record",
    "__dict__",
)

_REQUIRED_BLOCKED = ("outcome", "exit_price", "r_multiple", "actual_trade_state")


def _capture_views(records, *, role: str) -> list:
    """Run the engine and return every argument tuple one callback received."""
    seen: list = []

    def spy(*args, **kwargs):
        seen.append((args, kwargs))
        view = args[0]
        if role == "session":
            return session_date_key(view)
        return earliest_key(view)

    if role == "session":
        select_one_per_session(records, selection_key=earliest_key, session_key=spy)
    else:
        select_one_per_session(records, selection_key=spy)
    return seen


def test_selection_view_exposes_exactly_the_pre_decision_fields():
    assert SELECTION_VIEW_FIELDS == (
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
    assert (
        tuple(field.name for field in dataclasses.fields(SelectionView))
        == SELECTION_VIEW_FIELDS
    )
    for name in _REQUIRED_BLOCKED:
        assert name not in SELECTION_VIEW_FIELDS


@pytest.mark.parametrize("role", ["selection", "session"])
def test_each_callback_receives_exactly_one_selection_view_and_nothing_else(role):
    records = _three_candidates_one_session()
    seen = _capture_views(records, role=role)

    assert len(seen) == len(records)
    for args, kwargs in seen:
        assert kwargs == {}
        assert len(args) == 1
        assert type(args[0]) is SelectionView
        assert not isinstance(args[0], ValidatedCandidate)
    assert sorted(args[0].candidate_id for args, _ in seen) == ["klo", "orb", "ote"]


@pytest.mark.parametrize("forbidden", _REQUIRED_BLOCKED)
def test_a_selection_key_cannot_read_hindsight(forbidden):
    with pytest.raises(AttributeError):
        select_one_per_session(
            _three_candidates_one_session(),
            selection_key=lambda view: (getattr(view, forbidden),),
        )


@pytest.mark.parametrize("forbidden", _REQUIRED_BLOCKED)
def test_a_session_key_cannot_read_hindsight(forbidden):
    with pytest.raises(AttributeError):
        select_one_per_session(
            _three_candidates_one_session(),
            selection_key=earliest_key,
            session_key=lambda view: getattr(view, forbidden),
        )


@pytest.mark.parametrize("role", ["selection", "session"])
def test_the_view_holds_no_path_back_to_the_finalized_candidate(role):
    seen = _capture_views(_three_candidates_one_session(), role=role)

    for args, _ in seen:
        view = args[0]
        for name in _HINDSIGHT_NAMES:
            assert not hasattr(view, name), f"view exposes {name!r}"
        assert not set(dir(view)) & set(_HINDSIGHT_NAMES)
        with pytest.raises(TypeError):
            vars(view)

        # Every field value is a plain pre-decision scalar, never a record.
        for field in dataclasses.fields(view):
            value = getattr(view, field.name)
            assert type(value) in {str, bool, datetime, date, type(None)}, field.name

        # Nothing the view directly references is a finalized candidate.
        for referent in gc.get_referents(view):
            assert not isinstance(referent, ValidatedCandidate)

    for value in vars(SelectionView).values():
        assert not isinstance(value, ValidatedCandidate)


def test_selection_views_are_immutable():
    view = selection_view_of(record())
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.model = MODEL_STRICT_OTE  # type: ignore[misc]


def test_the_view_is_blind_to_outcome_so_the_selection_is_too():
    """Same setups, opposite results: the key must select the same rows both times."""

    def setups(winner_id: str) -> list[ValidatedCandidate]:
        built = []
        for offset, (cid, model) in enumerate(
            [
                ("orb", MODEL_ORB),
                ("ote", MODEL_STRICT_OTE),
                ("klo", MODEL_KEY_LEVEL_OPEN_10AM),
            ]
        ):
            won = cid == winner_id
            built.append(
                record(
                    cid,
                    ts=BASE_TS + timedelta(minutes=10 * offset),
                    model=model,
                    exit_price=103.0 if won else 99.0,
                    outcome="W" if won else "L",
                    actual_trade_state="taken" if won else "missed",
                )
            )
        return built

    orb_wins = setups("orb")
    klo_wins = setups("klo")

    assert [r.outcome for r in orb_wins] == ["W", "L", "L"]
    assert [r.outcome for r in klo_wins] == ["L", "L", "W"]
    for left, right in zip(orb_wins, klo_wins):
        assert selection_view_of(left) == selection_view_of(right)

    for key in (earliest_key, by_model_key):
        first = select_one_per_session(orb_wins, selection_key=key)
        second = select_one_per_session(klo_wins, selection_key=key)
        assert [c.candidate_id for c in first.comparisons] == [
            c.candidate_id for c in second.comparisons
        ]
        assert [c.selection_key for c in first.comparisons] == [
            c.selection_key for c in second.comparisons
        ]
        assert [c.disposition for c in first.comparisons] == [
            c.disposition for c in second.comparisons
        ]


def test_final_evidence_is_joined_back_to_the_finalized_candidate_after_selection():
    records = _three_candidates_one_session()
    evidence = select_one_per_session(records, selection_key=earliest_key)
    assert type(evidence.selected[0]) is ValidatedCandidate
    assert evidence.selected[0] is records[0]
    assert all(type(r) is ValidatedCandidate for r in evidence.skipped)
    assert evidence.comparisons[0].outcome == records[0].outcome
    assert evidence.comparisons[0].r_multiple == records[0].r_multiple


def test_confluence_and_ote_companion_metadata_reach_the_view():
    ote = record(
        "ote",
        model=MODEL_STRICT_OTE,
        fvg_confluence=True,
        ote_standard_deviation_context="+2 STDV",
    )
    view = selection_view_of(ote)
    assert view.fvg_confluence is True
    assert view.ote_standard_deviation_context == "+2 STDV"
    assert view.already_eligible is True
    assert view.session_date == ote.session_date
    assert view.candidate_timestamp_utc == ote.candidate_timestamp_utc


def test_default_session_grouping_reads_the_view_session_date():
    assert select_one_per_session.__kwdefaults__["session_key"] is session_date_key
    view = selection_view_of(record("solo"))
    assert session_date_key(view) == BASE_TS.date()


def test_a_selection_view_is_built_only_from_a_validated_candidate():
    with pytest.raises(RecordValidationError) as excinfo:
        selection_view_of({"candidate_id": "c1", "outcome": "W"})
    assert _code(excinfo) == "RECORD_TYPE"


# ---------------------------------------------------------------------------
# Ties
# ---------------------------------------------------------------------------


def test_an_unresolved_tie_is_an_error_not_a_silent_pick():
    with pytest.raises(EngineValidationError) as excinfo:
        select_one_per_session(
            _three_candidates_one_session(), selection_key=lambda view: ("same",)
        )
    assert _code(excinfo) == "AMBIGUOUS_TIE"
    message = str(excinfo.value)
    assert "klo" in message and "orb" in message and "ote" in message


def test_a_tie_on_the_first_key_component_still_raises():
    """Only the *winning* key matters, and only if it is unique."""
    records = [
        record("a", ts=BASE_TS, model=MODEL_ORB),
        record("b", ts=BASE_TS + timedelta(minutes=1), model=MODEL_ORB, symbol="MNQ"),
        record("c", ts=BASE_TS + timedelta(minutes=2), model=MODEL_STRICT_OTE),
    ]
    with pytest.raises(EngineValidationError) as excinfo:
        select_one_per_session(records, selection_key=lambda view: (view.model,))
    assert _code(excinfo) == "AMBIGUOUS_TIE"


def test_extending_the_caller_key_resolves_the_tie():
    records = [
        record("a", ts=BASE_TS, model=MODEL_ORB),
        record("b", ts=BASE_TS + timedelta(minutes=1), model=MODEL_ORB, symbol="MNQ"),
        record("c", ts=BASE_TS + timedelta(minutes=2), model=MODEL_STRICT_OTE),
    ]
    evidence = select_one_per_session(
        records, selection_key=lambda view: (view.model, view.candidate_timestamp_utc)
    )
    assert evidence.selected[0].candidate_id == "a"


def test_a_tie_in_one_session_does_not_leak_a_partial_result():
    records = [
        record("d0-a", ts=BASE_TS),
        record("d0-b", ts=BASE_TS + timedelta(minutes=1), symbol="MNQ"),
        record("d1-a", ts=BASE_TS + timedelta(days=1)),
    ]
    with pytest.raises(EngineValidationError):
        select_one_per_session(records, selection_key=lambda view: (view.session_date,))


def test_selection_is_deterministic_across_runs_and_input_orders():
    records = _three_candidates_one_session()
    first = select_one_per_session(records, selection_key=by_model_key)
    second = select_one_per_session(list(reversed(records)), selection_key=by_model_key)
    assert first == second


# ---------------------------------------------------------------------------
# Eligibility is upstream
# ---------------------------------------------------------------------------


def test_a_non_eligible_candidate_is_refused_because_the_engine_detects_nothing():
    records = [
        record("ok", ts=BASE_TS),
        record("not-yet", ts=BASE_TS + timedelta(days=1), already_eligible=False),
    ]
    with pytest.raises(EngineValidationError) as excinfo:
        select_one_per_session(records, selection_key=earliest_key)
    assert _code(excinfo) == "NOT_ELIGIBLE"
    assert excinfo.value.candidate_id == "not-yet"


def test_engine_refuses_a_contaminated_set():
    duplicated = [record("same", ts=BASE_TS), record("same", ts=BASE_TS + timedelta(days=1))]
    with pytest.raises(EngineValidationError) as excinfo:
        select_one_per_session(duplicated, selection_key=earliest_key)
    assert _code(excinfo) == "DUPLICATE_CANDIDATE_ID"

    mixed = [
        record("c1", ts=BASE_TS),
        record("c2", ts=BASE_TS + timedelta(days=1), source_sha256=HASH_B),
    ]
    with pytest.raises(EngineValidationError) as excinfo:
        select_one_per_session(mixed, selection_key=earliest_key)
    assert _code(excinfo) == "MIXED_PROVENANCE"


# ---------------------------------------------------------------------------
# Evidence, not verdicts
# ---------------------------------------------------------------------------


def test_comparison_labels_cover_every_disposition_and_actual_state():
    expected = {
        (disposition, state)
        for disposition in (DISPOSITION_SELECTED, DISPOSITION_SKIPPED)
        for state in ACTUAL_TRADE_STATES
    }
    assert set(COMPARISON_LABELS) == expected
    assert len(set(COMPARISON_LABELS.values())) == len(expected)


def test_comparison_labels_are_read_only():
    with pytest.raises(TypeError):
        COMPARISON_LABELS[("selected", "taken")] = "graded_a"  # type: ignore[index]


def test_taken_missed_and_rule_deviation_appear_as_neutral_evidence():
    records = [
        record("taken", ts=BASE_TS, actual_trade_state="taken"),
        record(
            "missed",
            ts=BASE_TS + timedelta(minutes=5),
            model=MODEL_STRICT_OTE,
            actual_trade_state="missed",
        ),
        record(
            "deviated",
            ts=BASE_TS + timedelta(minutes=10),
            model=MODEL_KEY_LEVEL_OPEN_10AM,
            actual_trade_state="rule-deviation",
        ),
    ]
    evidence = select_one_per_session(records, selection_key=earliest_key)
    labels = {c.candidate_id: c.label for c in evidence.comparisons}
    assert labels == {
        "taken": "selected_and_taken",
        "missed": "skipped_and_missed",
        "deviated": "skipped_with_rule_deviation",
    }
    assert evidence.comparisons_by_label() == {
        "selected_and_taken": 1,
        "skipped_and_missed": 1,
        "skipped_with_rule_deviation": 1,
    }


def test_a_skipped_candidate_that_was_actually_traded_is_recorded_plainly():
    records = [
        record("picked", ts=BASE_TS, actual_trade_state="missed"),
        record(
            "traded",
            ts=BASE_TS + timedelta(minutes=5),
            model=MODEL_STRICT_OTE,
            actual_trade_state="taken",
        ),
    ]
    evidence = select_one_per_session(records, selection_key=earliest_key)
    labels = {c.candidate_id: c.label for c in evidence.comparisons}
    assert labels["picked"] == "selected_but_missed"
    assert labels["traded"] == "skipped_but_taken"


def test_a_backtest_only_record_is_labeled_not_applicable_rather_than_missed():
    evidence = select_one_per_session(
        [record("hist", actual_trade_state="not-applicable")],
        selection_key=earliest_key,
    )
    assert evidence.comparisons[0].label == "selected_no_actual_trade"


def test_comparisons_carry_direction_aware_r_and_the_winning_key():
    short_loss = record(
        "s",
        direction="short",
        entry_price=100.0,
        exit_price=105.0,
        structural_risk_points=5.0,
        outcome="L",
    )
    evidence = select_one_per_session([short_loss], selection_key=earliest_key)
    comparison = evidence.comparisons[0]
    assert comparison.disposition == DISPOSITION_SELECTED
    assert comparison.r_multiple == pytest.approx(-1.0)
    assert comparison.outcome == "L"
    assert comparison.selection_key == evidence.selections[0].selected_key


def test_evidence_objects_are_immutable():
    evidence = select_one_per_session(
        _three_candidates_one_session(), selection_key=earliest_key
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.selections = ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.selections[0].selected = None
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.comparisons[0].label = "graded_a"


def test_comparison_mapping_is_read_only():
    evidence = select_one_per_session([record()], selection_key=earliest_key)
    view = evidence.comparisons[0].to_mapping()
    with pytest.raises(TypeError):
        view["label"] = "graded_a"  # type: ignore[index]


# ---------------------------------------------------------------------------
# Metrics: the honest sample
# ---------------------------------------------------------------------------


def _eight_record_sample() -> list[ValidatedCandidate]:
    """R series: +2, -1, +3, -2, 0, +1, +4, +2 in chronological order."""
    spec = [
        (0, 102.0, "W"),
        (1, 99.0, "L"),
        (2, 103.0, "W"),
        (3, 98.0, "L"),
        (4, 100.0, "BE"),
        (5, 101.0, "W"),
        (6, 104.0, "W"),
        (7, 102.0, "W"),
    ]
    return [
        outcome_record(f"c{day}", day, exit_price, outcome)
        for day, exit_price, outcome in spec
    ]


def test_counts_and_rates_on_a_complete_sample():
    report = compute_metrics(_eight_record_sample())

    assert report.data_state == metrics.DATA_STATE_COMPLETE
    assert report.sample_count == 8
    assert (report.wins, report.losses, report.breakevens) == (5, 2, 1)
    assert report.wins + report.losses + report.breakevens == report.sample_count

    assert report.win_rate == pytest.approx(5 / 8)
    assert report.expectancy_r == pytest.approx(9 / 8)
    assert report.gross_profit_r == pytest.approx(12.0)
    assert report.gross_loss_r == pytest.approx(3.0)
    assert report.total_r == pytest.approx(9.0)
    assert report.profit_factor == pytest.approx(4.0)
    assert report.profit_factor_state == metrics.PF_DEFINED
    assert report.hit_rate_2r_or_better == pytest.approx(0.5)
    assert report.max_drawdown_r == pytest.approx(2.0)
    assert report.longest_win_streak == 3
    assert report.longest_loss_streak == 1


def test_metrics_are_order_independent_because_they_sort_chronologically():
    sample = _eight_record_sample()
    assert compute_metrics(sample) == compute_metrics(list(reversed(sample)))


def test_metrics_report_is_immutable():
    report = compute_metrics(_eight_record_sample())
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.win_rate = 1.0


def test_short_side_records_contribute_direction_aware_r():
    shorts = [
        outcome_record("s0", 0, 90.0, "W", direction="short"),
        outcome_record("s1", 1, 105.0, "L", direction="short"),
    ]
    report = compute_metrics(shorts)
    assert report.gross_profit_r == pytest.approx(10.0)
    assert report.gross_loss_r == pytest.approx(5.0)
    assert report.total_r == pytest.approx(5.0)


def test_max_drawdown_is_zero_when_the_curve_never_dips():
    rising = [
        outcome_record("r0", 0, 101.0, "W"),
        outcome_record("r1", 1, 102.0, "W"),
    ]
    assert compute_metrics(rising).max_drawdown_r == pytest.approx(0.0)


def test_drawdown_is_reported_as_a_positive_magnitude():
    falling = [
        outcome_record("f0", 0, 103.0, "W"),
        outcome_record("f1", 1, 95.0, "L"),
        outcome_record("f2", 2, 96.0, "L"),
    ]
    report = compute_metrics(falling)
    assert report.total_r == pytest.approx(-6.0)
    assert report.max_drawdown_r == pytest.approx(9.0)


def test_a_breakeven_ends_a_streak_rather_than_extending_it():
    sample = [
        outcome_record("l0", 0, 99.0, "L"),
        outcome_record("be", 1, 100.0, "BE"),
        outcome_record("l1", 2, 99.0, "L"),
    ]
    report = compute_metrics(sample)
    assert report.longest_loss_streak == 1

    consecutive = [
        outcome_record("l0", 0, 99.0, "L"),
        outcome_record("l1", 1, 99.0, "L"),
        outcome_record("l2", 2, 99.0, "L"),
    ]
    assert compute_metrics(consecutive).longest_loss_streak == 3


def test_hit_rate_uses_the_stated_threshold_inclusively():
    sample = [
        outcome_record("exact", 0, 102.0, "W"),  # exactly +2R
        outcome_record("under", 1, 101.9, "W"),
        outcome_record("over", 2, 105.0, "W"),
    ]
    report = compute_metrics(sample)
    assert metrics.TARGET_R_THRESHOLD == 2.0
    assert report.hit_rate_2r_or_better == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# Metrics: honest edge cases
# ---------------------------------------------------------------------------


def test_an_empty_sample_reports_none_everywhere_not_zero():
    report = compute_metrics([])
    assert report.data_state == metrics.DATA_STATE_EMPTY
    assert report.sample_count == 0
    assert report.win_rate is None
    assert report.expectancy_r is None
    assert report.profit_factor is None
    assert report.profit_factor_state == metrics.PF_UNDEFINED_NO_SAMPLE
    assert report.max_drawdown_r is None
    assert report.hit_rate_2r_or_better is None
    assert report.has_rate_metrics is False
    assert any("not as zero" in note for note in report.notes)


def test_zero_loss_profit_factor_is_undefined_not_infinite():
    flawless = [
        outcome_record("w0", 0, 102.0, "W"),
        outcome_record("w1", 1, 103.0, "W"),
        outcome_record("be", 2, 100.0, "BE"),
    ]
    report = compute_metrics(flawless)

    assert report.losses == 0
    assert report.gross_loss_r == pytest.approx(0.0)
    assert report.profit_factor is None
    assert report.profit_factor_state == metrics.PF_UNDEFINED_NO_LOSSES
    assert any("zero denominator" in note for note in report.notes)
    # A 100% win rate on three records is still reported, but the sample is not
    # allowed to imply an infinite or unbeatable profit factor.
    assert report.win_rate == pytest.approx(2 / 3)


def test_zero_profit_sample_has_a_defined_profit_factor_of_zero():
    all_losers = [
        outcome_record("l0", 0, 99.0, "L"),
        outcome_record("l1", 1, 98.0, "L"),
    ]
    report = compute_metrics(all_losers)
    assert report.profit_factor == pytest.approx(0.0)
    assert report.profit_factor_state == metrics.PF_DEFINED
    assert report.win_rate == pytest.approx(0.0)
    assert report.longest_loss_streak == 2


def test_a_sample_below_the_caller_minimum_withholds_rate_metrics():
    report = compute_metrics(_eight_record_sample(), minimum_sample=30)

    assert report.data_state == metrics.DATA_STATE_BELOW_MINIMUM
    assert report.minimum_sample == 30
    assert report.win_rate is None
    assert report.expectancy_r is None
    assert report.profit_factor is None
    assert report.profit_factor_state == metrics.PF_UNDEFINED_BELOW_MINIMUM
    assert report.hit_rate_2r_or_better is None
    # Raw observations are still reported; only the rates are withheld.
    assert report.sample_count == 8
    assert report.wins == 5
    assert report.longest_win_streak == 3
    assert report.max_drawdown_r == pytest.approx(2.0)
    assert any("below the caller's declared minimum" in note for note in report.notes)


def test_meeting_the_caller_minimum_releases_the_rate_metrics():
    report = compute_metrics(_eight_record_sample(), minimum_sample=8)
    assert report.data_state == metrics.DATA_STATE_COMPLETE
    assert report.win_rate == pytest.approx(5 / 8)


def test_no_declared_minimum_is_flagged_in_the_notes():
    report = compute_metrics(_eight_record_sample())
    assert report.minimum_sample == 0
    assert any("no minimum sample" in note for note in report.notes)


def test_every_report_carries_the_no_profitability_claim_note():
    for report in (
        compute_metrics([]),
        compute_metrics(_eight_record_sample()),
        compute_metrics(_eight_record_sample(), minimum_sample=100),
    ):
        assert metrics.NO_PROFITABILITY_CLAIM_NOTE in report.notes


@pytest.mark.parametrize("bad_minimum", [-1, -30])
def test_negative_minimum_sample_rejected(bad_minimum):
    with pytest.raises(MetricsValidationError) as excinfo:
        compute_metrics(_eight_record_sample(), minimum_sample=bad_minimum)
    assert _code(excinfo) == "MINIMUM_SAMPLE_RANGE"


@pytest.mark.parametrize("bad_minimum", [True, 30.0, "30", None])
def test_non_integer_minimum_sample_rejected(bad_minimum):
    with pytest.raises(MetricsValidationError) as excinfo:
        compute_metrics(_eight_record_sample(), minimum_sample=bad_minimum)
    assert _code(excinfo) == "MINIMUM_SAMPLE_TYPE"


def test_report_mapping_is_read_only_and_states_its_data_state():
    view = compute_metrics(_eight_record_sample()).to_mapping()
    assert view["data_state"] == metrics.DATA_STATE_COMPLETE
    with pytest.raises(TypeError):
        view["win_rate"] = 1.0  # type: ignore[index]


# ---------------------------------------------------------------------------
# Metrics: aggregation requires complete provenance
# ---------------------------------------------------------------------------


def test_aggregation_refuses_duplicate_candidate_identity():
    sample = _eight_record_sample()
    sample.append(outcome_record("c0", 8, 102.0, "W"))
    with pytest.raises(MetricsValidationError) as excinfo:
        compute_metrics(sample)
    assert _code(excinfo) == "DUPLICATE_CANDIDATE_ID"


def test_aggregation_refuses_mixed_provenance_for_one_source_identity():
    sample = _eight_record_sample()
    sample.append(outcome_record("c8", 8, 102.0, "W", source_sha256=HASH_B))
    with pytest.raises(MetricsValidationError) as excinfo:
        compute_metrics(sample)
    assert _code(excinfo) == "MIXED_PROVENANCE"


def test_aggregation_refuses_a_double_counted_observation():
    sample = _eight_record_sample()
    sample.append(outcome_record("dup-instant", 0, 102.0, "W"))
    with pytest.raises(MetricsValidationError) as excinfo:
        compute_metrics(sample)
    assert _code(excinfo) == "DUPLICATE_OBSERVATION"


def test_per_model_aggregation_covers_only_the_models_present():
    sample = [
        outcome_record("orb-0", 0, 102.0, "W", model=MODEL_ORB),
        outcome_record("orb-1", 1, 99.0, "L", model=MODEL_ORB),
        outcome_record("ote-0", 2, 103.0, "W", model=MODEL_STRICT_OTE),
    ]
    reports = metrics_by_model(sample)

    assert set(reports) == {MODEL_ORB, MODEL_STRICT_OTE}
    assert MODEL_KEY_LEVEL_OPEN_10AM not in reports
    assert reports[MODEL_ORB].scope == f"model:{MODEL_ORB}"
    assert reports[MODEL_ORB].sample_count == 2
    assert reports[MODEL_ORB].win_rate == pytest.approx(0.5)
    assert reports[MODEL_STRICT_OTE].sample_count == 1
    assert reports[MODEL_STRICT_OTE].profit_factor_state == (
        metrics.PF_UNDEFINED_NO_LOSSES
    )


def test_per_model_report_mapping_is_read_only():
    reports = metrics_by_model([outcome_record("orb-0", 0, 102.0, "W")])
    with pytest.raises(TypeError):
        reports[MODEL_ORB] = None  # type: ignore[index]


def test_per_model_aggregation_refuses_a_contaminated_set():
    sample = _eight_record_sample()
    sample.append(outcome_record("c0", 8, 102.0, "W"))
    with pytest.raises(MetricsValidationError) as excinfo:
        metrics_by_model(sample)
    assert _code(excinfo) == "DUPLICATE_CANDIDATE_ID"


def test_combined_policy_metrics_sum_the_per_model_counts():
    sample = [
        outcome_record("orb-0", 0, 102.0, "W", model=MODEL_ORB),
        outcome_record("orb-1", 1, 99.0, "L", model=MODEL_ORB),
        outcome_record("ote-0", 2, 103.0, "W", model=MODEL_STRICT_OTE),
        outcome_record("klo-0", 3, 98.0, "L", model=MODEL_KEY_LEVEL_OPEN_10AM),
    ]
    combined = combined_policy_metrics(sample)
    per_model = metrics_by_model(sample)

    assert combined.scope == metrics.SCOPE_COMBINED_POLICY
    assert combined.sample_count == sum(r.sample_count for r in per_model.values())
    assert combined.wins == sum(r.wins for r in per_model.values())
    assert combined.losses == sum(r.losses for r in per_model.values())
    assert combined.total_r == pytest.approx(
        sum(r.total_r for r in per_model.values())
    )


def test_metrics_accept_the_engine_evidence_selection_directly():
    """The two halves compose: what the caller's key selected is what is measured."""
    records = []
    for day in range(4):
        stamp = BASE_TS + timedelta(days=day)
        records.append(record(f"orb-{day}", ts=stamp, model=MODEL_ORB))
        records.append(
            record(
                f"ote-{day}",
                ts=stamp + timedelta(minutes=5),
                model=MODEL_STRICT_OTE,
                exit_price=99.0,
                outcome="L",
            )
        )

    evidence = select_one_per_session(records, selection_key=earliest_key)
    selected_report = compute_metrics(evidence.selected, scope="selected")
    skipped_report = compute_metrics(evidence.skipped, scope="skipped")

    assert selected_report.sample_count == 4
    assert selected_report.wins == 4
    assert skipped_report.sample_count == 4
    assert skipped_report.losses == 4
    # Evidence only: the engine measured both sides, and neither number is a
    # recommendation to trade either one.
    assert metrics.NO_PROFITABILITY_CLAIM_NOTE in selected_report.notes


def test_outcome_universe_is_exactly_win_loss_breakeven():
    assert OUTCOMES == frozenset({"W", "L", "BE"})
    report = compute_metrics(_eight_record_sample())
    assert report.wins + report.losses + report.breakevens == report.sample_count
