from synergesis_context import ContextBudget, LexicalContextSelector, tokenize
from synergesis_cognitive_core import Fact
from synergesis_research_layer import Evidence


def fact(eid, subject, predicate, obj):
    return Fact(
        subject=subject,
        predicate=predicate,
        object=obj,
        source="test",
        confidence=1.0,
        observed_at="2026-01-01T00:00:00+00:00",
        evidence_id=eid,
    )


def evidence(eid, title, content):
    return Evidence(
        evidence_id=eid,
        source="test",
        title=title,
        content=content,
        retrieved_at="2026-01-01T00:00:00+00:00",
        source_type="test",
    )


def selector(max_facts=2, max_evidence=2):
    return LexicalContextSelector(
        budget=ContextBudget(max_facts=max_facts, max_evidence=max_evidence),
        k1=1.5,
        b=0.75,
    )


def test_tokenization_is_casefolded():
    assert tokenize("Syn SYN mémoire") == ("syn", "syn", "mémoire")


def test_retrieval_selects_relevant_memory_only():
    facts = (
        fact("f1", "market", "trend", "volatility rising"),
        fact("f2", "garden", "weather", "rain expected"),
    )
    ev = (
        evidence("e1", "Market report", "volatility increased after earnings"),
        evidence("e2", "Recipe", "bread and flour"),
    )
    result = selector().select(
        query="market volatility",
        facts=facts,
        evidence=ev,
    )
    assert [f.evidence_id for f in result.facts] == ["f1"]
    assert [e.evidence_id for e in result.evidence] == ["e1"]


def test_retrieval_does_not_pad_unrelated_items():
    result = selector().select(
        query="quantum entanglement",
        facts=(fact("f1", "garden", "weather", "rain"),),
        evidence=(evidence("e1", "Recipe", "bread flour"),),
    )
    assert result.facts == ()
    assert result.evidence == ()


def test_budget_is_hard_limit():
    facts = tuple(
        fact(f"f{i}", "market", "signal", f"market volatility signal {i}")
        for i in range(5)
    )
    result = selector(max_facts=2, max_evidence=1).select(
        query="market volatility signal",
        facts=facts,
        evidence=(),
    )
    assert len(result.facts) == 2
    assert len(result.fact_ranking) == 2


def test_tie_break_is_deterministic():
    facts = (
        fact("b", "alpha", "matches", "query"),
        fact("a", "alpha", "matches", "query"),
    )
    result = selector().select(
        query="alpha matches query",
        facts=facts,
        evidence=(),
    )
    assert [f.evidence_id for f in result.facts] == ["a", "b"]
