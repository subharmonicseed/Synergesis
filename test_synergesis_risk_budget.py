import pytest

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_risk_budget import (
    RiskBudgetLedger,
    RiskBudgetManager,
    RiskBudgetPolicy,
)


def manager(tmp_path, *, limit=1.0, single=1.0):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    ledger = RiskBudgetLedger(tmp_path / "budget.jsonl")
    budget = RiskBudgetManager(
        graph=graph,
        ledger=ledger,
        policy=RiskBudgetPolicy(
            budget_limit=limit,
            maximum_single_reservation=single,
        ),
    )
    return graph, ledger, budget


def reserve(budget, directive, amount=0.2):
    return budget.reserve(
        directive_id=directive,
        action_type="diagnostic.run",
        strategy_key="diagnose",
        intervention="repair",
        amount=amount,
    )


def test_reservation_counts_against_available_budget(tmp_path):
    _, _, budget = manager(tmp_path, limit=0.5)
    r = reserve(budget, "directive:1", 0.2)
    state = budget.state()
    assert state.consumed == pytest.approx(0)
    assert state.reserved == pytest.approx(0.2)
    assert state.available == pytest.approx(0.3)
    assert state.active_reservations == 1

    budget.consume(r, cycle_id="cycle:1", proposal_id="proposal:1")
    state = budget.state()
    assert state.consumed == pytest.approx(0.2)
    assert state.reserved == pytest.approx(0)
    assert state.available == pytest.approx(0.3)


def test_release_restores_unspent_capacity(tmp_path):
    _, _, budget = manager(tmp_path, limit=0.5)
    r = reserve(budget, "directive:1", 0.2)
    budget.release(r)
    state = budget.state()
    assert state.consumed == pytest.approx(0)
    assert state.reserved == pytest.approx(0)
    assert state.available == pytest.approx(0.5)


def test_multiple_reservations_cannot_overbook_budget(tmp_path):
    _, _, budget = manager(tmp_path, limit=0.5)
    reserve(budget, "directive:1", 0.3)
    with pytest.raises(ValueError, match="budget exhausted"):
        reserve(budget, "directive:2", 0.25)
    assert budget.state().reserved == pytest.approx(0.3)


def test_consumed_exposure_is_never_automatically_replenished(tmp_path):
    _, _, budget = manager(tmp_path, limit=0.5)
    r = reserve(budget, "directive:1", 0.3)
    budget.consume(r, cycle_id="cycle:1", proposal_id="proposal:1")
    assert budget.state().available == pytest.approx(0.2)

    with pytest.raises(ValueError, match="budget exhausted"):
        reserve(budget, "directive:2", 0.25)
    assert budget.state().consumed == pytest.approx(0.3)


def test_same_directive_cannot_create_second_budget_lifecycle(tmp_path):
    _, _, budget = manager(tmp_path)
    r = reserve(budget, "directive:1")
    budget.release(r)
    with pytest.raises(ValueError, match="already has"):
        reserve(budget, "directive:1")


def test_reservation_has_exactly_one_terminal_event(tmp_path):
    _, _, budget = manager(tmp_path)
    r = reserve(budget, "directive:1")
    budget.consume(r, cycle_id="cycle:1", proposal_id="proposal:1")
    with pytest.raises(ValueError, match="not active"):
        budget.release(r)


def test_maximum_single_reservation_is_hard_bound(tmp_path):
    _, _, budget = manager(tmp_path, limit=10, single=0.25)
    with pytest.raises(ValueError, match="single-exposure"):
        reserve(budget, "directive:1", 0.3)
    assert budget.ledger.events() == ()


def test_ledger_detects_tampering(tmp_path):
    _, ledger, budget = manager(tmp_path)
    reserve(budget, "directive:1", 0.2)
    raw = ledger.path.read_text(encoding="utf-8")
    ledger.path.write_text(
        raw.replace('"amount":0.2', '"amount":0.9'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="integrity failure"):
        ledger.verify()


def test_budget_glyphs_have_no_authorization_effect(tmp_path):
    graph, _, budget = manager(tmp_path, limit=0.1)
    with pytest.raises(ValueError, match="budget exhausted"):
        reserve(budget, "directive:1", 0.2)
    glyphs = [
        g for g in graph.ledger.glyphs()
        if g.content.get("kind") == "risk_budget_decision"
    ]
    assert glyphs
    assert glyphs[-1].content["authorization_effect"] == "none"


def test_policy_validation():
    with pytest.raises(ValueError):
        RiskBudgetPolicy(budget_limit=0)
    with pytest.raises(ValueError):
        RiskBudgetPolicy(
            budget_limit=1,
            maximum_single_reservation=0,
        )


def test_same_epoch_survives_restart_without_budget_reset(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    ledger_path = tmp_path / "budget.jsonl"

    first = RiskBudgetManager(
        graph=graph,
        ledger=RiskBudgetLedger(ledger_path),
        policy=RiskBudgetPolicy(
            budget_limit=0.5,
            epoch_id="epoch:alpha",
        ),
    )
    r = first.reserve(
        directive_id="directive:1",
        action_type="diagnostic.run",
        strategy_key="diagnose",
        intervention="repair",
        amount=0.3,
    )
    first.consume(r, cycle_id="cycle:1", proposal_id="proposal:1")
    assert first.state().consumed == pytest.approx(0.3)

    restarted = RiskBudgetManager(
        graph=graph,
        ledger=RiskBudgetLedger(ledger_path),
        policy=RiskBudgetPolicy(
            budget_limit=0.5,
            epoch_id="epoch:alpha",
        ),
    )
    state = restarted.state()
    assert state.epoch_id == "epoch:alpha"
    assert state.consumed == pytest.approx(0.3)
    assert state.available == pytest.approx(0.2)


def test_new_control_plane_epoch_opens_fresh_budget_without_erasing_history(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    ledger_path = tmp_path / "budget.jsonl"

    alpha = RiskBudgetManager(
        graph=graph,
        ledger=RiskBudgetLedger(ledger_path),
        policy=RiskBudgetPolicy(
            budget_limit=0.5,
            epoch_id="epoch:alpha",
        ),
    )
    r = alpha.reserve(
        directive_id="directive:1",
        action_type="diagnostic.run",
        strategy_key="diagnose",
        intervention="repair",
        amount=0.4,
    )
    alpha.consume(r, cycle_id="cycle:1", proposal_id="proposal:1")

    beta = RiskBudgetManager(
        graph=graph,
        ledger=RiskBudgetLedger(ledger_path),
        policy=RiskBudgetPolicy(
            budget_limit=0.5,
            epoch_id="epoch:beta",
        ),
    )
    beta_state = beta.state()
    assert beta_state.epoch_id == "epoch:beta"
    assert beta_state.consumed == pytest.approx(0)
    assert beta_state.available == pytest.approx(0.5)

    all_events = beta.ledger.events()
    assert len(all_events) == 2
    assert {event.epoch_id for event in all_events} == {"epoch:alpha"}

    rb = beta.reserve(
        directive_id="directive:2",
        action_type="diagnostic.run",
        strategy_key="diagnose",
        intervention="repair",
        amount=0.2,
    )
    beta.consume(rb, cycle_id="cycle:2", proposal_id="proposal:2")

    all_events = beta.ledger.events()
    assert {event.epoch_id for event in all_events} == {
        "epoch:alpha", "epoch:beta"
    }
    assert alpha.state().consumed == pytest.approx(0.4)
    assert beta.state().consumed == pytest.approx(0.2)


def test_epoch_id_is_mandatory_and_cannot_be_blank():
    with pytest.raises(ValueError, match="epoch_id"):
        RiskBudgetPolicy(
            budget_limit=1.0,
            epoch_id="",
        )
