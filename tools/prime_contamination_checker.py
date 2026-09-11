"""Deterministic guardrails for current PRIME authority surfaces.

Historical/research material may contain legacy terms, so callers pass only text
already classified as a current-authority surface. The checks deliberately allow
explicit negative/historical statements about legacy concepts.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

CURRENT_MODELS = ("Strict OTE", "10AM Key Level Open", "ORB")


@dataclass(frozen=True)
class Finding:
    code: str
    message: str


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None


def _explicitly_noncurrent(term: str, text: str) -> bool:
    patterns = (
        rf"{term}.{{0,100}}\b(not current|not an? (?:entry|execution|setup) model|historical|research only|superseded|dead|old version of PRIME|does not define|does not govern|has no current (?:execution )?authority)\b",
        rf"{term}.{{0,100}}\b(never an? (?:entry|execution|setup) model)\b",
    )
    return any(_has(pattern, text) for pattern in patterns)


def check_current_text(text: str) -> list[Finding]:
    """Return doctrine-contamination findings for a current-authority text."""
    findings: list[Finding] = []
    normalized = " ".join(text.split())

    pros_positive = _has(r"\bPROS\b.{0,80}\b(active|current|execution model|setup model)\b", normalized)
    if pros_positive and not _explicitly_noncurrent(r"\bPROS\b", normalized):
        findings.append(Finding("PROS_CURRENT", "PROS is represented as current doctrine."))

    fvg_positive = _has(r"\bFVG\b.{0,80}\b(entry model|execution model|setup model)\b", normalized)
    if fvg_positive and not _explicitly_noncurrent(r"\bFVG\b", normalized):
        findings.append(Finding("FVG_ENTRY_MODEL", "FVG is represented as an entry/execution model."))

    if _has(r"\b10AM Powell\b.{0,80}\b(current|canonical|model|setup)\b", normalized) and not _has(
        r"\b10AM Powell\b.{0,80}\b(historical|former|old alias|alias)\b", normalized
    ):
        findings.append(Finding("OLD_10AM_NAME", "Legacy 10AM Powell naming is represented as current."))

    orb_1100 = _has(r"\bORB\b.{0,120}\b(valid|validity|cutoff|kill)\b.{0,40}\b11:00\b", normalized)
    orb_history = _has(r"\b(historical|old|former|research)\b.{0,120}\b11:00\b", normalized)
    if orb_1100 and not orb_history:
        findings.append(Finding("ORB_1100_CURRENT", "11:00 is represented as the current ORB validity cutoff."))

    if _has(r"\bMES\b.{0,80}\b(primary|preferred|current instrument)\b", normalized):
        findings.append(Finding("MES_PRIMARY", "MES is represented as the current primary/preferred instrument."))

    if _has(r"\b(A|B|C|D)[-/ ]grade\b|\bA/B/C/D\b.{0,80}\b(current|PRIME|setup)\b", normalized):
        findings.append(Finding("LEGACY_GRADING", "Legacy A-D setup grading is represented as current PRIME doctrine."))

    if _has(r"trading (bot|automation).{0,80}\b(permanently (dead|retired|abandoned)|gone forever)\b", normalized):
        findings.append(Finding("BOT_PERMANENTLY_GONE", "Trading automation is described as permanently abandoned."))

    if _has(r"trading (bot|automation).{0,80}\b(currently active|enabled now|live execution active)\b", normalized):
        findings.append(Finding("BOT_CURRENTLY_ACTIVE", "Trading automation is described as currently active."))

    return findings


def check_model_list(models: list[str] | tuple[str, ...]) -> list[Finding]:
    """Validate the authoritative active execution-model list exactly."""
    if tuple(models) != CURRENT_MODELS:
        return [Finding("MODEL_LIST", f"Active models must be exactly: {', '.join(CURRENT_MODELS)}.")]
    return []


def check_files(
    paths: list[str], *, live_prompts: bool = False, live_journal_route: bool = False
) -> dict[str, list[Finding]]:
    """Scan explicit current-authority files; caller chooses scope."""
    from pathlib import Path

    if live_prompts and live_journal_route:
        raise ValueError("choose only one live-surface mode")
    if live_journal_route:
        checker = check_live_journal_route_text
    else:
        checker = check_live_prompt_text if live_prompts else check_current_text
    results: dict[str, list[Finding]] = {}
    for raw in paths:
        path = Path(raw)
        text = path.read_text(encoding="utf-8")
        findings = checker(text)
        if findings:
            results[str(path)] = findings
    return results


def _main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Check current PRIME surfaces for legacy contamination.")
    parser.add_argument("paths", nargs="+", help="Explicit current-authority files to scan")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--live-prompts", action="store_true", help="Enable live Intelligence prompt checks")
    parser.add_argument("--live-journal-route", action="store_true", help="Check journal_analyze route context")
    args = parser.parse_args()
    results = check_files(
        args.paths, live_prompts=args.live_prompts, live_journal_route=args.live_journal_route
    )
    if args.as_json:
        payload = {path: [f.__dict__ for f in findings] for path, findings in results.items()}
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for path, findings in results.items():
            for finding in findings:
                print(f"{path}: {finding.code}: {finding.message}")
    return 1 if results else 0



def check_live_journal_route_text(text: str) -> list[Finding]:
    """Check only the live journal_analyze function for legacy context leakage."""
    start = text.find("async def journal_analyze")
    if start < 0:
        return [Finding("JOURNAL_ROUTE_MISSING", "journal_analyze route was not found.")]
    end = text.find("@app.post('/journal/delete')", start)
    block = text[start:] if end < 0 else text[start:end]
    findings: list[Finding] = []
    forbidden_fields = {
        "pros_phase": "legacy PROS phase",
        "pros_direction": "legacy PROS direction",
        "pros_ote": "legacy generic OTE",
        "ib_draw": "legacy IB draw",
        "nova_conf": "legacy confidence score",
        "nova_cmd": "legacy command field",
    }
    for field, label in forbidden_fields.items():
        if field in block:
            findings.append(Finding("JOURNAL_LEGACY_CONTEXT", f"Journal route serializes {label}."))
    if "'current_knowledge': _knowledge.text" not in block:
        findings.append(Finding("JOURNAL_CURRENT_KNOWLEDGE_MISSING", "Journal route lacks current PRIME knowledge context."))
    return findings

def check_live_prompt_text(text: str) -> list[Finding]:
    """Extra checks for live Intelligence prompt templates."""
    findings = check_current_text(text)
    normalized = " ".join(text.split())

    if _has(r"\bReference PROS phase\b|\bPROS phase\b", normalized):
        findings.append(Finding("PROMPT_PROS_REQUIRED", "Live prompt requires legacy PROS qualification."))
    if _has(r"\bfor MES and MNQ micro futures\b", normalized):
        findings.append(Finding("PROMPT_MES_SCOPE", "Live prompt still declares MES/MNQ legacy scope."))
    if _has(r"\bIB draw\b", normalized):
        findings.append(Finding("PROMPT_IB_REQUIRED", "Live prompt hard-codes IB draw as a qualification criterion."))
    if _has(r"\bMR2\b.{0,80}\bobjective ground truth\b", normalized):
        findings.append(Finding("MR2_OBJECTIVE_GROUND_TRUTH", "Live prompt elevates MR2 to objective ground truth."))
    return findings


if __name__ == "__main__":
    raise SystemExit(_main())
