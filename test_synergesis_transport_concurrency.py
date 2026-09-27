"""Concurrency regression tests for signed provenance transport replay handling."""
from concurrent.futures import ThreadPoolExecutor
import copy
import multiprocessing
import threading
import time
import synergesis_provenance_transport as transport
from pathlib import Path

import pytest

from synergesis_provenance_transport import ProvenanceReplayLedger
from test_synergesis_provenance_transport import setup, resign


def _append_from_process(path, index, gate):
    original_digest = transport._digest
    def delayed_digest(value):
        time.sleep(0.01)
        return original_digest(value)
    transport._digest = delayed_digest
    gate.wait(10)
    ProvenanceReplayLedger(path).append(
        sender_id="agent-A",
        bundle_id=f"bundle-{index}",
        envelope_nonce=f"nonce-{index}",
        remote_glyph_id=f"remote-{index}",
        local_glyph_id=f"local-{index}",
    )


def test_concurrent_same_signed_bundle_has_one_import(tmp_path):
    state = setup(tmp_path)
    bundle = state["bundle"]
    mutation_lock = threading.Lock()
    receipt_appends = 0
    origin_bindings = 0
    original_append = state["local_store"].append
    original_bind = state["local_security"].bind_origin

    def counted_append(receipt):
        nonlocal receipt_appends
        with mutation_lock:
            receipt_appends += 1
        return original_append(receipt)

    def counted_bind(*args, **kwargs):
        nonlocal origin_bindings
        with mutation_lock:
            origin_bindings += 1
        return original_bind(*args, **kwargs)

    state["local_store"].append = counted_append
    state["local_security"].bind_origin = counted_bind
    original_staged = state["importer"]._verify_receipts_staged
    def delayed_staged(bundle):
        time.sleep(0.03)  # Widen the old check-to-commit race without bypassing checks.
        return original_staged(bundle)
    state["importer"]._verify_receipts_staged = delayed_staged
    barrier = threading.Barrier(8)
    importers = []
    for _ in range(8):
        importer = copy.copy(state["importer"])
        importer.replay_ledger = ProvenanceReplayLedger(state["replay"].path)
        importers.append(importer)

    def run_import(importer):
        barrier.wait(timeout=10)
        return importer.import_bundle(bundle)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(run_import, importer) for importer in importers]
    results = []
    failures = []
    for future in futures:
        try:
            results.append(future.result())
        except ValueError as exc:
            failures.append(str(exc))
    assert len(results) == 1
    assert len(failures) == 7
    assert all("replay" in failure for failure in failures)
    assert len(state["replay"].events()) == 1
    assert receipt_appends == len(bundle.receipts)
    assert origin_bindings == 1
    assert len(state["local_graph"].ledger.find_by_external_ref(
        f"remote-bundle:{bundle.bundle_id}"
    )) == 1


def test_concurrent_distinct_signed_bundles_both_import(tmp_path):
    state = setup(tmp_path)
    first = state["bundle"]
    second = resign(first, state["sender"], bundle_id="ppb:second-distinct-bundle")
    barrier = threading.Barrier(2)
    importers = []
    for _ in range(2):
        importer = copy.copy(state["importer"])
        importer.replay_ledger = ProvenanceReplayLedger(state["replay"].path)
        importers.append(importer)

    def run_import(importer, bundle):
        barrier.wait(timeout=10)
        return importer.import_bundle(bundle)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_import, importer, bundle)
                   for importer, bundle in zip(importers, (first, second))]
        results = [future.result() for future in futures]
    assert {result.bundle_id for result in results} == {first.bundle_id, second.bundle_id}
    assert state["replay"].verify()[0] == 2
    state["local_store"].verify()
    assert len(state["local_graph"].ledger.find_by_external_ref(
        f"remote-bundle:{first.bundle_id}"
    )) == 1
    assert len(state["local_graph"].ledger.find_by_external_ref(
        f"remote-bundle:{second.bundle_id}"
    )) == 1


def test_replay_ledger_rejects_nonce_reuse_across_distinct_bundle_ids(tmp_path):
    ledger = ProvenanceReplayLedger(tmp_path / "replay.jsonl")
    ledger.append(sender_id="agent-A", bundle_id="bundle-a", envelope_nonce="same-nonce",
                  remote_glyph_id="remote-a", local_glyph_id="local-a")
    with pytest.raises(ValueError, match="replay"):
        ledger.append(sender_id="agent-A", bundle_id="bundle-b", envelope_nonce="same-nonce",
                      remote_glyph_id="remote-b", local_glyph_id="local-b")
    assert len(ledger.events()) == 1


def test_spawned_processes_competing_ledger_appends_preserve_chain(tmp_path):
    path = str(Path(tmp_path) / "process-replay.jsonl")
    ctx = multiprocessing.get_context("spawn")
    gate = ctx.Barrier(8)
    workers = [ctx.Process(target=_append_from_process, args=(path, i, gate)) for i in range(8)]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(20)
            assert worker.exitcode == 0
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(5)
    ledger = ProvenanceReplayLedger(path)
    assert ledger.verify()[0] == 8
    assert len({event.event_id for event in ledger.events()}) == 8
