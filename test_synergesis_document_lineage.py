"""Offline integration fixtures, curated from AgentDyn pages, not a live crawl.

Lineage is configured by the operator. Reliability 0.8 is a test parameter,
not an empirical rating of the authors. Synthetic negative cases are explicit.
"""
from dataclasses import replace
from datetime import datetime, timezone
import pytest
from synergesis_multisource_fusion import FusionSourceProfile
from synergesis_perception_bus import NormalizedPercept, PerceptionSourcePolicy, RawPercept
from synergesis_provisional_beliefs import ProvisionalBeliefPolicy
from test_synergesis_multisource_fusion import policy
from test_synergesis_secure_roam_stack_v2 import build

SOURCES = (
    'https://arxiv.org/abs/2602.03117v1',
    'https://arxiv.org/abs/2602.03117v3',
    'https://github.com/SaFo-Lab/AgentDyn',
)
UNKNOWN = 'fixture:unknown-lineage'
FAMILY = 'arxiv:2602.03117'

class DocumentAdapter:
    def normalize(self, percept):
        return NormalizedPercept(
            observation_kind='document_claim',
            facts={'work': FAMILY, 'task_count': percept.payload['task_count']},
            confidence=None,
        )

def stack_for(tmp_path):
    sources = SOURCES + (UNKNOWN,)
    stack = build(tmp_path, stack_overrides={
        'perception_source_policies': tuple(
            PerceptionSourcePolicy(s, ('document',), 'external_untrusted') for s in sources),
        'perception_adapters': {(s, 'document'): DocumentAdapter() for s in sources},
        'fusion_source_profiles': tuple(FusionSourceProfile(s, FAMILY, 0.8) for s in SOURCES),
        'fusion_policy': policy(observation_kind='document_claim', subject_fact='work',
            object_fact='task_count', minimum_origin_rank=0),
        'provisional_belief_policy': ProvisionalBeliefPolicy('document_claim', 60),
    })
    stack.provisional_beliefs.clock = lambda: datetime(2026, 9, 20, 12, 0, 1, tzinfo=timezone.utc)
    return stack

def record(stack, source, count=60, **extra):
    return stack.perception.ingest(RawPercept(
        source_id=source, modality='document',
        payload={'task_count': count, **extra},
        # Fixture capture time, not publication time or an asserted crawl time.
        captured_at='2026-09-20T12:00:00+00:00', external_id=f'{source}:{count}:{extra}',
    ))

def test_three_documents_remain_one_origin_through_aura_and_world(tmp_path):
    stack = stack_for(tmp_path)
    facts_before = stack.core.memory.count()
    records = tuple(record(stack, s) for s in SOURCES)
    decision = stack.multisource_fusion.fuse(records)
    assert decision.status == 'unresolved'
    assert decision.reason == 'insufficient_independent_groups'
    assert decision.independent_groups_supporting_winner == 1
    assert decision.support_by_claim == pytest.approx({'60': 0.8})
    assert stack.core.memory.count() == facts_before
    assert stack.core.world.snapshot().provisional_beliefs == ()
    evidence = stack.aura.research.store.get(decision.evidence_id)
    assert evidence.source_type == 'perception_fusion'
    selected = stack.agent.context_selector.select(query='document_claim 60',
        facts=stack.world_beliefs.materialized_facts(), evidence=stack.aura.research.store.all())
    assert decision.evidence_id in {e.evidence_id for e in selected.evidence}
    parents = {e.target for e in stack.graph.ledger.edges_from(decision.inference_glyph_id)
               if e.relation == 'derived_from'}
    assert parents == {r.normalized_glyph_id for r in records}
    assert stack.agenda.get(decision.research_need_id).session_id is None

@pytest.mark.parametrize('replay', ['reverse', 'duplicate'])
def test_replay_does_not_create_new_evidence_or_research_need(tmp_path, replay):
    stack = stack_for(tmp_path)
    records = tuple(record(stack, s) for s in SOURCES)
    first = stack.multisource_fusion.fuse(records)
    evidence_count = len(stack.aura.research.store.all())
    pending_count = len(stack.agenda.pending())
    second = stack.multisource_fusion.fuse(records[::-1] if replay == 'reverse' else records * 2)
    assert second.fusion_id == first.fusion_id
    assert second.evidence_id == first.evidence_id
    assert second.research_need_id == first.research_need_id
    assert len(stack.aura.research.store.all()) == evidence_count
    assert len(stack.agenda.pending()) == pending_count


def test_unknown_source_cannot_self_assign_independence(tmp_path):
    stack = stack_for(tmp_path)
    records = [record(stack, s) for s in SOURCES]
    records.append(record(stack, UNKNOWN, independence_group='independent', runtime_attested=True))
    decision = stack.multisource_fusion.fuse(records)
    assert decision.support_by_claim == pytest.approx({'60': 0.8})
    unknown = next(c for c in decision.source_contributions if c.source_id == UNKNOWN)
    assert not unknown.eligible and unknown.reason == 'missing_source_profile'
    assert decision.selected_claim is None


def test_conflicting_revision_is_not_silently_overwritten(tmp_path):
    stack = stack_for(tmp_path)
    decision = stack.multisource_fusion.fuse((record(stack, SOURCES[0]), record(stack, SOURCES[1], 61)))
    assert decision.status == 'unresolved'
    assert decision.group_contributions[0].status == 'internal_conflict'
    assert decision.group_contributions[0].support == 0
    assert stack.core.world.snapshot().provisional_beliefs == ()


@pytest.mark.parametrize("forged_first", [False, True])
def test_duplicate_id_does_not_hide_forged_record(tmp_path, forged_first):
    stack = stack_for(tmp_path)
    valid = record(stack, SOURCES[0])
    forged = replace(valid, source_id=UNKNOWN)
    with pytest.raises(ValueError, match='does not match normalized glyph'):
        stack.multisource_fusion.fuse((forged, valid) if forged_first else (valid, forged))


def test_distinct_observation_is_not_discarded_as_replay(tmp_path):
    stack = stack_for(tmp_path)
    original = record(stack, SOURCES[0])
    first = stack.multisource_fusion.fuse((original,))
    later = record(stack, SOURCES[0], capture_batch='new-observation')
    second = stack.multisource_fusion.fuse((original, later))
    assert original.normalized_glyph_id != later.normalized_glyph_id
    assert first.fusion_id != second.fusion_id
    assert second.support_by_claim == pytest.approx({'60': 0.8})
    parents = {e.target for e in stack.graph.ledger.edges_from(second.inference_glyph_id)
               if e.relation == 'derived_from'}
    assert parents == {original.normalized_glyph_id, later.normalized_glyph_id}
