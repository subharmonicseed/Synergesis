from synergesis_cognitive_core import Fact, SemanticMemory
from synergesis_world_belief_view import VersionedBeliefView


def fact(subject, predicate, obj, evidence, observed="2026-09-12T00:00:00+00:00"):
    return Fact(
        subject=subject,
        predicate=predicate,
        object=obj,
        source="test",
        confidence=1.0,
        observed_at=observed,
        evidence_id=evidence,
    )


def test_head_is_latest_append_not_lexicographic_evidence_id(tmp_path):
    memory = SemanticMemory(tmp_path / "semantic.jsonl")
    memory.add(fact("s", "p", "old", "z-old"))
    memory.add(fact("s", "p", "new", "a-new"))

    view = VersionedBeliefView(memory, versioned_predicates=("p",))
    head = view.head(subject="s", predicate="p")
    assert head.current.object == "new"
    assert [f.object for f in head.history] == ["old", "new"]


def test_restart_preserves_append_order_head(tmp_path):
    path = tmp_path / "semantic.jsonl"
    memory = SemanticMemory(path)
    memory.add(fact("s", "p", "v1", "e1"))
    memory.add(fact("s", "p", "v2", "e2"))

    restarted = SemanticMemory(path)
    view = VersionedBeliefView(restarted, versioned_predicates=("p",))
    assert view.current(subject="s", predicate="p").object == "v2"


def test_materialized_view_keeps_non_versioned_multivalued_facts(tmp_path):
    memory = SemanticMemory(tmp_path / "semantic.jsonl")
    memory.add(fact("s", "versioned", "v1", "e1"))
    memory.add(fact("s", "versioned", "v2", "e2"))
    memory.add(fact("s", "tag", "alpha", "e3"))
    memory.add(fact("s", "tag", "beta", "e4"))

    view = VersionedBeliefView(
        memory,
        versioned_predicates=("versioned",),
    )
    materialized = view.materialized_facts()
    pairs = {(f.predicate, f.object) for f in materialized}
    assert ("versioned", "v1") not in pairs
    assert ("versioned", "v2") in pairs
    assert ("tag", "alpha") in pairs
    assert ("tag", "beta") in pairs
    assert memory.count() == 4


def test_current_facts_returns_one_head_per_subject_predicate(tmp_path):
    memory = SemanticMemory(tmp_path / "semantic.jsonl")
    memory.add(fact("a", "p", "1", "e1"))
    memory.add(fact("b", "p", "2", "e2"))
    memory.add(fact("a", "p", "3", "e3"))

    view = VersionedBeliefView(memory, versioned_predicates=("p",))
    current = view.current_facts(predicate="p")
    assert {(f.subject, f.object) for f in current} == {
        ("a", "3"),
        ("b", "2"),
    }


def test_unknown_versioned_predicate_request_is_rejected(tmp_path):
    memory = SemanticMemory(tmp_path / "semantic.jsonl")
    view = VersionedBeliefView(memory, versioned_predicates=("p",))

    import pytest
    with pytest.raises(ValueError, match="not declared versioned"):
        view.current(subject="s", predicate="q")
    with pytest.raises(ValueError, match="not declared versioned"):
        view.current_facts(predicate="q")


def test_snapshot_reports_history_and_current_counts_separately(tmp_path):
    memory = SemanticMemory(tmp_path / "semantic.jsonl")
    memory.add(fact("s", "p", "v1", "e1"))
    memory.add(fact("s", "p", "v2", "e2"))
    memory.add(fact("s", "other", "x", "e3"))

    view = VersionedBeliefView(memory, versioned_predicates=("p",))
    snapshot = view.snapshot()
    assert snapshot.history_fact_count == 3
    assert snapshot.current_fact_count == 2
    assert len(snapshot.digest) == 64


def test_current_means_latest_recorded_not_truth_claim(tmp_path):
    memory = SemanticMemory(tmp_path / "semantic.jsonl")
    memory.add(fact("s", "p", "likely-true", "e1"))
    memory.add(fact("s", "p", "later-but-wrong", "e2"))

    view = VersionedBeliefView(memory, versioned_predicates=("p",))
    assert view.current(subject="s", predicate="p").object == "later-but-wrong"
    assert len(view.history(subject="s", predicate="p")) == 2


def test_view_requires_explicit_versioned_predicates(tmp_path):
    memory = SemanticMemory(tmp_path / "semantic.jsonl")

    import pytest
    with pytest.raises(ValueError, match="at least one"):
        VersionedBeliefView(memory, versioned_predicates=())
    with pytest.raises(ValueError, match="non-empty"):
        VersionedBeliefView(memory, versioned_predicates=(" ",))
