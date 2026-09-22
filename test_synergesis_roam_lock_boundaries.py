"""Real process exit and bounded contention at the research-call boundary."""
import multiprocessing as mp
import os
import threading

import pytest

import synergesis_roam_attention as attention
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_roam_service import RoamServiceLedger, RoamServiceLimits, SynRoamService
from test_synergesis_roam_attention import need, stack


def _agenda(root):
    return attention.ResearchAgenda(
        root / "agenda.jsonl", graph=GlyphAuditGraph(GlyphLedger(root / "graph.jsonl")),
        weights=attention.AttentionWeights(1, 1, 1, 1),
    )


class ExitDuringResearch:
    def __init__(self, root):
        self.root = root

    def research_once(self, question):
        with (self.root / "effect.txt").open("a") as fh:
            fh.write("called\n")
            fh.flush()
            os.fsync(fh.fileno())
        os._exit(23)


def _crashing_worker(root, boundary):
    controller = attention.RoamAttentionController(agenda=_agenda(root), roam=ExitDuringResearch(root))
    target = controller if boundary == "controller" else SynRoamService(
        controller=controller, ledger=RoamServiceLedger(root / "service.jsonl"),
        limits=RoamServiceLimits(1, True),
    )
    target.tick_once()


@pytest.mark.parametrize("boundary", ["controller", "service"])
def test_process_exit_releases_lock_but_preserves_unknown_outcome(tmp_path, boundary):
    agenda = _agenda(tmp_path)
    item = need("process interruption", 0.8)
    agenda.add(item)
    worker = mp.get_context("spawn").Process(target=_crashing_worker, args=(tmp_path, boundary))
    worker.start()
    try:
        worker.join(10)
        assert worker.exitcode == 23
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(10)
    calls = []

    class NoReplay:
        def research_once(self, question):
            calls.append(question)
            raise AssertionError("uncertain call must not repeat")

    restarted = attention.RoamAttentionController(agenda=_agenda(tmp_path), roam=NoReplay())
    target = restarted if boundary == "controller" else SynRoamService(
        controller=restarted, ledger=RoamServiceLedger(tmp_path / "service.jsonl"),
        limits=RoamServiceLimits(1, True),
    )
    with pytest.raises(RuntimeError, match="unknown"):
        target.tick_once()
    assert calls == []
    assert (tmp_path / "effect.txt").read_text() == "called\n"
    assert agenda.get(item.need_id).status == "pending"
    agenda.graph.ledger.verify()


def test_contending_controller_times_out_without_overwriting_live_receipt(tmp_path, monkeypatch):
    _, agenda, first = stack(tmp_path)
    item = need("one live research", 0.9)
    agenda.add(item)
    other_agenda = attention.ResearchAgenda(
        agenda.path, graph=agenda.graph, weights=agenda.weights, actor=agenda.actor,
    )
    second = attention.RoamAttentionController(agenda=other_agenda, roam=first.roam)
    entered, release = threading.Event(), threading.Event()
    calls, errors = [], []
    original = first.roam.research_once

    def held(question):
        calls.append(question)
        entered.set()
        assert release.wait(5)
        return original(question)

    monkeypatch.setattr(first.roam, "research_once", held)

    def run():
        try:
            first.tick_once()
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert entered.wait(5)
        receipt = first._attempt_path.read_bytes()
        monkeypatch.setattr(other_agenda._lock, "timeout", 0.05)
        with pytest.raises(TimeoutError):
            second.tick_once()
        assert first._attempt_path.read_bytes() == receipt
        assert len(calls) == 1
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive()
    assert not errors
    assert agenda.get(item.need_id).status == "researched"
