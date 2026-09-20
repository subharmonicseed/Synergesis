from datetime import timedelta
from dataclasses import replace
import pytest
from synergesis_belief_research import BeliefResearchPolicy, ProvisionalBeliefResearch
from synergesis_roam_attention import AttentionMeasurements, RoamAttentionController, ResearchAgenda
from synergesis_provisional_beliefs import FusionProvisionalBeliefs
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from test_synergesis_provisional_beliefs import setup, fuse, BASE
from test_synergesis_multisource_fusion import ingest


def build(tmp_path, **overrides):
    core, bus, fusion, beliefs, clock = setup(tmp_path)
    policy = BeliefResearchPolicy('operations', AttentionMeasurements(0.8,0.5,0.8,0.5),
                                 **{'cooldown_seconds': 100, **overrides})
    bridge = ProvisionalBeliefResearch(beliefs=beliefs, agenda=fusion.agenda,
                                      policy=policy, clock=lambda:clock[0])
    return core, bus, fusion, beliefs, clock, bridge


def expire(bus, fusion, clock):
    fuse(bus, fusion)
    clock[0] = BASE + timedelta(seconds=61)


def test_expired_belief_queues_provenance_without_execution(tmp_path):
    core, bus, fusion, beliefs, clock, bridge = build(tmp_path)
    expire(bus, fusion, clock)
    states = bridge.scan_once()
    assert len(states) == 1 and states[0].status == 'pending'
    assert states[0].need.hypothesis is None
    assert states[0].need.source_glyph_ids == (beliefs.current('node:A').revision_glyph_id,)
    assert core.memory.count() == 0
    assert bridge.scan_once() == ()


def test_restart_preserves_deduplication_and_researched_not_requeued(tmp_path):
    core, bus, fusion, beliefs, clock, bridge = build(tmp_path)
    expire(bus, fusion, clock)
    first = bridge.scan_once()[0]
    fusion.agenda.mark_researched(first.need.need_id, 'session:test')
    graph = GlyphAuditGraph(GlyphLedger(tmp_path/'glyphs.jsonl'))
    agenda = ResearchAgenda(fusion.agenda.path, graph=graph, weights=fusion.agenda.weights)
    restored = ProvisionalBeliefResearch(
        beliefs=FusionProvisionalBeliefs(graph=graph, policy=beliefs.policy, clock=lambda:clock[0]),
        agenda=agenda, policy=bridge.policy, clock=lambda:clock[0])
    assert restored.scan_once() == ()
    assert agenda.get(first.need.need_id).status == 'researched'


def test_recovered_belief_cancels_pending_before_tick(tmp_path):
    core, bus, fusion, beliefs, clock, bridge = build(tmp_path)
    expire(bus, fusion, clock)
    need = bridge.scan_once()[0].need
    clock[0] = BASE + timedelta(seconds=63)
    fuse(bus, fusion, second=62)
    class NoResearch:
        def research_once(self, question):
            raise AssertionError('recovered belief must not launch research')
    controller = RoamAttentionController(agenda=fusion.agenda, roam=NoResearch())
    controller.add_tick_hook(bridge.scan_once)
    controller.add_need_guard(bridge.still_needed)
    assert controller.tick_once().status == 'idle'
    assert fusion.agenda.get(need.need_id).status == 'cancelled'


def test_last_moment_guard_cancels_selected_obsolete_need(tmp_path):
    core, bus, fusion, beliefs, clock, bridge = build(tmp_path)
    expire(bus, fusion, clock)
    need = bridge.scan_once()[0].need
    clock[0] = BASE + timedelta(seconds=63)
    fuse(bus, fusion, second=62)
    class NoResearch:
        def research_once(self, question): raise AssertionError('stale')
    controller=RoamAttentionController(agenda=fusion.agenda, roam=NoResearch())
    controller.add_need_guard(bridge.still_needed)
    assert controller.tick_once().status == 'cancelled'
    assert fusion.agenda.get(need.need_id).status == 'cancelled'


def test_cooldown_applies_across_new_revisions(tmp_path):
    core, bus, fusion, beliefs, clock, bridge = build(tmp_path)
    expire(bus, fusion, clock)
    first = bridge.scan_once()[0]
    clock[0] = BASE + timedelta(seconds=63)
    fuse(bus, fusion, second=62)
    bridge.scan_once()
    clock[0] = BASE + timedelta(seconds=123)
    assert bridge.scan_once() == ()
    clock[0] = BASE + timedelta(seconds=162)
    second = bridge.scan_once()[0]
    assert first.need.need_id != second.need.need_id


def test_fusion_conflict_need_is_not_duplicated_or_cancelled(tmp_path):
    core, bus, fusion, beliefs, clock, bridge = build(tmp_path)
    result = fuse(bus, fusion, ('on','off'))
    assert result.research_need_id
    assert bridge.scan_once() == ()
    assert fusion.agenda.get(result.research_need_id).status == 'pending'


def test_rejected_single_source_creates_no_belief_research(tmp_path):
    core, bus, fusion, beliefs, clock, bridge = build(tmp_path)
    fuse(bus, fusion, ('on',))
    assert bridge.scan_once() == ()


def test_durable_intent_recovers_after_agenda_write_failure(tmp_path, monkeypatch):
    core, bus, fusion, beliefs, clock, bridge = build(tmp_path)
    expire(bus, fusion, clock)
    add = fusion.agenda.add
    def fail(need): raise OSError('interrupted write')
    monkeypatch.setattr(fusion.agenda,'add',fail)
    with pytest.raises(OSError): bridge.scan_once()
    monkeypatch.setattr(fusion.agenda,'add',add)
    assert bridge.scan_once() == ()
    assert len(fusion.agenda.pending()) == 1


@pytest.mark.parametrize('field,value', [('max_new_per_scan',0),('max_pending',True),
                                       ('cooldown_seconds',float('nan')),('domain','')])
def test_invalid_policy_rejected(field,value):
    policy=BeliefResearchPolicy('ops',AttentionMeasurements(0.5,0.5,0.5,0.5))
    with pytest.raises(ValueError): replace(policy,**{field:value})


def test_scan_and_pending_limits(tmp_path):
    core,bus,fusion,beliefs,clock,bridge=build(tmp_path,max_new_per_scan=1,max_pending=2)
    from synergesis_perception_bus import RawPercept
    for subject in ('A','B','C'):
        records=[bus.ingest(RawPercept(source_id=source,modality='state',
            payload={'device':subject,'state':'on'},captured_at=BASE.isoformat(),
            external_id=subject+source)) for source in ('sensor:a','sensor:b')]
        fusion.fuse(records)
    clock[0]=BASE+timedelta(seconds=61)
    assert len(bridge.scan_once())==1
    assert len(bridge.scan_once())==1
    assert bridge.scan_once()==()
    assert len(fusion.agenda.pending())==2


def test_active_belief_creates_no_research(tmp_path):
    core,bus,fusion,beliefs,clock,bridge=build(tmp_path)
    fuse(bus,fusion)
    assert bridge.scan_once()==()
