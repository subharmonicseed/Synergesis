"""An importer must recheck freshness after waiting for the shared journal."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from threading import Event

import pytest

from synergesis_provenance_transport import ProvenanceReplayLedger
from test_synergesis_provenance_transport import BASE, setup


def test_bundle_expiring_while_waiting_is_rejected_before_mutations(tmp_path, monkeypatch):
    env = setup(tmp_path)
    importer = env['importer']
    now = [BASE + timedelta(seconds=10)]
    importer.now_fn = lambda: now[0]
    blocker = ProvenanceReplayLedger(tmp_path / 'replay.jsonl')
    started = Event()
    transaction = env['replay'].transaction
    @contextmanager
    def signaled_transaction():
        started.set()
        with transaction():
            yield
    monkeypatch.setattr(env['replay'], 'transaction', signaled_transaction)
    def run():
        return importer.import_bundle(env['bundle'])
    with ThreadPoolExecutor(max_workers=1) as pool:
        with blocker.transaction():
            future = pool.submit(run)
            assert started.wait(2)
            now[0] = BASE + timedelta(seconds=301)
        with pytest.raises(ValueError, match='expired'):
            future.result(timeout=3)
    assert env['replay'].events() == ()
    for filename in ('local_glyphs.jsonl', 'local_receipts.jsonl'):
        path = tmp_path / filename
        assert not path.exists() or path.stat().st_size == 0


def test_import_lock_timeout_does_not_write_remote_claim(tmp_path):
    env = setup(tmp_path)
    blocker = ProvenanceReplayLedger(tmp_path / 'replay.jsonl')
    env['replay'].transaction().timeout = 0.05
    with ThreadPoolExecutor(max_workers=1) as pool:
        with blocker.transaction():
            future = pool.submit(env['importer'].import_bundle, env['bundle'])
            with pytest.raises(TimeoutError):
                future.result(timeout=3)
    assert env['replay'].events() == ()
    for filename in ('local_glyphs.jsonl', 'local_receipts.jsonl'):
        path = tmp_path / filename
        assert not path.exists() or path.stat().st_size == 0
    # Timeout is not a spent nonce: retry once the holder releases it.
    env['importer'].import_bundle(env['bundle'])
    assert len(env['replay'].events()) == 1
