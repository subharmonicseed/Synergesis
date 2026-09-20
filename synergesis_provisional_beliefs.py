"""Expiring, provisional World Model beliefs from audited perception fusion.

No Fact insertion, probability invention, authority elevation or action dispatch.
The shared Glyph ledger is the durable source; one writer is assumed.
"""
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math


def _time(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('timestamps must have a timezone')
    return result.astimezone(timezone.utc)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class ProvisionalBeliefPolicy:
    observation_kind: str
    ttl_seconds: float
    minimum_independent_groups: int = 2
    minimum_support: float = 1.0
    minimum_margin: float = 0.2

    def __post_init__(self):
        if not isinstance(self.observation_kind, str) or not self.observation_kind.strip():
            raise ValueError('observation kind required')
        if type(self.minimum_independent_groups) is not int or self.minimum_independent_groups < 2:
            raise ValueError('at least two independent groups required')
        for name in ('ttl_seconds', 'minimum_support', 'minimum_margin'):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(name + ' must be finite and positive')

    @property
    def policy_id(self):
        return sha256(_canonical(asdict(self)).encode()).hexdigest()


@dataclass(frozen=True)
class ProvisionalBelief:
    subject: str
    observation_kind: str
    claim: str | None
    status: str
    confidence: None
    winner_support: float | None
    reason: str
    observed_from: str
    observed_through: str
    expires_at: str
    fusion_id: str
    evidence_id: str
    revision_glyph_id: str


class FusionProvisionalBeliefs:
    actor = 'SYN-PROVISIONAL-BELIEFS'

    def __init__(self, *, graph, policy, clock=None):
        self.graph, self.policy = graph, policy
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self):
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError('clock must return timezone-aware datetime')
        return value.astimezone(timezone.utc)

    def _events(self):
        return tuple(g for g in self.graph.ledger.glyphs()
                     if g.actor == self.actor
                     and g.content.get('kind') == 'provisional_belief_revision'
                     and g.content.get('policy_id') == self.policy.policy_id)

    def history(self, subject):
        return tuple(g for g in self._events() if g.content['subject'] == subject)

    def _head(self, subject):
        applied = [g for g in self.history(subject) if g.content['applied']]
        return applied[-1] if applied else None

    def current(self, subject):
        head = self._head(subject)
        if head is None:
            return None
        c = head.content
        belief = ProvisionalBelief(
            subject=c['subject'], observation_kind=c['observation_kind'],
            claim=c['claim'], status=c['status'], confidence=None,
            winner_support=c['winner_support'], reason=c['reason'],
            observed_from=c['observed_from'], observed_through=c['observed_through'],
            expires_at=c['expires_at'], fusion_id=c['fusion_id'],
            evidence_id=c['evidence_id'], revision_glyph_id=head.glyph_id)
        if belief.status == 'provisional' and self._now() >= _time(belief.expires_at):
            return replace(belief, status='expired', reason='observation_ttl_elapsed')
        return belief

    def states(self):
        subjects = sorted({g.content['subject'] for g in self._events()})
        return tuple(b for subject in subjects
                     if (b := self.current(subject)) is not None)

    def active(self):
        return tuple(b for b in self.states() if b.status == 'provisional')

    def on_fusion(self, decision):
        g = self.graph.ledger.get(decision.inference_glyph_id)
        c = g.content
        if (g.glyph_type != 'inference' or g.actor != 'SYN-MULTISOURCE-FUSION'
                or c.get('kind') != 'multisource_perception_fusion'):
            raise ValueError('audited fusion inference required')
        if c.get('observation_kind') != self.policy.observation_kind:
            raise ValueError('fusion outside configured observation kind')
        for name, value in asdict(decision).items():
            if name in c and _canonical(c[name]) != _canonical(value):
                raise ValueError('fusion decision differs from its glyph')
        if not decision.evidence_id or not decision.evidence_glyph_id:
            raise ValueError('fusion AURA evidence required')
        evidence = self.graph.ledger.get(decision.evidence_glyph_id)
        if evidence.glyph_type != 'evidence' or decision.evidence_id not in evidence.external_refs:
            raise ValueError('fusion evidence identity mismatch')
        if not any(e.target == g.glyph_id and e.relation == 'derived_from'
                   for e in self.graph.ledger.edges_from(evidence.glyph_id)):
            raise ValueError('fusion evidence provenance missing')
        parents = [self.graph.ledger.get(e.target)
                   for e in self.graph.ledger.edges_from(g.glyph_id, relation='derived_from')]
        if not parents or any(p.content.get('kind') != 'normalized_perception' for p in parents):
            raise ValueError('fusion perception provenance missing')
        times = [_time(p.content['captured_at']) for p in parents]
        earliest, latest, now = min(times), max(times), self._now()
        expires = earliest + timedelta(seconds=self.policy.ttl_seconds)
        ref = 'provisional:' + self.policy.policy_id + ':' + decision.fusion_id
        existing = self.graph.ledger.find_by_external_ref(ref)
        if existing:
            return existing[-1]  # Replay never renews TTL or changes the current head.
        previous = self._head(decision.subject)
        status, reason, applied = 'provisional', 'fusion_support_admitted', True
        claim = decision.selected_claim
        eligible_groups = {item.independence_group for item in decision.source_contributions if item.eligible}
        if len(eligible_groups) < self.policy.minimum_independent_groups:
            status, reason, applied = 'rejected', 'insufficient_eligible_independent_groups', False
        elif latest > now:
            status, reason, applied = 'rejected', 'future_observation', False
        elif expires <= now:
            status, reason, applied = 'rejected', 'stale_observation', False
        elif previous and earliest < _time(previous.content['observed_through']):
            status, reason, applied = 'rejected', 'overlapping_or_older_observation', False
        elif previous and earliest == _time(previous.content['observed_through']):
            if previous.content['status'] != 'provisional' or claim != previous.content['claim']:
                status, reason, claim = 'suspended', 'same_time_conflict', None
        if applied and status == 'provisional':
            supported = (decision.status == 'resolved'
                         and decision.independent_groups_supporting_winner >= self.policy.minimum_independent_groups
                         and decision.winner_support is not None
                         and decision.winner_support >= self.policy.minimum_support
                         and decision.support_margin is not None
                         and decision.support_margin >= self.policy.minimum_margin)
            if not supported:
                status, reason, claim = 'suspended', 'insufficient_or_conflicting_support', None
            elif previous and previous.content['status'] == 'provisional' and previous.content['claim'] != claim:
                status, reason, claim = 'suspended', 'newer_fusion_contradicts_belief', None
        if not applied:
            claim = None
        return self.graph.create(
            'hypothesis', actor=self.actor,
            content={'kind': 'provisional_belief_revision', 'policy_id': self.policy.policy_id,
                     'subject': decision.subject, 'observation_kind': decision.observation_kind,
                     'claim': claim, 'status': status, 'reason': reason, 'applied': applied,
                     'confidence': None, 'winner_support': decision.winner_support,
                     'support_semantics': 'weighted_independent_support_not_truth_probability',
                     'authorization_effect': 'none', 'runtime_local': False,
                     'observed_from': earliest.isoformat(), 'observed_through': latest.isoformat(),
                     'expires_at': expires.isoformat(), 'recorded_at': now.isoformat(),
                     'fusion_id': decision.fusion_id, 'evidence_id': decision.evidence_id,
                     'supersedes': previous.glyph_id if applied and previous else None},
            external_refs=(ref,), dedupe_external_ref=ref,
            derived_from=(g.glyph_id, evidence.glyph_id, *((previous.glyph_id,) if previous else ())))
