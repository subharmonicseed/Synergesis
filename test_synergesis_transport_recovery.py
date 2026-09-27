from pathlib import Path
from datetime import timedelta
import json
from synergesis_provenance_transport import _digest

import pytest

from test_synergesis_provenance_transport import setup
from synergesis_provenance_transport import ProvenanceTransportImporter


def fresh(s):
    return ProvenanceTransportImporter(
        graph=s["local_graph"], security_graph=s["local_security"],
        receipt_store=s["local_store"], receipt_verifier=s["verifier"],
        replay_ledger=s["replay"], policy=s["importer"].policy,
        now_fn=s["importer"].now_fn,
    )


def marker_path(s):
    return Path(str(s["replay"].path) + ".transport-attempt.json")


def assert_uncertain(s):
    with pytest.raises(ValueError, match="uncertain interrupted"):
        fresh(s).import_bundle(s["bundle"])


def test_fault_after_first_receipt_write_fails_closed_after_restart(tmp_path, monkeypatch):
    s = setup(tmp_path)
    orig = s["local_store"].append
    calls = 0
    def fault(receipt):
        nonlocal calls
        calls += 1
        orig(receipt)
        if calls == 1:
            raise RuntimeError("crash")
    monkeypatch.setattr(s["local_store"], "append", fault)
    with pytest.raises(RuntimeError, match="crash"):
        s["importer"].import_bundle(s["bundle"])
    assert marker_path(s).exists()
    assert_uncertain(s)
    assert marker_path(s).exists()


def test_fault_after_graph_create_fails_closed(tmp_path, monkeypatch):
    s = setup(tmp_path)
    orig = s["local_graph"].create
    def fault(*args, **kwargs):
        orig(*args, **kwargs)
        raise RuntimeError("graph crash")
    monkeypatch.setattr(s["local_graph"], "create", fault)
    with pytest.raises(RuntimeError, match="graph crash"):
        s["importer"].import_bundle(s["bundle"])
    assert_uncertain(s)


def test_append_durable_then_raises_reconciles_but_replay_rejected(tmp_path, monkeypatch):
    s = setup(tmp_path)
    orig = s["replay"].append
    def fault(**kwargs):
        orig(**kwargs)
        raise RuntimeError("after append")
    monkeypatch.setattr(s["replay"], "append", fault)
    with pytest.raises(RuntimeError, match="after append"):
        s["importer"].import_bundle(s["bundle"])
    assert marker_path(s).exists()
    restarted = fresh(s)
    with pytest.raises(ValueError, match="replay"):
        restarted.import_bundle(s["bundle"])
    assert not marker_path(s).exists()
    assert len(s["replay"].events()) == 1


def test_corrupt_marker_fails_closed(tmp_path):
    s = setup(tmp_path)
    marker_path(s).write_text('{"tampered":true}')
    with pytest.raises(ValueError, match="marker"):
        fresh(s).import_bundle(s["bundle"])
    assert marker_path(s).exists()


def test_marker_destination_mismatch_fails_closed(tmp_path):
    s = setup(tmp_path)
    s["importer"]._write_attempt(s["bundle"], 0, None)
    other = setup(tmp_path / "other")
    other["replay"] = s["replay"]
    with pytest.raises(ValueError, match="destinations"):
        fresh(other).import_bundle(other["bundle"])


def test_expired_bundle_does_not_create_attempt_marker(tmp_path):
    s = setup(tmp_path)
    expired = ProvenanceTransportImporter(
        graph=s["local_graph"], security_graph=s["local_security"],
        receipt_store=s["local_store"], receipt_verifier=s["verifier"],
        replay_ledger=s["replay"], policy=s["importer"].policy,
        now_fn=lambda: s["importer"].now_fn() + timedelta(seconds=400),
    )
    with pytest.raises(ValueError, match="expired"):
        expired.import_bundle(s["bundle"])
    assert not marker_path(s).exists()


@pytest.mark.parametrize("changes", [
    {"sender_id": "another-sender"},
    {"nonce": "another-nonce"},
    {"remote_glyph_id": "another-glyph"},
    {"prefix_count": 999, "prefix_head": "0" * 64},
    {"prefix_count": True},
    {"schema": True},
])
def test_terminal_entry_does_not_clear_inconsistent_marker(tmp_path, monkeypatch, changes):
    s = setup(tmp_path)
    original = s["replay"].append
    def committed_then_fault(**kwargs):
        original(**kwargs)
        raise RuntimeError("committed")
    monkeypatch.setattr(s["replay"], "append", committed_then_fault)
    with pytest.raises(RuntimeError):
        s["importer"].import_bundle(s["bundle"])
    path = marker_path(s)
    marker = json.loads(path.read_text())
    marker.update(changes)
    marker["digest"] = _digest({k: v for k, v in marker.items() if k != "digest"})
    path.write_text(json.dumps(marker))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="marker|uncertain"):
        fresh(s).import_bundle(s["bundle"])
    assert path.read_bytes() == before
    assert s["replay"].verify()[0] == 1
