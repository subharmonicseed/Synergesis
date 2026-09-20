import tempfile
from pathlib import Path
import pytest
from synergesis_cognitive_core import SynCognitiveCore, Rule
from synergesis_research_layer import EvidenceStore, DeepResearch, SynEcho, Vyra, Aura


def test_evidence_must_exist_before_claim():
    with tempfile.TemporaryDirectory() as d:
        dr = DeepResearch(EvidenceStore(Path(d)/"e.jsonl"))
        with pytest.raises(ValueError):
            dr.propose_claim("x", ["missing"])


def test_approved_claim_can_enter_memory():
    with tempfile.TemporaryDirectory() as d:
        dr = DeepResearch(EvidenceStore(Path(d)/"e.jsonl"))
        e = dr.ingest("paper", "T", "content", "paper")
        c = dr.propose_claim("claim", [e.evidence_id])
        with pytest.raises(ValueError):
            dr.commit_approved_claim(c.claim_id, SynCognitiveCore(Path(d)/"m.jsonl").memory,
                                      "s", "p", "o", .8)
        c = dr.approve(c.claim_id, "human")
        core = SynCognitiveCore(Path(d)/"m2.jsonl")
        f = dr.commit_approved_claim(c.claim_id, core.memory, "s", "p", "o", .8)
        assert f.confidence == .8


def test_echo_is_bounded_and_deterministic():
    with tempfile.TemporaryDirectory() as d:
        core = SynCognitiveCore(Path(d)/"m.jsonl")
        a = core.remember("s", "p", "o", "src", .5)
        r = SynEcho().compare([a], [])
        assert r.change_rate == 1.0
        assert 0 <= r.change_rate <= 1


def test_vyra_is_not_random():
    idea1 = Vyra().generate(["a", "b"], "recombine", "explicit")
    idea2 = Vyra().generate(["a", "b"], "recombine", "explicit")
    assert idea1 == idea2


def test_aura_orchestrates_core():
    with tempfile.TemporaryDirectory() as d:
        core = SynCognitiveCore(Path(d)/"m.jsonl")
        aura = Aura(core)
        aura.research_ingest("src", "title", "text", "web")
        core.remember("x", "state", "ready", "test", .9)
        response = aura.cycle(required_predicates=["state"])
        assert response.evidence_count == 1
        assert response.memory_count == 1
        assert response.drift.change_rate == 0
