from dataclasses import replace
from datetime import datetime, timedelta, timezone
import pytest

from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_provisional_beliefs import FusionProvisionalBeliefs, ProvisionalBeliefPolicy
from test_synergesis_multisource_fusion import setup as fusion_setup, ingest

BASE = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)


def setup(tmp_path, **policy_overrides):
    graph, security, bus, agenda, ledger, fusion = fusion_setup(tmp_path)
    core = GlyphAuditedCognitiveCore(tmp_path / 'memory.jsonl', graph=graph)
    fusion.aura = GlyphAuditedAura(core, graph=graph)
    clock = [BASE + timedelta(seconds=1)]
    policy = ProvisionalBeliefPolicy('device_state', **{'ttl_seconds': 60, **policy_overrides})
    bridge = FusionProvisionalBeliefs(graph=graph, policy=policy, clock=lambda: clock[0])
    fusion.add_decision_sink(bridge)
    core.world.provisional_beliefs = bridge
    return core, bus, fusion, bridge, clock


def fuse(bus, fusion, claims=('on', 'on'), second=0):
    captured = (BASE + timedelta(seconds=second)).isoformat()
    return fusion.fuse(tuple(ingest(bus, f'sensor:{letter}', claim, captured_at=captured)
                             for letter, claim in zip('abc', claims)))


def test_fusion_becomes_provisional_world_snapshot_not_fact(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    decision = fuse(bus, fusion)
    current = bridge.current('node:A')
    assert current.status == 'provisional' and current.claim == 'on'
    assert current.confidence is None and current.winner_support == pytest.approx(1.6)
    assert core.memory.count() == 0
    snapshot = core.world.snapshot()
    assert snapshot.facts == () and snapshot.provisional_beliefs == (current,)
    event = bridge.history('node:A')[-1]
    assert event.content['authorization_effect'] == 'none'
    parents = {e.target for e in fusion.graph.ledger.edges_from(event.glyph_id)}
    assert {decision.inference_glyph_id, decision.evidence_glyph_id} <= parents


def test_expiration_and_replay_do_not_renew(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    decision = fuse(bus, fusion)
    clock[0] = BASE + timedelta(seconds=60)
    assert bridge.current('node:A').status == 'expired'
    assert core.world.snapshot().provisional_beliefs == ()
    bridge.on_fusion(decision)
    assert len(bridge.history('node:A')) == 1
    assert bridge.current('node:A').status == 'expired'


def test_newer_contradiction_suspends_until_new_support(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    fuse(bus, fusion)
    clock[0] = BASE + timedelta(seconds=3)
    fuse(bus, fusion, ('off', 'off'), 2)
    assert bridge.current('node:A').status == 'suspended'
    assert core.world.snapshot().provisional_beliefs == ()
    clock[0] = BASE + timedelta(seconds=5)
    fuse(bus, fusion, ('off', 'off'), 4)
    assert bridge.current('node:A').status == 'provisional'
    assert bridge.current('node:A').claim == 'off'
    assert len(bridge.history('node:A')) == 3


def test_unresolved_new_fusion_suspends_existing(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    fuse(bus, fusion)
    clock[0] = BASE + timedelta(seconds=3)
    fuse(bus, fusion, ('on', 'off'), 2)
    assert bridge.current('node:A').status == 'suspended'


def test_older_evidence_never_replaces_newer_head(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    clock[0] = BASE + timedelta(seconds=11)
    fuse(bus, fusion, second=10)
    previous = bridge.current('node:A')
    fuse(bus, fusion, ('off', 'off'), 2)
    assert bridge.current('node:A') == previous
    assert bridge.history('node:A')[-1].content['applied'] is False


def test_same_timestamp_conflict_cannot_be_resolved_by_arrival_order(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    fuse(bus, fusion)
    fuse(bus, fusion, ('off', 'off'))
    assert bridge.current('node:A').status == 'suspended'
    fuse(bus, fusion, ('on', 'on', 'on'))
    assert bridge.current('node:A').status == 'suspended'


@pytest.mark.parametrize('second,reason', [(-60, 'stale_observation'), (5, 'future_observation')])
def test_invalid_observation_age_rejected(tmp_path, second, reason):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    fuse(bus, fusion, second=second)
    assert bridge.current('node:A') is None
    assert bridge.history('node:A')[-1].content['reason'] == reason


def test_restart_restores_expiring_view(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    fuse(bus, fusion)
    reloaded = FusionProvisionalBeliefs(
        graph=GlyphAuditGraph(GlyphLedger(tmp_path / 'glyphs.jsonl')),
        policy=bridge.policy, clock=lambda: BASE + timedelta(seconds=2))
    assert reloaded.current('node:A') == bridge.current('node:A')
    reloaded.clock = lambda: BASE + timedelta(seconds=61)
    assert reloaded.active() == ()


@pytest.mark.parametrize('field,value', [('selected_claim', 'forged'), ('winner_support', 999.0),
                                        ('subject', 'other'), ('evidence_id', 'fake')])
def test_forged_decision_rejected(tmp_path, field, value):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    decision = fuse(bus, fusion)
    with pytest.raises(ValueError):
        bridge.on_fusion(replace(decision, **{field: value}))
    assert len(bridge.history('node:A')) == 1


def test_extra_threshold_can_refuse_resolved_fusion(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path, minimum_independent_groups=3)
    assert fuse(bus, fusion).status == 'resolved'
    assert bridge.active() == ()


@pytest.mark.parametrize('ttl', [0, -1, float('inf'), float('nan'), True])
def test_invalid_ttl_rejected(ttl):
    with pytest.raises(ValueError):
        ProvisionalBeliefPolicy('state', ttl)


def test_oldest_percept_controls_expiration(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    clock[0] = BASE + timedelta(seconds=5)
    records = (ingest(bus, 'sensor:a', 'on', captured_at=BASE.isoformat()),
               ingest(bus, 'sensor:b', 'on', captured_at=(BASE+timedelta(seconds=4)).isoformat()))
    fusion.fuse(records)
    assert bridge.current('node:A').expires_at == (BASE+timedelta(seconds=60)).isoformat()


def test_single_source_cannot_suspend_independently_supported_belief(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    fuse(bus, fusion)
    prior = bridge.current('node:A')
    clock[0] = BASE + timedelta(seconds=3)
    fuse(bus, fusion, ('off',), 2)
    assert bridge.current('node:A') == prior
    assert bridge.history('node:A')[-1].content['reason'] == 'insufficient_eligible_independent_groups'


def test_repeated_claim_does_not_accumulate_probability(tmp_path):
    core, bus, fusion, bridge, clock = setup(tmp_path)
    for second in (0, 2, 4):
        clock[0] = BASE + timedelta(seconds=second+1)
        fuse(bus, fusion, second=second)
        belief = bridge.current('node:A')
        assert belief.confidence is None and belief.winner_support == pytest.approx(1.6)
    assert len(bridge.active()) == 1
