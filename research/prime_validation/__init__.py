"""PRIME emotionless validation foundation — read-only historical validation.

A standard-library-only research package that consumes **pre-labeled, finalized**
historical PRIME candidates and reports what they contain. It is the first rung
of the approved validation ladder described in
``docs/PRIME_EMOTIONLESS_VALIDATION.md``; it is not a trading system, and it
contains no dataset.

Modules
-------
``schema``   immutable validated-candidate records, fail-closed validation
``splits``   deterministic chronological train / validation / out-of-sample sets
``engine``   one-per-session selection under a caller-supplied deterministic key
             that sees only a pre-decision ``SelectionView``, never the outcome
``metrics``  honest descriptive metrics with explicit undefined states

Hard boundaries. This package does not, and must not be extended to:

* detect setups, or decide that something was eligible;
* invent, tune, rank, or optimize a rule or parameter;
* assign strategy/model priority, grade, or score;
* execute, size dollars, or contact a broker or webhook;
* read or toggle ``NOVA_TRADING_SUBSYSTEM_ENABLED``, ``NOVA_AUTO_EXECUTE``, or
  any other flag;
* promote research into current PRIME authority — that is Pedro's decision
  alone, per ``docs/claude-cowork/RESPONSIBILITY_CONTRACT.md``.

Locked universe: exactly three execution models (Strict OTE, 10AM Key Level
Open, ORB), symbols NQ and MNQ, directions long and short. FVG is confluence
metadata only; standard deviation is a Strict-OTE companion read only. There is
no fourth model and no legacy PROS logic.

**No output of this package is a profitability claim, and none of it authorizes
trading.** The trading/execution subsystem remains disabled.
"""

from __future__ import annotations

from research.prime_validation.engine import (
    COMPARISON_LABELS,
    DISPOSITION_SELECTED,
    DISPOSITION_SKIPPED,
    EngineValidationError,
    SelectionComparison,
    SelectionEvidence,
    SessionSelection,
    select_one_per_session,
)
from research.prime_validation.metrics import (
    DATA_STATE_BELOW_MINIMUM,
    DATA_STATE_COMPLETE,
    DATA_STATE_EMPTY,
    NO_PROFITABILITY_CLAIM_NOTE,
    PF_DEFINED,
    PF_UNDEFINED_BELOW_MINIMUM,
    PF_UNDEFINED_NO_LOSSES,
    PF_UNDEFINED_NO_SAMPLE,
    SCOPE_COMBINED_POLICY,
    TARGET_R_THRESHOLD,
    MetricsReport,
    MetricsValidationError,
    combined_policy_metrics,
    compute_metrics,
    metrics_by_model,
)
from research.prime_validation.schema import (
    ACTUAL_MISSED,
    ACTUAL_NOT_APPLICABLE,
    ACTUAL_RULE_DEVIATION,
    ACTUAL_TAKEN,
    ACTUAL_TRADE_STATES,
    BREAKEVEN_R_TOLERANCE,
    DIRECTION_LONG,
    DIRECTION_SHORT,
    DIRECTIONS,
    LABEL_METHOD_DETERMINISTIC,
    LABEL_METHOD_HUMAN_CONFIRMED,
    LABEL_METHODS,
    MODEL_DISPLAY_NAMES,
    MODEL_KEY_LEVEL_OPEN_10AM,
    MODEL_ORB,
    MODEL_STRICT_OTE,
    OUTCOME_BREAKEVEN,
    OUTCOME_LOSS,
    OUTCOME_WIN,
    OUTCOMES,
    PRIME_MODELS,
    PRIME_SYMBOLS,
    PrimeValidationError,
    RecordValidationError,
    SELECTION_VIEW_FIELDS,
    SYMBOL_MNQ,
    SYMBOL_NQ,
    SelectionKeyFn,
    SelectionView,
    SessionKeyFn,
    ValidatedCandidate,
    assert_integrity,
    find_integrity_issues,
    selection_view_of,
    session_date_key,
    sort_chronologically,
    validate_records,
)
from research.prime_validation.splits import (
    DEFAULT_RATIOS,
    PARTITION_NAMES,
    PARTITION_OUT_OF_SAMPLE,
    PARTITION_TRAIN,
    PARTITION_VALIDATION,
    DatasetSplit,
    SplitRatios,
    SplitValidationError,
    assert_no_future_leakage,
    make_chronological_splits,
)

#: Phase 2F PRIME emotionless validation foundation, revision 1.
FOUNDATION_VERSION = "0.1.0"

#: Restated here so an importer of this package sees it without opening a doc.
AUTHORIZATION_NOTICE = (
    "Read-only historical validation only. No dataset is included, no "
    "profitability claim can be made, and nothing here authorizes autonomous or "
    "funded trading. Execution remains disabled."
)

__all__ = [
    "ACTUAL_MISSED",
    "ACTUAL_NOT_APPLICABLE",
    "ACTUAL_RULE_DEVIATION",
    "ACTUAL_TAKEN",
    "ACTUAL_TRADE_STATES",
    "AUTHORIZATION_NOTICE",
    "BREAKEVEN_R_TOLERANCE",
    "COMPARISON_LABELS",
    "DATA_STATE_BELOW_MINIMUM",
    "DATA_STATE_COMPLETE",
    "DATA_STATE_EMPTY",
    "DEFAULT_RATIOS",
    "DIRECTIONS",
    "DIRECTION_LONG",
    "DIRECTION_SHORT",
    "DISPOSITION_SELECTED",
    "DISPOSITION_SKIPPED",
    "FOUNDATION_VERSION",
    "LABEL_METHODS",
    "LABEL_METHOD_DETERMINISTIC",
    "LABEL_METHOD_HUMAN_CONFIRMED",
    "MODEL_DISPLAY_NAMES",
    "MODEL_KEY_LEVEL_OPEN_10AM",
    "MODEL_ORB",
    "MODEL_STRICT_OTE",
    "NO_PROFITABILITY_CLAIM_NOTE",
    "OUTCOMES",
    "OUTCOME_BREAKEVEN",
    "OUTCOME_LOSS",
    "OUTCOME_WIN",
    "PARTITION_NAMES",
    "PARTITION_OUT_OF_SAMPLE",
    "PARTITION_TRAIN",
    "PARTITION_VALIDATION",
    "PF_DEFINED",
    "PF_UNDEFINED_BELOW_MINIMUM",
    "PF_UNDEFINED_NO_LOSSES",
    "PF_UNDEFINED_NO_SAMPLE",
    "PRIME_MODELS",
    "PRIME_SYMBOLS",
    "SCOPE_COMBINED_POLICY",
    "SELECTION_VIEW_FIELDS",
    "SYMBOL_MNQ",
    "SYMBOL_NQ",
    "TARGET_R_THRESHOLD",
    "DatasetSplit",
    "EngineValidationError",
    "MetricsReport",
    "MetricsValidationError",
    "PrimeValidationError",
    "RecordValidationError",
    "SelectionComparison",
    "SelectionEvidence",
    "SelectionKeyFn",
    "SelectionView",
    "SessionKeyFn",
    "SessionSelection",
    "SplitRatios",
    "SplitValidationError",
    "ValidatedCandidate",
    "assert_integrity",
    "assert_no_future_leakage",
    "combined_policy_metrics",
    "compute_metrics",
    "find_integrity_issues",
    "make_chronological_splits",
    "metrics_by_model",
    "select_one_per_session",
    "selection_view_of",
    "session_date_key",
    "sort_chronologically",
    "validate_records",
]
