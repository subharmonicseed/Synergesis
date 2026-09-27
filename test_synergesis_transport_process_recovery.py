"""Actual process death must not silently replay partial transport writes."""
from datetime import timedelta
import multiprocessing
import os
from pathlib import Path

import pytest

from synergesis_aegis import AegisSecurityGraph, IdentityRegistry
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_provenance_receipts import ProvenanceReceiptStore, ProvenanceReceiptVerifier
from synergesis_provenance_transport import (
    ProvenanceReplayLedger, ProvenanceTransportImporter, ProvenanceTransportPolicy,
)
from test_synergesis_provenance_transport import BASE, setup, resign


def reopened(root):
    root = Path(root)
    graph = GlyphAuditGraph(GlyphLedger(root / 'local_glyphs.jsonl'))
    security = AegisSecurityGraph(graph)
    receipts = ProvenanceReceiptStore(root / 'local_receipts.jsonl')
    verifier = ProvenanceReceiptVerifier(
        store=receipts, identity_registry=IdentityRegistry(root / 'identities.jsonl'),
        trusted_origin_issuers=frozenset({'ingress'}),
        trusted_derivation_issuers=frozenset({'relay'}),
        origin_ranks=security.ORIGIN_CLASSES,
    )
    return ProvenanceTransportImporter(
        graph=graph, security_graph=security, receipt_store=receipts,
        receipt_verifier=verifier, replay_ledger=ProvenanceReplayLedger(root / 'replay.jsonl'),
        policy=ProvenanceTransportPolicy(
            trusted_senders=frozenset({'agent-A'}),
            allowed_origin_classes=frozenset({'trusted_observation'}),
            max_lifetime_seconds=600, max_future_skew_seconds=30, max_receipts=8,
        ), now_fn=lambda: BASE + timedelta(seconds=10),
    )


def _die_during_import(root, bundle, stage):
    importer = reopened(root)
    owner, name = {
        'receipt': (importer.receipt_store, 'append'),
        'graph': (importer.graph, 'create'),
        'committed': (importer.replay_ledger, 'append'),
    }[stage]
    original = getattr(owner, name)
    def fatal(*args, **kwargs):
        original(*args, **kwargs)
        os._exit(37)
    setattr(owner, name, fatal)
    importer.import_bundle(bundle)


def killed_import(tmp_path, bundle, stage):
    ctx = multiprocessing.get_context('spawn')
    worker = ctx.Process(target=_die_during_import, args=(str(tmp_path), bundle, stage))
    worker.start()
    try:
        worker.join(10)
        assert worker.exitcode == 37
    finally:
        if worker.is_alive():
            worker.terminate()
        worker.join(2)


def journal_bytes(root):
    return {p.name: p.read_bytes() for p in root.glob('local_*.jsonl')}


@pytest.mark.parametrize('stage', ['receipt', 'graph'])
def test_process_death_blocks_retry_and_other_messages(tmp_path, stage):
    state = setup(tmp_path)
    killed_import(tmp_path, state['bundle'], stage)
    before = journal_bytes(tmp_path)
    other = resign(state['bundle'], state['sender'], bundle_id='ppb:other')
    for bundle in (state['bundle'], other):
        importer = reopened(tmp_path)
        with pytest.raises((RuntimeError, ValueError), match='(?i)interrupted|uncertain|reconcil'):
            importer.import_bundle(bundle)
        assert journal_bytes(tmp_path) == before
        assert importer.replay_ledger.events() == ()


def test_process_death_after_commit_recovers_without_duplicate_effects(tmp_path):
    state = setup(tmp_path)
    killed_import(tmp_path, state['bundle'], 'committed')
    before = journal_bytes(tmp_path)
    importer = reopened(tmp_path)
    with pytest.raises(ValueError, match='replay'):
        importer.import_bundle(state['bundle'])
    assert journal_bytes(tmp_path) == before
    assert importer.replay_ledger.verify()[0] == 1
    other = resign(state['bundle'], state['sender'], bundle_id='ppb:next')
    importer.import_bundle(other)
    assert importer.replay_ledger.verify()[0] == 2
