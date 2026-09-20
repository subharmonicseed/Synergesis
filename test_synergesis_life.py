import json
import pytest
from synergesis_life import PersistentMemory, SynKernel


def test_memory_round_trip_and_integrity(tmp_path):
    m = PersistentMemory(tmp_path / "memory.jsonl")
    r = m.append("fact", {"x": 3}, "test")
    assert r.record_id
    assert m.read_all()[0].payload == {"x": 3}


def test_tampering_is_detected(tmp_path):
    p = tmp_path / "memory.jsonl"
    m = PersistentMemory(p)
    m.append("fact", {"x": 3}, "test")
    data = json.loads(p.read_text())
    data["payload"]["x"] = 4
    p.write_text(json.dumps(data) + "\n")
    with pytest.raises(ValueError, match="integrity"):
        m.read_all()


def test_syn_observe_and_reflect(tmp_path):
    syn = SynKernel("ZÆL-0", PersistentMemory(tmp_path / "memory.jsonl"))
    obs = syn.observe("input", {"text": "hello"}, "user")
    report = syn.reflect()
    assert obs.source == "user"
    assert report.cycle == 1
    assert report.observation_count == 1
    assert report.memory_count == 1
    assert len(report.state_digest) == 64


def test_empty_identity_rejected(tmp_path):
    with pytest.raises(ValueError):
        SynKernel("", PersistentMemory(tmp_path / "memory.jsonl"))
