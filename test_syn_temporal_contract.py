from datetime import timedelta

import pytest

from test_synergesis_multisource_fusion import ingest
from test_synergesis_provisional_beliefs import BASE, fuse as fuse_belief, setup as belief_setup


@pytest.mark.parametrize("offset,reason", [
    (5, "future_observation"),
    (-20, "stale_observation"),
])
def test_fusion_optional_clock_marks_future_and_stale(tmp_path, offset, reason):
    from test_synergesis_multisource_fusion import setup

    graph, security, bus, agenda, ledger, fusion = setup(tmp_path)
    fusion.now_fn = lambda: BASE
    if reason == "stale_observation":
        fusion.policy = type(fusion.policy)(**{
            **fusion.policy.__dict__, "max_observation_age_seconds": 10,
        })
    capture = (BASE + timedelta(seconds=offset)).isoformat()
    decision = fusion.fuse(tuple(
        ingest(bus, f"sensor:{letter}", "on", captured_at=capture)
        for letter in "ab"
    ))
    assert decision.status == "unresolved"
    glyph = graph.ledger.get(decision.inference_glyph_id)
    assert glyph.content["reason"] == reason
    assert glyph.content["fusion_identity_version"] == 2
    assert len(glyph.content["configuration_fingerprint"]) == 64


def test_fusion_without_clock_keeps_historical_capture_behavior(tmp_path):
    from test_synergesis_multisource_fusion import setup

    graph, security, bus, agenda, ledger, fusion = setup(tmp_path)
    capture = (BASE + timedelta(days=365)).isoformat()
    decision = fusion.fuse(tuple(
        ingest(bus, f"sensor:{letter}", "on", captured_at=capture)
        for letter in "ab"
    ))
    assert decision.status == "resolved"


def test_clock_adjudication_instant_is_part_of_replay_identity(tmp_path):
    from test_synergesis_multisource_fusion import setup

    graph, security, bus, agenda, ledger, fusion = setup(tmp_path)
    records = tuple(ingest(bus, f"sensor:{letter}", "on", captured_at=BASE.isoformat())
                    for letter in "ab")
    clock = [BASE - timedelta(seconds=1)]
    fusion.now_fn = lambda: clock[0]
    future = fusion.fuse(records)
    assert future.status == "unresolved"
    clock[0] = BASE
    current = fusion.fuse(records)
    assert current.status == "resolved"
    assert current.fusion_id != future.fusion_id
    assert fusion.fuse(records).inference_glyph_id == current.inference_glyph_id


def test_fusion_identity_changes_with_policy_fingerprint(tmp_path):
    from test_synergesis_multisource_fusion import setup

    graph, security, bus, agenda, ledger, fusion = setup(tmp_path)
    records = tuple(ingest(bus, f"sensor:{letter}", "on", captured_at=BASE.isoformat())
                    for letter in "ab")
    first = fusion.fuse(records)
    original = fusion.policy
    fusion.policy = type(original)(**{
        **original.__dict__, "max_observation_age_seconds": 3600,
    })
    second = fusion.fuse(records)
    assert first.fusion_id != second.fusion_id
    a = graph.ledger.get(first.inference_glyph_id).content
    b = graph.ledger.get(second.inference_glyph_id).content
    assert a["configuration_fingerprint"] != b["configuration_fingerprint"]


def test_freshness_uses_oldest_capture_in_evidence_set(tmp_path):
    from test_synergesis_multisource_fusion import setup

    graph, security, bus, agenda, ledger, fusion = setup(tmp_path)
    fusion.policy = type(fusion.policy)(**{
        **fusion.policy.__dict__, "max_observation_age_seconds": 10,
    })
    fusion.now_fn = lambda: BASE
    records = (
        ingest(bus, "sensor:a", "on", captured_at=(BASE - timedelta(seconds=20)).isoformat()),
        ingest(bus, "sensor:b", "on", captured_at=BASE.isoformat()),
    )
    decision = fusion.fuse(records)
    assert decision.status == "unresolved"
    assert decision.reason == "stale_observation"


def test_expired_belief_no_longer_conflicts_with_new_claim(tmp_path):
    _, bus, fusion, bridge, clock = belief_setup(tmp_path)
    fuse_belief(bus, fusion, ("on", "on"), 0)
    clock[0] = BASE + timedelta(seconds=61)
    assert bridge.current("node:A").status == "expired"
    fuse_belief(bus, fusion, ("off", "off"), 60)
    current = bridge.current("node:A")
    assert current.status == "provisional"
    assert current.claim == "off"
    assert bridge.history("node:A")[-1].content["reason"] == "fusion_support_admitted"
