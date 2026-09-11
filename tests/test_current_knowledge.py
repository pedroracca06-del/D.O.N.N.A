from pathlib import Path

from intelligence.current_knowledge import retrieve_current_prime


def test_retrieval_returns_current_prime_sources_only():
    result = retrieve_current_prime("What are the current PRIME models?")
    assert result.sources
    assert all("nova_knowledge_core/CURRENT/PRIME/" in s for s in result.sources)
    assert all("PROS_EVAN_INVESTING" not in s for s in result.sources)
    assert "[CURRENT SOURCE:" in result.text


def test_query_prefers_relevant_current_document():
    result = retrieve_current_prime("Explain the 10AM Key Level Open model")
    assert result.sources[0].endswith("10AM_KEY_LEVEL_OPEN.md")


def test_history_term_does_not_escape_current_authority_layer():
    result = retrieve_current_prime("Tell me about PROS")
    assert result.sources
    assert all("CURRENT/PRIME" in s for s in result.sources)
    assert "PROS_EVAN_INVESTING" not in result.text


def test_limits_are_enforced():
    result = retrieve_current_prime("PRIME ORB OTE", max_docs=2, max_chars=300)
    assert len(result.sources) <= 2
    assert len(result.text) <= 302


def test_retrieval_reports_content_hashes_for_exact_sources():
    import hashlib
    from intelligence import current_knowledge as ck

    result = retrieve_current_prime("current PRIME models", max_docs=2)
    assert len(result.source_hashes) == len(result.sources)
    for source, digest in zip(result.sources, result.source_hashes):
        body = (ck._REPO_ROOT / source).read_text(encoding="utf-8")
        assert digest == hashlib.sha256(body.encode("utf-8")).hexdigest()
        assert len(digest) == 64


def test_retrieval_never_emits_or_hashes_a_partial_document():
    from intelligence import current_knowledge as ck

    query = "current PRIME models"
    first = retrieve_current_prime(query, max_docs=1)
    source = first.sources[0]
    body = (ck._REPO_ROOT / source).read_text(encoding="utf-8")
    complete_chunk = f"[CURRENT SOURCE: {source}]\n{body.strip()}"
    result = retrieve_current_prime(query, max_docs=2, max_chars=len(complete_chunk) + 10)
    assert result.sources == (source,)
    assert result.text == complete_chunk
    assert len(result.source_hashes) == 1
