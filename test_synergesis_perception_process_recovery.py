"""Restart after real process termination at perception's durable boundaries."""
import multiprocessing
import os
from pathlib import Path

import pytest

from test_synergesis_perception_bus import setup, percept


def _crash_after_glyph(root, kind):
    graph, _, bus = setup(Path(root), authority='external_untrusted', taint='external_untrusted')
    append = graph.ledger.append_glyph
    def fatal(*args, **kwargs):
        result = append(*args, **kwargs)
        if kwargs.get('content', {}).get('kind') == kind:
            os._exit(39)
        return result
    graph.ledger.append_glyph = fatal
    bus.ingest(percept())


@pytest.mark.parametrize('kind', ['raw_percept', 'origin_authority', 'taint', 'normalized_perception'])
def test_process_death_repairs_provenance_without_duplicate_percept(tmp_path, kind):
    ctx = multiprocessing.get_context('spawn')
    worker = ctx.Process(target=_crash_after_glyph, args=(str(tmp_path), kind))
    worker.start()
    try:
        worker.join(10)
        assert worker.exitcode == 39
    finally:
        if worker.is_alive():
            worker.terminate()
        worker.join(2)
    graph, security, bus = setup(tmp_path, authority='external_untrusted', taint='external_untrusted')
    record = bus.ingest(percept())
    assert security.origin_binding(record.raw_glyph_id).content['authority_class'] == 'external_untrusted'
    assert security._policy_targets('taint', record.raw_glyph_id)
    assert any(e.target == record.raw_glyph_id and e.relation == 'derived_from'
               for e in graph.ledger.edges_from(record.normalized_glyph_id))
    kinds = [g.content.get('kind') for g in graph.ledger.glyphs()]
    for expected in ['raw_percept', 'normalized_perception', 'origin_authority', 'taint']:
        assert kinds.count(expected) == 1
    checkpoint = graph.ledger.verify()
    _, _, restarted = setup(tmp_path, authority='external_untrusted', taint='external_untrusted')
    assert restarted.ingest(percept()) == record
    assert graph.ledger.verify() == checkpoint


@pytest.mark.parametrize('authority,taint', [('trusted_observation', 'external_untrusted'), ('external_untrusted', None)])
def test_restart_cannot_replace_original_policy_before_binding(tmp_path, authority, taint):
    ctx = multiprocessing.get_context('spawn')
    worker = ctx.Process(target=_crash_after_glyph, args=(str(tmp_path), 'raw_percept'))
    worker.start()
    try:
        worker.join(10)
        assert worker.exitcode == 39
    finally:
        if worker.is_alive():
            worker.terminate()
        worker.join(2)
    graph, _, changed = setup(tmp_path, authority=authority, taint=taint)
    checkpoint = graph.ledger.verify()
    with pytest.raises(ValueError, match='configuration changed'):
        changed.ingest(percept())
    assert graph.ledger.verify() == checkpoint
    _, security, original = setup(tmp_path, authority='external_untrusted', taint='external_untrusted')
    record = original.ingest(percept())
    assert security.origin_binding(record.raw_glyph_id).content['authority_class'] == 'external_untrusted'
