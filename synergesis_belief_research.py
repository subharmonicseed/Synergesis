"""Bounded research requests for suspended/expired provisional beliefs.

Scanning only queues work. The existing explicit ROAM tick is the sole research
entry point. Shared graph/agenda, trusted configuration and one writer assumed.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math

from synergesis_roam_attention import AttentionMeasurements, ResearchNeed


@dataclass(frozen=True)
class BeliefResearchPolicy:
    domain: str
    measurements: AttentionMeasurements
    cooldown_seconds: float = 300.0
    max_new_per_scan: int = 2
    max_pending: int = 8

    def __post_init__(self):
        if not isinstance(self.domain, str) or not self.domain.strip():
            raise ValueError('research domain required')
        if not isinstance(self.measurements, AttentionMeasurements):
            raise ValueError('explicit attention measurements required')
        if (isinstance(self.cooldown_seconds, bool) or not math.isfinite(self.cooldown_seconds)
                or self.cooldown_seconds < 0):
            raise ValueError('cooldown must be finite and nonnegative')
        for name in ('max_new_per_scan', 'max_pending'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError('research limits must be positive integers')


class ProvisionalBeliefResearch:
    actor = 'SYN-BELIEF-RESEARCH'

    def __init__(self, *, beliefs, agenda, policy, clock=None):
        if beliefs.graph is not agenda.graph:
            raise ValueError('beliefs and research agenda must share a graph')
        self.beliefs, self.agenda, self.policy = beliefs, agenda, policy
        self.graph = beliefs.graph
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _requests(self):
        return tuple(g for g in self.graph.ledger.glyphs()
                     if g.actor == self.actor and g.content.get('kind') == 'provisional_research_request')

    @staticmethod
    def _need(request):
        raw = dict(request.content['need'])
        raw['measurements'] = AttentionMeasurements(**raw['measurements'])
        raw['source_glyph_ids'] = tuple(raw['source_glyph_ids'])
        return ResearchNeed(**raw)

    def still_needed(self, need):
        matches = [g for g in self._requests() if g.content['need']['need_id'] == need.need_id]
        if not matches:
            return True  # Other producers own their research requests.
        c = matches[-1].content
        current = self.beliefs.current(c['subject'])
        return (current is not None and current.status in {'expired', 'suspended'}
                and current.revision_glyph_id == c['revision_glyph_id'])

    def scan_once(self):
        now = self.clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError('research clock must be timezone-aware')
        now = now.astimezone(timezone.utc)
        requests = self._requests()
        # Replay durable intents after an interruption between graph and agenda.
        for request in requests:
            self.agenda.add(self._need(request))
        owned_ids = {g.content['need']['need_id'] for g in requests}
        for state in self.agenda.pending():
            if state.need.need_id in owned_ids and not self.still_needed(state.need):
                self.agenda.cancel(state.need.need_id, reason='provisional belief recovered or was superseded')
        pending = self.agenda.pending()
        owned_pending = sum(s.need.need_id in owned_ids for s in pending)
        created = []
        current = sorted(self.beliefs.states(), key=lambda b: (b.observed_through, b.subject))
        for belief in current:
            if len(created) >= self.policy.max_new_per_scan or owned_pending >= self.policy.max_pending:
                break
            if belief.status not in {'expired', 'suspended'}:
                continue
            # Exactly one request per revision, including after completion/restart.
            if any(g.content['revision_glyph_id'] == belief.revision_glyph_id for g in requests):
                continue
            same_subject = [g for g in requests if g.content['subject'] == belief.subject]
            if same_subject:
                latest = max(datetime.fromisoformat(g.content['created_at']) for g in same_subject)
                if (now - latest).total_seconds() < self.policy.cooldown_seconds:
                    continue
            # Fusion may already have queued a conflict enquiry. Do not take ownership.
            fusion_ids = {e.target for e in self.graph.ledger.edges_from(belief.revision_glyph_id, relation='derived_from')
                          if self.graph.ledger.get(e.target).content.get('kind') == 'multisource_perception_fusion'}
            if any(fusion_ids.intersection(s.need.source_glyph_ids) for s in self.agenda.pending()):
                continue
            subject_literal = json.dumps(belief.subject, ensure_ascii=False)
            need = ResearchNeed.create(
                domain=self.policy.domain,
                question=(f'Investigate provisional {belief.observation_kind} for subject {subject_literal}: '
                          f'status={belief.status}. Seek fresh independent evidence and counter-evidence; '
                          'do not assume the previous claim is true.'),
                reason=f'Provisional belief requires review: {belief.reason}. No factual promotion authorized.',
                hypothesis=None,
                measurements=self.policy.measurements,
                source_glyph_ids=(belief.revision_glyph_id,))
            ref = 'belief-research:' + sha256(need.need_id.encode()).hexdigest()
            self.graph.create(
                'learning', actor=self.actor,
                content={'kind': 'provisional_research_request', 'subject': belief.subject,
                         'revision_glyph_id': belief.revision_glyph_id, 'trigger_status': belief.status,
                         'created_at': now.isoformat(), 'need': asdict(need),
                         'policy': asdict(self.policy), 'authorization_effect': 'none'},
                external_refs=(ref,), dedupe_external_ref=ref,
                derived_from=(belief.revision_glyph_id,))
            created.append(self.agenda.add(need))
            owned_pending += 1
        return tuple(created)
