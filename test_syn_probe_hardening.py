import sqlite3
import time
import hashlib
import os

import pytest

from synergesis_aegis import AegisSecurityGraph
from synergesis_agent_loop_v2 import ActionResult
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
import synergesis_reality
from synergesis_reality import (
    FileStateProbe, FunctionRealityProbe, RealityAssertion,
    RealityObservation, RealityProbeBinding, RealityProfile, RealityVerifier,
)
from synergesis_reality_state import SQLiteProbePolicy, SQLiteStateProbe


def test_file_probe_refuses_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "secret"
    outside.write_text("secret")
    (root / "link").symlink_to(outside)
    probe = FileStateProbe(observer_id="fs", allowed_root=root,
                           path_parameter="path", max_hash_bytes=100)
    with pytest.raises(ValueError, match="refuses symlinks"):
        probe.observe(action_type="read", resource="r", parameters={"path": "link"})


def test_file_probe_rejects_in_root_symlink_and_traversal(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "real").write_text("inside")
    (root / "alias").symlink_to(root / "real")
    probe = FileStateProbe(observer_id="fs", allowed_root=root,
                           path_parameter="path", max_hash_bytes=100)
    with pytest.raises(ValueError, match="refuses symlinks"):
        probe.observe(action_type="read", resource="r", parameters={"path": "alias"})
    with pytest.raises(ValueError, match="escapes allowed_root"):
        probe.observe(action_type="read", resource="r", parameters={"path": "../root/real"})


def test_file_probe_reads_opened_inode_if_path_is_replaced(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    target = root / "target"
    target.write_text("original")
    probe = FileStateProbe(observer_id="fs", allowed_root=root,
                           path_parameter="path", max_hash_bytes=100)
    real_open = os.open
    replaced = False

    def replace_after_open(path, flags, *args, **kwargs):
        nonlocal replaced
        fd = real_open(path, flags, *args, **kwargs)
        if path == "target" and kwargs.get("dir_fd") is not None and not replaced:
            replaced = True
            target.unlink()
            target.write_text("replacement")
        return fd

    monkeypatch.setattr(synergesis_reality.os, "open", replace_after_open)
    result = probe.observe(action_type="read", resource="r", parameters={"path": "target"})[0]
    assert result.facts["sha256"] == hashlib.sha256(b"original").hexdigest()


def test_sqlite_select_timeout_reports_unknown_and_closes_connection(tmp_path):
    root = tmp_path / "db"
    root.mkdir()
    db = root / "state.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE t(v INTEGER)")
        conn.executemany("INSERT INTO t VALUES (?)", ((i,) for i in range(200)))
    probe = SQLiteStateProbe(observer_id="sql", policy=SQLiteProbePolicy(
        database_path=db, allowed_root=root,
        select_sql="SELECT count(*) AS value FROM t a, t b, t c, t d",
        bind_parameter_keys=(), result_column="value", query_timeout_seconds=0.01,
    ))
    observed = probe.observe(action_type="read", resource="r", parameters={})[0]
    assert observed.facts["known"] is False
    assert observed.facts["unknown_reason"] == "query_timeout"
    # A separate connection/probe remains usable after SQLite interrupts the SELECT.
    fast = SQLiteStateProbe(observer_id="sql", policy=SQLiteProbePolicy(
        database_path=db, allowed_root=root, select_sql="SELECT count(*) AS value FROM t",
        bind_parameter_keys=(), result_column="value"))
    assert fast.observe(action_type="read", resource="r", parameters={})[0].facts["value"] == 200


@pytest.mark.parametrize("timeout", [float("inf"), float("nan"), float("-inf")])
def test_sqlite_policy_rejects_nonfinite_timeout(tmp_path, timeout):
    with pytest.raises(ValueError, match="finite"):
        SQLiteProbePolicy(database_path=tmp_path / "x.db", allowed_root=tmp_path,
            select_sql="SELECT 1 AS value", bind_parameter_keys=(),
            result_column="value", query_timeout_seconds=timeout)


def test_event_id_conflict_rejected_and_exact_replay_accepted(tmp_path):
    current = {"value": 1}
    def observe(action_type, resource, parameters):
        return (RealityObservation.create(observer_id="runtime", channel="fixture",
            resource=resource, facts={"value": current["value"]}, observed_at="fixed",
            event_id="event:fixed"),)
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "ledger.jsonl"))
    security = AegisSecurityGraph(graph)
    verifier = RealityVerifier(graph=graph, security_graph=security,
        probe_bindings=(RealityProbeBinding("runtime", "runtime_attested",
            FunctionRealityProbe(observer_id="runtime", callback=observe)),),
        profiles=(RealityProfile("act", ("runtime",),
            (RealityAssertion("runtime", "value", "eq", 1),)),))
    from synergesis_agent_loop_v2 import ActionProposal
    def verify():
        p = ActionProposal.create("act", {}, rationale="test", expected_outcome="test", strategy_key="test")
        action = graph.create("action", actor="test", content={"action_type": "act", "parameters": {}}, external_refs=(p.proposal_id,))
        return verifier.verify(proposal=p, action_glyph_id=action.glyph_id,
            resource="r", raw_result=ActionResult("act", True, {}))
    verify()
    verify()
    current["value"] = 2
    with pytest.raises(ValueError, match="event_id conflicts"):
        verify()
