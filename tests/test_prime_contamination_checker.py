from tools.prime_contamination_checker import (
    CURRENT_MODELS,
    check_current_text,
    check_model_list,
)


def codes(text: str) -> set[str]:
    return {finding.code for finding in check_current_text(text)}


def test_exact_current_model_list_passes():
    assert check_model_list(list(CURRENT_MODELS)) == []


def test_fourth_model_fails():
    findings = check_model_list([*CURRENT_MODELS, "FVG"])
    assert [f.code for f in findings] == ["MODEL_LIST"]


def test_pros_current_fails_but_history_passes():
    assert "PROS_CURRENT" in codes("PROS is an active execution model in PRIME.")
    assert "PROS_CURRENT" not in codes("PROS is historical research and is not current PRIME doctrine.")
    assert "PROS_CURRENT" not in codes("PROS is the superseded dead old version of PRIME.")
    assert "PROS_CURRENT" not in codes("Historical PROS does not define the current model.")


def test_fvg_entry_model_fails_but_context_statement_passes():
    assert "FVG_ENTRY_MODEL" in codes("FVG is an entry model used by PRIME.")
    assert "FVG_ENTRY_MODEL" not in codes("FVG is context/confluence only, never an entry model.")


def test_old_10am_name_fails_when_presented_as_current():
    assert "OLD_10AM_NAME" in codes("10AM Powell is the current setup model.")
    assert "OLD_10AM_NAME" not in codes("10AM Powell is a historical alias for 10AM Key Level Open.")


def test_orb_1100_current_validity_fails_but_history_passes():
    assert "ORB_1100_CURRENT" in codes("ORB validity cutoff is 11:00 ET.")
    assert "ORB_1100_CURRENT" not in codes("Historical RP material used an 11:00 cutoff; current validity ends 10:30 ET.")


def test_mes_primary_fails():
    assert "MES_PRIMARY" in codes("MES is the preferred current instrument for NOVA.")


def test_legacy_grading_fails():
    assert "LEGACY_GRADING" in codes("A/B/C/D setup grading is current PRIME doctrine.")


def test_bot_state_language_is_guarded_both_directions():
    assert "BOT_PERMANENTLY_GONE" in codes("The trading bot is permanently retired and gone forever.")
    assert "BOT_CURRENTLY_ACTIVE" in codes("The trading automation is currently active for live execution.")
    clean = codes("Trading automation is temporarily disabled and preserved for separately approved future return.")
    assert "BOT_PERMANENTLY_GONE" not in clean
    assert "BOT_CURRENTLY_ACTIVE" not in clean


def test_check_files_returns_only_files_with_findings(tmp_path):
    from tools.prime_contamination_checker import check_files
    good = tmp_path / "good.md"
    bad = tmp_path / "bad.md"
    good.write_text("FVG is context/confluence only, never an entry model.", encoding="utf-8")
    bad.write_text("PROS is an active execution model in PRIME.", encoding="utf-8")
    result = check_files([str(good), str(bad)])
    assert str(good) not in result
    assert [f.code for f in result[str(bad)]] == ["PROS_CURRENT"]


def test_live_prompt_checks_detect_verified_legacy_patterns():
    from tools.prime_contamination_checker import check_live_prompt_text
    text = (
        "You are NOVA for MES and MNQ micro futures. Reference PROS phase, OTE, IB draw. "
        "MR2 is objective ground truth."
    )
    found = {finding.code for finding in check_live_prompt_text(text)}
    assert {"PROMPT_PROS_REQUIRED", "PROMPT_MES_SCOPE", "PROMPT_IB_REQUIRED", "MR2_OBJECTIVE_GROUND_TRUTH"} <= found


def test_live_journal_route_detects_legacy_context_fields():
    from tools.prime_contamination_checker import check_live_journal_route_text
    text = """
async def journal_analyze(request):
    x = s.get('pros_phase')
    y = s.get('nova_conf')
@app.post('/journal/delete')
async def journal_delete(request):
    pass
"""
    found = {f.code for f in check_live_journal_route_text(text)}
    assert 'JOURNAL_LEGACY_CONTEXT' in found
    assert 'JOURNAL_CURRENT_KNOWLEDGE_MISSING' in found


def test_actual_journal_route_is_clean_and_has_current_knowledge():
    from pathlib import Path
    from tools.prime_contamination_checker import check_files

    main_py = Path(__file__).resolve().parents[1] / 'main.py'
    result = check_files([str(main_py)], live_journal_route=True)
    assert result == {}



def test_actual_live_prompt_modules_are_clean():
    from pathlib import Path
    from tools.prime_contamination_checker import check_files

    root = Path(__file__).resolve().parents[1]
    prompts = [
        root / "intelligence" / "prompts" / "assistant.py",
        root / "intelligence" / "prompts" / "journal_review.py",
    ]
    assert check_files([str(path) for path in prompts], live_prompts=True) == {}
