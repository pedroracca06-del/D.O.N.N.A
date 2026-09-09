from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    check: str
    passed: bool
    detail: str


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE | re.MULTILINE) is not None


def audit_market_map(path: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8")
    executable = "\n".join(line.split("//", 1)[0] for line in text.splitlines())
    findings: list[Finding] = []
    findings.append(Finding("pine_v6", _has(r"^//@version=6$", text), "Pine v6 declaration present"))
    findings.append(Finding("visual_only", _has(r"Contains no trading logic of any kind", text), "visual-only boundary declared"))
    findings.append(Finding("orb_start_0800", _has(r"orbStartHour\s*=\s*8\b", text) and _has(r"orbStartMinute\s*=\s*0\b", text), "ORB starts 08:00 ET"))
    findings.append(Finding("orb_end_0815", _has(r"orbEndHour\s*=\s*8\b", text) and _has(r"orbEndMinute\s*=\s*15\b", text), "ORB freezes 08:15 ET"))
    findings.append(Finding("one_minute_orb", 'request.security(syminfo.tickerid, "1", _f_orbHigh1m()' in text, "ORB high derived from 1m"))
    findings.append(Finding("no_signal_engine", not _has(r"buySignal|sellSignal|activeGrade|signalReason", executable), "no legacy signal variables"))
    findings.append(Finding("no_execution_bridge", not _has(r"webhook|broker|bridge|strategy\.entry|strategy\.exit", executable), "no execution bridge/broker path"))
    return findings


def phase1_gap_report(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    visual_kill_1100 = _has(r"orbKillHour\s*=\s*11\b", text)
    has_validity_1030 = _has(r"10\s*[:.]?\s*30|orbValid.*10|valid.*10:30", text)
    has_status_surface = _has(r"table\.new|ORB_VALID|ORB_INVALID|PRIME", text)
    return {
        "visual_reference_through_1100": visual_kill_1100,
        "explicit_setup_validity_ends_1030": has_validity_1030,
        "explicit_prime_or_orb_status_surface": has_status_surface,
        "phase1_ready_for_implementation": visual_kill_1100 and not has_validity_1030,
        "required_change": "Add a separate deterministic ORB setup-validity state ending 10:30 ET; do not repurpose the 11:00 visual lifetime as setup validity.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit NOVA Market Map against PRIME Indicator Phase I invariants.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    findings = audit_market_map(args.path)
    payload = {
        "path": str(args.path),
        "foundation": [asdict(item) for item in findings],
        "phase1_gap": phase1_gap_report(args.path),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for item in findings:
            print(f"{'PASS' if item.passed else 'FAIL'} {item.check}: {item.detail}")
        print(json.dumps(payload["phase1_gap"], indent=2))
    return 0 if all(item.passed for item in findings) else 1


if __name__ == "__main__":
    raise SystemExit(main())
