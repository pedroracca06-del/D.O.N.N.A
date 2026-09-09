"""Deterministic provider benchmark primitives.

No provider calls live here. This module freezes fixture identity and scores hard
invariants so provider comparisons can be mocked/tested before spending credits.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class BenchmarkFixture:
    fixture_id: str
    version: int
    feature: str
    context: str
    question: str
    required_substrings: tuple[str, ...] = ()
    forbidden_substrings: tuple[str, ...] = ()

    def validate(self) -> None:
        if not re.fullmatch(r"PB-[0-9]{3}", self.fixture_id):
            raise ValueError("fixture_id must match PB-###")
        if self.version < 1:
            raise ValueError("fixture version must be >= 1")
        if not self.feature.strip() or not self.context.strip() or not self.question.strip():
            raise ValueError("feature, context, and question must be non-empty")
        if len(set(x.casefold() for x in self.required_substrings)) != len(self.required_substrings):
            raise ValueError("required_substrings contains duplicates")
        if len(set(x.casefold() for x in self.forbidden_substrings)) != len(self.forbidden_substrings):
            raise ValueError("forbidden_substrings contains duplicates")
        overlap = {x.casefold() for x in self.required_substrings} & {x.casefold() for x in self.forbidden_substrings}
        if overlap:
            raise ValueError("an invariant cannot be both required and forbidden")

    def canonical_payload(self) -> dict:
        return {
            "fixture_id": self.fixture_id,
            "version": self.version,
            "feature": self.feature,
            "context": self.context,
            "question": self.question,
            "required_substrings": list(self.required_substrings),
            "forbidden_substrings": list(self.forbidden_substrings),
        }


def fixture_hash(fixture: BenchmarkFixture) -> str:
    fixture.validate()
    payload = json.dumps(
        fixture.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_fixtures(path: str | Path) -> tuple[BenchmarkFixture, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("fixture file must contain a non-empty JSON array")
    fixtures: list[BenchmarkFixture] = []
    seen: set[tuple[str, int]] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each fixture must be an object")
        fixture = BenchmarkFixture(
            fixture_id=item["fixture_id"], version=item["version"], feature=item["feature"],
            context=item["context"], question=item["question"],
            required_substrings=tuple(item.get("required_substrings", ())),
            forbidden_substrings=tuple(item.get("forbidden_substrings", ())),
        )
        fixture.validate()
        key = (fixture.fixture_id, fixture.version)
        if key in seen:
            raise ValueError(f"duplicate fixture identity: {fixture.fixture_id} v{fixture.version}")
        seen.add(key)
        fixtures.append(fixture)
    return tuple(fixtures)


@dataclass(frozen=True)
class BenchmarkResult:
    fixture_id: str
    fixture_version: int
    fixture_hash: str
    provider: str
    model: str
    hard_pass: bool
    failures: tuple[str, ...]
    latency_ms: int | None = None
    request_count: int = 1
    retries: int = 0
    fallback_used: bool = False
    marginal_cost: float | None = None

    def to_record(self) -> dict:
        return {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "fixture_hash": self.fixture_hash,
            "provider": self.provider,
            "model": self.model,
            "hard_pass": self.hard_pass,
            "failures": list(self.failures),
            "latency_ms": self.latency_ms,
            "request_count": self.request_count,
            "retries": self.retries,
            "fallback_used": self.fallback_used,
            "marginal_cost": self.marginal_cost,
        }


def eligible_results(results: list[BenchmarkResult]) -> list[BenchmarkResult]:
    """Only hard-pass results may proceed to cost/latency comparison."""
    return [r for r in results if r.hard_pass]


def score_response(
    fixture: BenchmarkFixture,
    response_text: str,
    *,
    provider: str,
    model: str,
    latency_ms: int | None = None,
    request_count: int = 1,
    retries: int = 0,
    fallback_used: bool = False,
    marginal_cost: float | None = None,
) -> BenchmarkResult:
    fixture.validate()
    if not provider.strip() or not model.strip():
        raise ValueError("provider and model must be non-empty")
    if request_count < 1 or retries < 0 or retries >= request_count:
        raise ValueError("invalid request/retry accounting")
    if latency_ms is not None and latency_ms < 0:
        raise ValueError("latency_ms cannot be negative")
    if marginal_cost is not None and marginal_cost < 0:
        raise ValueError("marginal_cost cannot be negative")

    lowered = response_text.casefold()
    failures: list[str] = []

    for required in fixture.required_substrings:
        if required.casefold() not in lowered:
            failures.append(f"missing required invariant: {required}")

    for forbidden in fixture.forbidden_substrings:
        if forbidden.casefold() in lowered:
            failures.append(f"forbidden invariant present: {forbidden}")

    return BenchmarkResult(
        fixture_id=fixture.fixture_id,
        fixture_version=fixture.version,
        fixture_hash=fixture_hash(fixture),
        provider=provider,
        model=model,
        hard_pass=not failures,
        failures=tuple(failures),
        latency_ms=latency_ms,
        request_count=request_count,
        retries=retries,
        fallback_used=fallback_used,
        marginal_cost=marginal_cost,
    )
