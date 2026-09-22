"""Process-level serialization checks for the ROAM agenda and service."""
from __future__ import annotations

from multiprocessing import get_context
from pathlib import Path
import time

import pytest

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_roam import RoamSession
from synergesis_roam_attention import (
    AttentionMeasurements,
    AttentionWeights,
    ResearchAgenda,
    ResearchNeed,
    RoamAttentionController,
)
from synergesis_roam_service import RoamServiceLedger, RoamServiceLimits, SynRoamService
from synergesis_roam_attention import RoamTick


def _need() -> ResearchNeed:
    return ResearchNeed.create(
        domain="science",
        question="Does serialization hold?",
        hypothesis="yes",
        reason="concurrency test",
        measurements=AttentionMeasurements(0.8, 0.8, 0.2, 0.2),
    )


class _Roam:
    def __init__(self, calls):
        self.calls = calls

    def research_once(self, question):
        with self.calls.open("a", encoding="utf-8") as fh:
            fh.write("call\n")
            fh.flush()
        time.sleep(0.05)
        return RoamSession(
            session_id="session:concurrency",
            question=question,
            method_id="method:test",
            executions=(),
            total_items=0,
            total_cost_units=0.0,
            status="completed",
            plan_glyph_id="plan:test",
        )


def _agenda_worker(root, ledger_path, barrier, output):
    try:
        root = Path(root)
        graph = GlyphAuditGraph(GlyphLedger(root / "glyphs.jsonl"))
        agenda = ResearchAgenda(
            root / "agenda.jsonl",
            graph=graph,
            weights=AttentionWeights(1, 1, 1, 1),
        )
        controller = RoamAttentionController(
            agenda=agenda, roam=_Roam(root / "calls.log")
        )
        original = agenda.select_next

        def delayed_select():
            selected = original()
            time.sleep(0.1)
            return selected

        agenda.select_next = delayed_select
        service = SynRoamService(
            controller=controller,
            ledger=RoamServiceLedger(root / ledger_path),
            limits=RoamServiceLimits(1, False),
        )
        barrier.wait(timeout=10)
        tick = service.tick_once()
        output.put(("ok", tick.status, tick.need_id))
    except Exception as exc:  # pragma: no cover - surfaced by parent assertion
        output.put(("error", type(exc).__name__, str(exc)))


def _run_workers(root, ledger_paths):
    ctx = get_context("spawn")
    barrier = ctx.Barrier(len(ledger_paths))
    output = ctx.Queue()
    workers = [ctx.Process(target=_agenda_worker, args=(str(root), path, barrier, output))
               for path in ledger_paths]
    for worker in workers:
        worker.start()
    try:
        results = [output.get(timeout=20) for _ in workers]
    finally:
        for worker in workers:
            worker.join(timeout=5)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
                worker.join(timeout=5)
    return results


def _make_agenda(path):
    graph = GlyphAuditGraph(GlyphLedger(path / "glyphs.jsonl"))
    agenda = ResearchAgenda(
        path / "agenda.jsonl",
        graph=graph,
        weights=AttentionWeights(1, 1, 1, 1),
    )
    agenda.add(_need())
    return agenda


@pytest.mark.parametrize("ledger_paths", [("service.jsonl", "service.jsonl"),
                                           ("service-a.jsonl", "service-b.jsonl")])
def test_spawned_schedulers_research_one_pending_need_once(tmp_path, ledger_paths):
    agenda = _make_agenda(tmp_path)
    results = _run_workers(tmp_path, ledger_paths)
    assert all(result[0] == "ok" for result in results), results
    assert sum(result[1] == "researched" for result in results) == 1
    assert sum(result[1] == "idle" for result in results) == 1
    assert len((tmp_path / "calls.log").read_text(encoding="utf-8").splitlines()) == 1
    records = [r for path in set(ledger_paths)
               for r in RoamServiceLedger(tmp_path / path).records()]
    assert sorted(r.status for r in records) == ["idle", "researched"]
    assert agenda.get(_need().need_id).event_count == 2
    agenda.graph.ledger.verify()


def _add_worker(root, index, barrier, output):
    try:
        root = Path(root)
        graph = GlyphAuditGraph(GlyphLedger(root / "add-glyphs.jsonl"))
        agenda = ResearchAgenda(root / "add-agenda.jsonl", graph=graph,
                                weights=AttentionWeights(1, 1, 1, 1))
        barrier.wait(timeout=10)
        need = ResearchNeed.create(
            domain="science", question=f"q-{index}", reason="parallel add",
            measurements=AttentionMeasurements(.1, .2, .3, .4),
            source_glyph_ids=(graph.ledger.find_by_external_ref("seed")[0].glyph_id,),
        )
        agenda.add(need)
        output.put("ok")
    except Exception as exc:
        output.put(f"{type(exc).__name__}: {exc}")


def test_distinct_concurrent_agenda_adds_preserve_all_rows_and_edges(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "add-glyphs.jsonl"))
    graph.create("observation", actor="test", content={"source": True}, external_refs=("seed",))
    ctx = get_context("spawn")
    barrier, output = ctx.Barrier(2), ctx.Queue()
    workers = [ctx.Process(target=_add_worker, args=(str(tmp_path), i, barrier, output)) for i in range(2)]
    for worker in workers:
        worker.start()
    try:
        assert [output.get(timeout=20) for _ in workers] == ["ok", "ok"]
    finally:
        for worker in workers:
            worker.join(timeout=5)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
    rows = (tmp_path / "add-agenda.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2
    reopened = ResearchAgenda(tmp_path / "add-agenda.jsonl", graph=graph,
                              weights=AttentionWeights(1, 1, 1, 1))
    assert len(reopened.pending()) == 2
    assert graph.ledger.verify().event_count == 5
    assert len(graph.ledger.edges()) == 2


def _transition_worker(root, action, barrier, output):
    try:
        root = Path(root)
        graph = GlyphAuditGraph(GlyphLedger(root / "race-glyphs.jsonl"))
        agenda = ResearchAgenda(root / "race-agenda.jsonl", graph=graph,
                                weights=AttentionWeights(1, 1, 1, 1))
        barrier.wait(timeout=10)
        if action == "cancel":
            agenda.cancel(_need().need_id, reason="race")
        else:
            agenda.mark_researched(_need().need_id, "session:race")
        output.put("accepted")
    except ValueError:
        output.put("rejected")
    except Exception as exc:
        output.put(f"{type(exc).__name__}: {exc}")


def test_concurrent_terminal_agenda_transitions_accept_one(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "race-glyphs.jsonl"))
    agenda = ResearchAgenda(tmp_path / "race-agenda.jsonl", graph=graph,
                            weights=AttentionWeights(1, 1, 1, 1))
    agenda.add(_need())
    ctx = get_context("spawn")
    barrier, output = ctx.Barrier(2), ctx.Queue()
    workers = [ctx.Process(target=_transition_worker, args=(str(tmp_path), action, barrier, output))
               for action in ("cancel", "research")]
    for worker in workers:
        worker.start()
    try:
        assert sorted(output.get(timeout=20) for _ in workers) == ["accepted", "rejected"]
    finally:
        for worker in workers:
            worker.join(timeout=5)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
    reopened = ResearchAgenda(agenda.path, graph=graph, weights=agenda.weights)
    assert reopened.get(_need().need_id).status in {"cancelled", "researched"}
    assert reopened.get(_need().need_id).event_count == 2
    graph.ledger.verify()


def _ledger_worker(path, index, barrier, output):
    ledger = RoamServiceLedger(path)
    barrier.wait(timeout=10)
    tick = RoamTick(f"need:{index}", type("S", (), {"session_id": f"session:{index}"})(), "researched")
    try:
        ledger.append(tick)
        output.put("ok")
    except Exception as exc:
        output.put(f"{type(exc).__name__}: {exc}")


def test_concurrent_service_ledger_appends_form_one_chain(tmp_path):
    ctx = get_context("spawn")
    path = tmp_path / "service.jsonl"
    barrier, output = ctx.Barrier(2), ctx.Queue()
    workers = [ctx.Process(target=_ledger_worker, args=(str(path), i, barrier, output)) for i in range(2)]
    for worker in workers:
        worker.start()
    try:
        assert sorted(output.get(timeout=20) for _ in workers) == ["ok", "ok"]
    finally:
        for worker in workers:
            worker.join(timeout=5)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
    records = RoamServiceLedger(path).records()
    assert [record.sequence for record in records] == [1, 2]
    assert records[1].previous_digest == records[0].digest
