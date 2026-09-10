"""Deterministic read-only retrieval from NOVA's CURRENT knowledge layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import re

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CURRENT_PRIME = _REPO_ROOT / "nova_knowledge_core" / "CURRENT" / "PRIME"
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {"a", "an", "and", "are", "for", "in", "is", "of", "on", "the", "to", "what"}


@dataclass(frozen=True)
class KnowledgeSelection:
    text: str
    sources: tuple[str, ...]
    source_hashes: tuple[str, ...]


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.casefold()) if t not in _STOP and len(t) > 1}


def _safe_docs(root: Path) -> list[Path]:
    resolved = root.resolve()
    docs: list[Path] = []
    for path in sorted(root.glob("*.md")):
        if path.is_symlink() or not path.is_file():
            continue
        if resolved not in path.resolve().parents:
            continue
        docs.append(path)
    return docs


class CurrentKnowledgeIntegrityError(RuntimeError):
    """Raised when Git-authoritative CURRENT PRIME documents disagree or are malformed."""


def validate_current_prime_package(root: Path | None = None) -> tuple[str, ...]:
    """Fail closed when the CURRENT PRIME package loses required authority invariants."""
    root = root or _CURRENT_PRIME
    docs = {path.name: path.read_text(encoding="utf-8") for path in _safe_docs(root)}
    required = {
        "README.md",
        "PRIME_FRAMEWORK.md",
        "EXECUTION_MODELS.md",
        "STRICT_OTE.md",
        "10AM_KEY_LEVEL_OPEN.md",
        "ORB.md",
        "RISK_AND_SESSION_RULES.md",
    }
    missing = sorted(required - docs.keys())
    if missing:
        raise CurrentKnowledgeIntegrityError(f"missing current authority documents: {', '.join(missing)}")

    unexpected = sorted(docs.keys() - required)
    if unexpected:
        raise CurrentKnowledgeIntegrityError(
            f"unexpected current authority documents: {', '.join(unexpected)}"
        )

    problems: list[str] = []
    for name, body in docs.items():
        if "Status: CURRENT" not in body:
            problems.append(f"{name}: missing Status: CURRENT")
        if "Authority:" not in body:
            problems.append(f"{name}: missing Authority metadata")

    expected_models = ("Strict OTE", "10AM Key Level Open", "ORB")
    for name in ("README.md", "EXECUTION_MODELS.md"):
        body = docs[name]
        positions = tuple(body.find(model) for model in expected_models)
        if any(pos < 0 for pos in positions) or positions != tuple(sorted(positions)):
            problems.append(f"{name}: current model list is incomplete or out of canonical order")
        if "exactly three" not in body.casefold():
            problems.append(f"{name}: missing exactly-three model invariant")
        if "PROS" not in body or not any(word in body.casefold() for word in ("superseded", "dead")):
            problems.append(f"{name}: PROS supersession is not explicit")
        if "FVG" not in body or "not an entry model" not in body:
            problems.append(f"{name}: FVG boundary is not explicit")

    risk = docs["RISK_AND_SESSION_RULES.md"].casefold()
    for phrase, label in (("one real trade per day", "one-trade rule"), ("$500", "$500 risk ceiling"), ("before 09:45 et", "09:45 gate"), ("orb is the only approved execution model", "ORB-only early window")):
        if phrase not in risk:
            problems.append(f"RISK_AND_SESSION_RULES.md: missing {label}")

    # An explicit contradiction is not neutralised by required good phrasing
    # sitting somewhere else in the same document -- both a correct sentence
    # and a wrong one can be true statements about the *text*, and only the
    # absence of the wrong one is a true statement about the *doctrine*. Each
    # document is scanned independently for the six invariants below.
    for name, body in docs.items():
        for label, message in _explicit_contradictions(body):
            problems.append(f"{name}: {message}")

    if problems:
        raise CurrentKnowledgeIntegrityError("; ".join(problems))
    return tuple(sorted(docs))


# Deliberately a fixed, bounded set of regexes -- not an attempt at general
# natural-language contradiction detection. Each pattern targets one known
# adversarial phrasing of "the opposite of an invariant we already require
# elsewhere." New adversarial phrasings need a new pattern, not a smarter
# parser.
_CONTRADICTION_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (
        "MODEL_COUNT",
        "current model list contradicts the exactly-three-models invariant",
        r"\b(?:four|4)\b[^.\n]{0,30}\b(?:active|current)\b[^.\n]{0,30}\bexecution\s+models?\b"
        r"|\b(?:fourth|4th)\b[^.\n]{0,30}\b(?:active|current\s+)?execution\s+model\b"
        r"|\bmore\s+than\s+three\b[^.\n]{0,30}\bexecution\s+models?\b",
    ),
    (
        "PROS_REACTIVATED",
        "PROS is stated as active/current, contradicting PROS supersession",
        r"\bPROS\b[^.\n]{0,80}\bis\s+(?:an?\s+)?(?:active|current)\s+execution\s+model\b"
        r"|\bPROS\b[^.\n]{0,40}\bis\s+(?:now\s+)?(?:active|current)\b"
        r"|\bPROS\s+is\s+not\s+superseded\b"
        r"|\bPROS\s+and\s+PRIME\s+(?:run|are)\s+(?:in\s+)?parallel\b",
    ),
    (
        "FVG_ENTRY",
        "FVG is stated as an entry/execution model, contradicting the FVG boundary",
        r"\bFVG\b(?:(?!\bnot\b)[^.\n]){0,80}\bis\s+(?:an?\s+(?:valid\s+)?)?(?:entry|execution|setup)\s+model\b"
        r"|\bFVG\s+(?:can\s+be\s+used\s+as|is)\s+(?:an?\s+)?(?:valid\s+)?entry\b",
    ),
    (
        "SECOND_TRADE",
        "a second funded/eval trade is stated as permitted, contradicting the one-trade-per-day rule",
        r"\btwo\s+(?:real\s+)?(?:funded|eval)?\s*trades?\s+per\s+day\b"
        r"|\bmultiple\s+(?:funded|eval)\s+trades\s+per\s+day\b"
        r"|\bsecond\s+(?:funded|eval)\s+trade\s+is\s+(?:permitted|allowed|authorized)\b",
    ),
    (
        "RISK_CEILING",
        "a risk ceiling other than $500 is stated, contradicting the $500 maximum",
        r"\$(?!500\b)[\d,]+(?:\.\d+)?\s+(?:maximum|max)\s+risk\b"
        r"|\brisk\s+ceiling\s+(?:is|of)\s+\$(?!500\b)[\d,]+(?:\.\d+)?\b",
    ),
    (
        "EARLY_WINDOW",
        "a non-ORB model is stated as approved before 09:45 ET, contradicting the ORB-only early window",
        r"\bbefore\s+09:45\s*ET\b[^.\n]{0,60}\b(?:Strict\s+OTE|10AM\s+Key\s+Level\s+Open)\b[^.\n]{0,30}"
        r"\b(?:is\s+)?(?:also\s+)?(?:approved|permitted|allowed)\b"
        r"|\bbefore\s+09:45\s*ET\b[^.\n]{0,60}\ball\s+(?:current\s+)?models?\s+(?:are\s+)?(?:approved|permitted|allowed)\b",
    ),
)


# A negation sitting immediately before a match (in the same sentence/line,
# e.g. "not a fourth execution model", "no second funded trade is permitted")
# means the text is stating the invariant, not contradicting it. Only the
# same sentence counts -- an unrelated negation left over from a PRECEDING
# sentence (e.g. the required "...is not an entry model." anchor sitting
# right before an injected "FVG is a valid entry model" contradiction) must
# not suppress detection of the new sentence that follows it.
_NEGATION_WORDS = re.compile(r"\b(?:not|never|isn't|doesn't|does\s+not|no\s+longer|without|non-|no)\b", re.IGNORECASE)
_NEGATION_WINDOW = 25


def _negated_immediately_before(body: str, pos: int) -> bool:
    window = body[max(0, pos - _NEGATION_WINDOW):pos]
    boundary = max(window.rfind("."), window.rfind("\n"))
    same_sentence_tail = window[boundary + 1:]
    return _NEGATION_WORDS.search(same_sentence_tail) is not None


def _explicit_contradictions(body: str) -> list[tuple[str, str]]:
    """Return (code, message) pairs for each explicit-contradiction pattern that matches."""
    findings: list[tuple[str, str]] = []
    for code, message, pattern in _CONTRADICTION_PATTERNS:
        for match in re.finditer(pattern, body, re.IGNORECASE):
            if _negated_immediately_before(body, match.start()):
                continue
            findings.append((code, message))
            break
    return findings


def retrieve_current_prime(query: str, *, max_docs: int = 3, max_chars: int = 5000) -> KnowledgeSelection:
    """Return a bounded CURRENT-only PRIME context selection for a user query."""
    if max_docs < 1 or max_chars < 1:
        raise ValueError("max_docs and max_chars must be positive")

    validate_current_prime_package(_CURRENT_PRIME)
    docs = _safe_docs(_CURRENT_PRIME)
    q = _tokens(query)
    ranked: list[tuple[int, str, Path, str]] = []
    for path in docs:
        body = path.read_text(encoding="utf-8")
        name_tokens = _tokens(path.stem.replace("_", " "))
        body_tokens = _tokens(body)
        score = (4 * len(q & name_tokens)) + len(q & body_tokens)
        if path.name in {"README.md", "EXECUTION_MODELS.md"}:
            score += 1
        ranked.append((score, path.name, path, body))

    ranked.sort(key=lambda row: (-row[0], row[1]))
    chosen = ranked[:max_docs]
    chunks: list[str] = []
    sources: list[str] = []
    source_hashes: list[str] = []
    used = 0
    for _score, _name, path, body in chosen:
        rel = path.relative_to(_REPO_ROOT).as_posix()
        chunk = f"[CURRENT SOURCE: {rel}]\n{body.strip()}"
        separator_cost = 2 if chunks else 0
        if used + separator_cost + len(chunk) > max_chars:
            continue
        chunks.append(chunk)
        sources.append(rel)
        source_hashes.append(hashlib.sha256(body.encode("utf-8")).hexdigest())
        used += separator_cost + len(chunk)

    return KnowledgeSelection(
        text="\n\n".join(chunks),
        sources=tuple(sources),
        source_hashes=tuple(source_hashes),
    )
