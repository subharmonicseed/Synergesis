"""The risk budget and an independent audit writer share the same graph."""
import multiprocessing as mp

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_risk_budget import RiskBudgetLedger, RiskBudgetManager, RiskBudgetPolicy


def _worker(root, role, start, output):
    try:
        graph = GlyphAuditGraph(GlyphLedger(root / "graph.jsonl"))
        manager = RiskBudgetManager(
            graph=graph, ledger=RiskBudgetLedger(root / "budget.jsonl"),
            policy=RiskBudgetPolicy(budget_limit=1.0),
        )
        start.wait(timeout=10)
        if role == "audit":
            for i in range(8):
                graph.create("observation", actor="independent", content={"index": i})
            output.put("audited")
        else:
            try:
                manager.reserve(directive_id=role, action_type="diagnostic.run",
                                strategy_key="s", intervention="i", amount=0.6)
            except ValueError as exc:
                if "budget exhausted" not in str(exc):
                    raise
                output.put("blocked")
            else:
                output.put("reserved")
    except BaseException as exc:
        output.put(repr(exc))


def test_budget_and_independent_audit_writer_preserve_both_chains(tmp_path):
    ctx = mp.get_context("spawn")
    barrier, output = ctx.Barrier(3), ctx.Queue()
    workers = [ctx.Process(target=_worker, args=(tmp_path, role, barrier, output))
               for role in ("first", "second", "audit")]
    try:
        for worker in workers:
            worker.start()
        results = [output.get(timeout=20) for _ in workers]
        for worker in workers:
            worker.join(10)
            assert worker.exitcode == 0
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(10)
    assert sorted(results) == ["audited", "blocked", "reserved"]
    assert RiskBudgetLedger(tmp_path / "budget.jsonl").verify()[0] == 1
    ledger = GlyphLedger(tmp_path / "graph.jsonl")
    assert ledger.verify().event_count == 10
    assert len([g for g in ledger.glyphs() if g.actor == "independent"]) == 8
