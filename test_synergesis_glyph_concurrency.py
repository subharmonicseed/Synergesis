"""Concurrency coverage for the append-only glyph journal."""
from __future__ import annotations

import multiprocessing as mp
import time
import threading

import pytest
import synergesis_glyph_protocol as protocol
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger


def _process_worker(path: str, barrier, mode: str, index: int, result):
    try:
        graph = GlyphAuditGraph(GlyphLedger(path))
        original_now = protocol._now

        def delayed_now():
            time.sleep(0.02)  # Widen the interval after dedupe/sequence reads.
            return original_now()

        protocol._now = delayed_now
        barrier.wait(timeout=20)
        if mode == "distinct":
            graph.create("observation", actor=f"p{index}", content={"i": index})
        elif mode == "ref":
            graph.create(
                "evidence", actor=f"p{index}", content={"i": index},
                external_refs=("shared-ref",), dedupe_external_ref="shared-ref",
            )
        elif mode == "edge":
            graph.relate(index[0], index[1], "supports", actor=f"p{index}")
        result.put((True, ""))
    except BaseException as exc:  # report failures from child processes
        result.put((False, repr(exc)))


def _run_processes(path: Path, mode: str, count: int, index=None):
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(count)
    result = ctx.Queue()
    processes = [
        ctx.Process(target=_process_worker, args=(str(path), barrier, mode, i if index is None else index, result))
        for i in range(count)
    ]
    try:
        for process in processes:
            process.start()
        outcomes = [result.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(10)
    assert all(ok for ok, _ in outcomes), outcomes


def test_spawned_processes_preserve_distinct_glyph_chain(tmp_path):
    path = tmp_path / "glyphs.jsonl"
    _run_processes(path, "distinct", 6)
    ledger = GlyphLedger(path)
    assert len(ledger.glyphs()) == 6
    assert ledger.verify().event_count == 6


def test_spawned_processes_dedupe_shared_external_ref(tmp_path):
    path = tmp_path / "glyphs.jsonl"
    _run_processes(path, "ref", 6)
    ledger = GlyphLedger(path)
    assert len(ledger.find_by_external_ref("shared-ref")) == 1
    assert ledger.verify().event_count == 1


def test_spawned_processes_dedupe_same_edge(tmp_path):
    path = tmp_path / "glyphs.jsonl"
    graph = GlyphAuditGraph(GlyphLedger(path))
    source = graph.create("concept", actor="seed", content={"name": "s"})
    target = graph.create("concept", actor="seed", content={"name": "t"})
    _run_processes(path, "edge", 6, index=(source.glyph_id, target.glyph_id))
    ledger = GlyphLedger(path)
    assert len(ledger.edges()) == 1
    assert ledger.verify().event_count == 3


def test_threads_using_multiple_ledger_instances_serialize(tmp_path):
    path = tmp_path / "glyphs.jsonl"

    def append(index):
        return GlyphAuditGraph(GlyphLedger(path)).create(
            "observation", actor=f"t{index}", content={"i": index}
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append, range(24)))
    ledger = GlyphLedger(path)
    assert len(ledger.glyphs()) == 24
    assert ledger.verify().event_count == 24


def test_invalid_private_event_does_not_poison_journal(tmp_path):
    ledger = GlyphLedger(tmp_path / "glyphs.jsonl")
    with pytest.raises(ValueError):
        ledger._append("invalid", {})
    assert ledger.verify().event_count == 0
    assert not ledger.path.exists()


def test_reader_waits_for_writer_and_sees_complete_event(tmp_path, monkeypatch):
    path = tmp_path / "glyphs.jsonl"
    writer, reader = GlyphLedger(path), GlyphLedger(path)
    entered, release, read_started, read_done = (threading.Event() for _ in range(4))
    original = writer._append_locked
    failures, observed = [], []

    def held(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(writer, "_append_locked", held)

    def write():
        try:
            writer.append_glyph(glyph_type="observation", actor="writer", content={"x": 1})
        except BaseException as exc:
            failures.append(exc)

    def read():
        try:
            read_started.set()
            observed.extend(reader.events())
        except BaseException as exc:
            failures.append(exc)
        finally:
            read_done.set()

    first, second = threading.Thread(target=write), threading.Thread(target=read)
    first.start()
    try:
        assert entered.wait(5)
        second.start()
        assert read_started.wait(5)
        assert not read_done.wait(0.05)
    finally:
        release.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert not failures
    assert len(observed) == 1
    assert reader.verify().event_count == 1
