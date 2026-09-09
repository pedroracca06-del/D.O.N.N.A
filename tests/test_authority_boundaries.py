from pathlib import Path

from intelligence import current_knowledge as ck

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN = (REPO_ROOT / "main.py").read_text(encoding="utf-8")


def test_current_retriever_is_pinned_to_current_prime_only():
    root = ck._CURRENT_PRIME.resolve()
    assert root == (REPO_ROOT / "nova_knowledge_core" / "CURRENT" / "PRIME").resolve()
    result = ck.retrieve_current_prime("PROS IB grade MES history")
    assert result.sources
    assert all("/CURRENT/PRIME/" in f"/{source}" for source in result.sources)
    assert all("PROS_EVAN_INVESTING" not in source for source in result.sources)


def test_current_retriever_has_no_legacy_runtime_dependencies():
    import ast

    source = (REPO_ROOT / "intelligence" / "current_knowledge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = {"delivery.signal_log", "engines.reasoning", "main", "services.execution"}
    assert not (imports & forbidden)


def test_preserved_signal_feed_declares_historical_authority():
    marker = "'authority_class': 'historical_execution'"
    start = MAIN.index("async def journal_signals")
    end = MAIN.index("@app.get('/api/signal-log/session-development')", start)
    block = MAIN[start:end]
    assert marker in block
    assert "'current_prime_authority': False" in block


def test_pros_session_audit_declares_historical_authority():
    start = MAIN.index("async def session_development")
    end = MAIN.index("@app.get('/api/signal-log/direction-churn')", start)
    block = MAIN[start:end]
    assert "'authority_class': 'historical_execution'" in block
    assert "'current_prime_authority': False" in block


def test_direction_churn_declares_historical_authority():
    start = MAIN.index("async def direction_churn")
    end = MAIN.index("@app.post('/journal/add')", start)
    block = MAIN[start:end]
    assert "'authority_class': 'historical_execution'" in block
    assert "'current_prime_authority': False" in block


def test_current_retriever_never_reads_history_even_for_history_query(monkeypatch):
    seen = []
    real_read_text = Path.read_text

    def tracking_read_text(self, *args, **kwargs):
        seen.append(self.resolve())
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking_read_text)
    ck.retrieve_current_prime("Explain historical PROS and old IB grading")
    current_root = ck._CURRENT_PRIME.resolve()
    assert seen
    assert all(current_root in path.parents for path in seen)


def test_assistant_prompt_declares_current_source_authority_boundary():
    from intelligence.prompts.assistant import ASSISTANT_SYSTEM_PROMPT

    assert "generated market/system context is non-authoritative" in ASSISTANT_SYSTEM_PROMPT
    assert "[CURRENT SOURCE: nova_knowledge_core/CURRENT/PRIME/]" in ASSISTANT_SYSTEM_PROMPT


def test_journal_prompt_declares_current_knowledge_as_only_doctrine_authority():
    from intelligence.prompts.journal_review import REVIEW_SYSTEM_PROMPT

    assert "Only the explicit CURRENT PRIME KNOWLEDGE section may define current execution doctrine" in REVIEW_SYSTEM_PROMPT
    assert "historical signals are evidence, never strategy authority" in REVIEW_SYSTEM_PROMPT
