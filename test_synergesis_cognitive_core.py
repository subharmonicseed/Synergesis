from pathlib import Path
import tempfile
from synergesis_cognitive_core import SemanticMemory, Fact, Rule, SynCognitiveCore


def test_semantic_memory_persists():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "memory.jsonl"
        m = SemanticMemory(p)
        f = Fact("a", "is", "b", "test", 0.8, "2026-01-01T00:00:00+00:00", "e1")
        m.add(f)
        assert SemanticMemory(p).query() == [f]


def test_core_inference_is_auditable():
    with tempfile.TemporaryDirectory() as d:
        core = SynCognitiveCore(Path(d) / "m.jsonl")
        core.remember("sun", "is", "star", "source-A", 0.9, "fact-1")
        cycle = core.cycle_once([Rule("star-rule", "is", "star", "class", "stellar-body")])
        assert cycle.inferred_count == 1
        inferred = core.memory.query(subject="sun", predicate="class", object="stellar-body")
        assert len(inferred) == 1
        assert inferred[0].source == "THALES:star-rule"


def test_missing_information_is_reported():
    with tempfile.TemporaryDirectory() as d:
        core = SynCognitiveCore(Path(d) / "m.jsonl")
        cycle = core.cycle_once(required_predicates=["mass", "distance"])
        assert cycle.gaps == ("distance", "mass")


def test_confidence_is_bounded():
    with tempfile.TemporaryDirectory() as d:
        core = SynCognitiveCore(Path(d) / "m.jsonl")
        try:
            core.remember("x", "p", "y", "src", 1.2)
            assert False
        except ValueError:
            pass
