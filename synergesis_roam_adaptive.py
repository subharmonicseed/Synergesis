"""Non-stationary research-method selection for SYN-ROAM.

The original ResearchMethodLearner uses all historical observations. That is
appropriate for a stationary environment but can starve a method after one bad
early trial even when the world later changes.

This learner adds:
- rolling-window utility estimates;
- bounded forced re-exploration of stale methods;
- auditable selection decisions in the Glyph Graph.

It changes strategy selection only. It cannot grant permissions, add sources,
or expand ROAM budgets.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Optional, Tuple

from synergesis_glyph_protocol import GlyphAuditGraph
from synergesis_roam import (
    MethodStats,
    ResearchMethod,
    ResearchMethodLearner,
    ResearchQuestion,
)


@dataclass(frozen=True)
class AdaptiveSelectionConfig:
    rolling_window_per_method: int
    max_selection_gap: int
    exploration_strength: float
    decay_half_life_events: float = 8.0

    def __post_init__(self):
        if self.rolling_window_per_method < 1:
            raise ValueError("rolling_window_per_method must be >= 1")
        if self.max_selection_gap < 1:
            raise ValueError("max_selection_gap must be >= 1")
        if (
            not math.isfinite(self.exploration_strength)
            or self.exploration_strength < 0
        ):
            raise ValueError("exploration_strength must be finite and >= 0")
        if (
            not math.isfinite(self.decay_half_life_events)
            or self.decay_half_life_events <= 0
        ):
            raise ValueError("decay_half_life_events must be finite and > 0")


@dataclass(frozen=True)
class AdaptiveMethodScore:
    method_id: str
    observations_total: int
    observations_window: int
    recent_mean_utility: Optional[float]
    selections_since_last_trial: Optional[int]
    exploration_bonus: Optional[float]
    score: Optional[float]


class AdaptiveResearchMethodLearner(ResearchMethodLearner):
    def __init__(
        self,
        *,
        ledger,
        config,
        adaptive_config: AdaptiveSelectionConfig,
        graph: Optional[GlyphAuditGraph] = None,
        actor: str = "SYN-ROAM",
    ):
        super().__init__(ledger=ledger, config=config)
        self.adaptive_config = adaptive_config
        self.graph = graph
        self.actor = actor

    def _global_outcome_events(self):
        return tuple(self.ledger.events())

    def _last_event_sequence(self, method_id: str) -> Optional[int]:
        last = None
        for event in self._global_outcome_events():
            if event["payload"]["method_id"] == method_id:
                last = int(event["sequence"])
        return last

    def _recent_events(self, method_id: str):
        events = [
            event
            for event in self._global_outcome_events()
            if event["payload"]["method_id"] == method_id
        ]
        return tuple(
            events[-self.adaptive_config.rolling_window_per_method:]
        )

    def _score_snapshot(
        self,
        candidates: Tuple[ResearchMethod, ...],
    ) -> Tuple[AdaptiveMethodScore, ...]:
        global_events = self._global_outcome_events()
        total_events = len(global_events)
        out = []

        for method in candidates:
            all_outcomes = self.ledger.outcomes(method_id=method.method_id)
            events = self._recent_events(method.method_id)
            last_seq = self._last_event_sequence(method.method_id)
            gap = None if last_seq is None else total_events - last_seq

            if not events:
                out.append(
                    AdaptiveMethodScore(
                        method_id=method.method_id,
                        observations_total=len(all_outcomes),
                        observations_window=0,
                        recent_mean_utility=None,
                        selections_since_last_trial=gap,
                        exploration_bonus=None,
                        score=None,
                    )
                )
                continue

            weighted_sum = 0.0
            total_weight = 0.0
            for event in events:
                age = max(0, total_events - int(event["sequence"]))
                weight = 0.5 ** (
                    age / self.adaptive_config.decay_half_life_events
                )
                weighted_sum += float(event["payload"]["utility"]) * weight
                total_weight += weight

            mean = weighted_sum / total_weight
            effective_n = max(total_weight, 1e-9)
            bonus = self.adaptive_config.exploration_strength * math.sqrt(
                math.log(max(total_events, 1) + 1.0) / effective_n
            )
            out.append(
                AdaptiveMethodScore(
                    method_id=method.method_id,
                    observations_total=len(all_outcomes),
                    observations_window=len(events),
                    recent_mean_utility=mean,
                    selections_since_last_trial=gap,
                    exploration_bonus=bonus,
                    score=mean + bonus,
                )
            )
        return tuple(out)

    def _audit_selection(
        self,
        *,
        question: ResearchQuestion,
        selected: ResearchMethod,
        scores: Tuple[AdaptiveMethodScore, ...],
        forced: bool,
        reason: str,
    ) -> None:
        if self.graph is None:
            return
        sequence = len(self.ledger.events()) + 1
        self.graph.create(
            "decision",
            actor=self.actor,
            content={
                "kind": "adaptive_research_method_selection",
                "question_id": question.question_id,
                "selected_method_id": selected.method_id,
                "forced_exploration": forced,
                "reason": reason,
                "rolling_window_per_method": (
                    self.adaptive_config.rolling_window_per_method
                ),
                "max_selection_gap": self.adaptive_config.max_selection_gap,
                "decay_half_life_events": self.adaptive_config.decay_half_life_events,
                "scores": [asdict(x) for x in scores],
            },
            external_refs=(
                f"method-selection:{question.question_id}:{sequence}",
            ),
        )

    def select(self, question: ResearchQuestion) -> ResearchMethod:
        candidates = self._eligible(question)
        if not candidates:
            raise ValueError("no eligible research method")

        scores = self._score_snapshot(candidates)

        # Cold start remains deterministic.
        unseen = [
            method
            for method in candidates
            if next(
                s for s in scores if s.method_id == method.method_id
            ).observations_total == 0
        ]
        if unseen:
            selected = sorted(unseen, key=lambda m: m.method_id)[0]
            self._audit_selection(
                question=question,
                selected=selected,
                scores=scores,
                forced=True,
                reason="cold_start",
            )
            return selected

        # Bounded forced re-exploration: a historically bad method cannot be
        # starved forever if the environment changes.
        stale = []
        for method in candidates:
            score = next(s for s in scores if s.method_id == method.method_id)
            gap = score.selections_since_last_trial or 0
            if gap >= self.adaptive_config.max_selection_gap:
                stale.append((gap, method.method_id, method))
        if stale:
            stale.sort(key=lambda x: (-x[0], x[1]))
            selected = stale[0][2]
            self._audit_selection(
                question=question,
                selected=selected,
                scores=scores,
                forced=True,
                reason="stale_method_retest",
            )
            return selected

        ranked = []
        for method in candidates:
            score = next(s for s in scores if s.method_id == method.method_id)
            assert score.score is not None
            ranked.append((score.score, method.method_id, method))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        selected = ranked[0][2]
        self._audit_selection(
            question=question,
            selected=selected,
            scores=scores,
            forced=False,
            reason="rolling_ucb",
        )
        return selected
