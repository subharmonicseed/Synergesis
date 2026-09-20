from datetime import datetime, timezone
import math

import pytest

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_prediction import PredictionLedger, PredictionSettlement
from synergesis_prediction_curiosity import (
    PredictionCuriosityMonitor,
    PredictionCuriosityPolicy,
)
from synergesis_roam_attention import AttentionWeights, ResearchAgenda


def policy(**overrides):
    values = dict(
        min_observations=3,
        rolling_window=3,
        minimum_absolute_error=0.6,
        minimum_surprise_bits=1.5,
        rolling_brier_threshold=0.3,
        cooldown_records=2,
        surprise_scale_bits=4.0,
        default_domain="system-learning",
        default_expected_impact=0.7,
        domain_by_action={"file.write": "systems"},
        expected_impact_by_action={"file.write": 0.9},
    )
    values.update(overrides)
    return PredictionCuriosityPolicy(**values)


def setup(tmp_path, *, policy_value=None):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    ledger = PredictionLedger(tmp_path / "predictions.jsonl")
    agenda = ResearchAgenda(
        tmp_path / "agenda.jsonl",
        graph=graph,
        weights=AttentionWeights(1, 1, 1, 1),
    )
    monitor = PredictionCuriosityMonitor(
        graph=graph,
        prediction_ledger=ledger,
        agenda=agenda,
        policy=policy_value or policy(),
    )
    return graph, ledger, agenda, monitor


def settlement(graph, *, n, probability, observed, strategy="s"):
    outcome = 1.0 if observed else 0.0
    brier = (probability - outcome) ** 2
    absolute = abs(probability - outcome)
    surprise = -math.log2(
        max(probability if observed else 1.0 - probability, 1e-12)
    )
    prediction = graph.create(
        "hypothesis",
        actor="SYN-PREDICT",
        content={"kind": "action_prediction", "n": n},
    )
    verdict = graph.create(
        "decision",
        actor="SYN-REALITY",
        content={"kind": "reality_verdict", "n": n},
    )
    learning = graph.create(
        "learning",
        actor="SYN-PREDICT",
        content={"kind": "prediction_error", "n": n},
        derived_from=(prediction.glyph_id, verdict.glyph_id),
    )
    return PredictionSettlement(
        prediction_id=f"pred:{n}",
        proposal_id=f"proposal:{n}",
        action_type="file.write",
        strategy_key=strategy,
        probability_effect_success=probability,
        observed_effect=observed,
        status="scored",
        brier_score=brier,
        absolute_error=absolute,
        surprise_bits=surprise,
        reality_verdict_glyph_id=verdict.glyph_id,
        prediction_glyph_id=prediction.glyph_id,
        learning_glyph_id=learning.glyph_id,
        settled_at=datetime.now(timezone.utc).isoformat(),
    )


def append_and_observe(ledger, monitor, value):
    ledger.append(value)
    monitor.on_prediction_settlement(value)


def test_no_research_need_before_minimum_observations(tmp_path):
    graph, ledger, agenda, monitor = setup(tmp_path)
    for n in (1, 2):
        s = settlement(graph, n=n, probability=0.95, observed=False)
        append_and_observe(ledger, monitor, s)
    assert agenda.pending() == ()
    assert monitor.last_trigger is None


def test_large_prediction_surprise_creates_research_need(tmp_path):
    graph, ledger, agenda, monitor = setup(tmp_path)
    # Two accurate warm-up observations then a high-surprise miss.
    for n, p, observed in [
        (1, 0.8, True),
        (2, 0.8, True),
        (3, 0.95, False),
    ]:
        s = settlement(graph, n=n, probability=p, observed=observed)
        append_and_observe(ledger, monitor, s)

    pending = agenda.pending()
    assert len(pending) == 1
    need = pending[0].need
    assert need.domain == "systems"
    assert "file.write" in need.question
    assert need.measurements.expected_impact == pytest.approx(0.9)
    assert need.reason.startswith("prediction_surprise:")
    assert monitor.last_trigger.need_id == need.need_id


def test_research_need_keeps_prediction_and_reality_provenance(tmp_path):
    graph, ledger, agenda, monitor = setup(tmp_path)
    values = [
        settlement(graph, n=1, probability=0.8, observed=True),
        settlement(graph, n=2, probability=0.8, observed=True),
        settlement(graph, n=3, probability=0.99, observed=False),
    ]
    for value in values:
        append_and_observe(ledger, monitor, value)

    need = agenda.pending()[0].need
    need_glyph = graph.ledger.find_by_external_ref(
        need.need_id,
        glyph_type="goal",
    )[-1]
    upstream = graph.upstream(need_glyph.glyph_id, max_depth=4)
    ids = {g.glyph_id for g in upstream.glyphs}
    assert values[-1].learning_glyph_id in ids
    assert values[-1].reality_verdict_glyph_id in ids


def test_cooldown_suppresses_repeated_surprise_spam(tmp_path):
    graph, ledger, agenda, monitor = setup(
        tmp_path,
        policy_value=policy(cooldown_records=3),
    )
    for n in range(1, 5):
        s = settlement(graph, n=n, probability=0.95, observed=False)
        append_and_observe(ledger, monitor, s)
    # Trigger at n=3, n=4 is inside cooldown.
    triggers = [
        g for g in graph.ledger.glyphs()
        if g.glyph_type == "decision"
        and g.content.get("kind") == "prediction_curiosity_trigger"
    ]
    assert len(triggers) == 1


def test_trigger_can_recur_after_cooldown(tmp_path):
    graph, ledger, agenda, monitor = setup(
        tmp_path,
        policy_value=policy(cooldown_records=2),
    )
    for n in range(1, 7):
        s = settlement(graph, n=n, probability=0.95, observed=False)
        append_and_observe(ledger, monitor, s)
    triggers = [
        g for g in graph.ledger.glyphs()
        if g.glyph_type == "decision"
        and g.content.get("kind") == "prediction_curiosity_trigger"
    ]
    assert len(triggers) == 2
    assert triggers[-1].content["prediction_record_sequence"] == 6


def test_small_well_calibrated_errors_do_not_trigger(tmp_path):
    graph, ledger, agenda, monitor = setup(
        tmp_path,
        policy_value=policy(
            minimum_absolute_error=0.7,
            minimum_surprise_bits=3.0,
            rolling_brier_threshold=0.4,
        ),
    )
    for n in range(1, 6):
        s = settlement(graph, n=n, probability=0.8, observed=True)
        append_and_observe(ledger, monitor, s)
    assert agenda.pending() == ()


def test_regime_shift_becomes_staleness_signal(tmp_path):
    graph, ledger, agenda, monitor = setup(
        tmp_path,
        policy_value=policy(
            min_observations=6,
            rolling_window=3,
            cooldown_records=0,
        ),
    )
    # Previous window is all success; recent window becomes all failure.
    for n in range(1, 7):
        observed = n <= 3
        probability = 0.9
        s = settlement(
            graph,
            n=n,
            probability=probability,
            observed=observed,
        )
        append_and_observe(ledger, monitor, s)

    assert monitor.last_trigger is not None
    assert monitor.last_trigger.previous_success_rate == pytest.approx(1.0)
    assert monitor.last_trigger.recent_success_rate == pytest.approx(0.0)
    assert monitor.last_trigger.regime_shift == pytest.approx(1.0)


def test_invalid_curiosity_policy_is_rejected():
    with pytest.raises(ValueError):
        policy(min_observations=0)
    with pytest.raises(ValueError):
        policy(rolling_window=0)
    with pytest.raises(ValueError):
        policy(default_expected_impact=1.1)
    with pytest.raises(ValueError):
        policy(surprise_scale_bits=0)
