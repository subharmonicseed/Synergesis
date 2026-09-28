import json
import socket

import pytest

from run_syn_discovery import run_discovery
from synergesis_glyph_protocol import GlyphLedger


def test_real_stack_discovery_is_offline_and_keeps_auditable_outcomes(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Discovery must not access the network')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    output = tmp_path / 'discovery'
    result = run_discovery(output)
    assert json.loads((output / 'bilan.json').read_text()) == result
    real, claim = result['scenarios']
    assert real['file_exists'] and real['effective_success']
    assert real['reality']['status'] == 'confirmed'
    assert not claim['file_exists'] and not claim['effective_success']
    assert claim['reality']['status'] == 'contradicted'
    assert claim['learning_score'] == 0
    for scenario in result['scenarios']:
        assert {'executor_claim', 'runtime_reality_observation', 'reality_verdict',
                'reality_effective_outcome', 'prediction_error', 'world_model_revision'} <= set(scenario['kinds'])
        reader = GlyphLedger(scenario['ledger'])
        assert reader.verify().merkle_root == scenario['audit']['merkle_root']
        assert reader.get(scenario['cycle_glyph_id']) is not None
        for glyph_id in scenario['trace_ids'].values():
            if glyph_id is not None:
                assert reader.get(glyph_id) is not None


def test_discovery_refuses_existing_directory_without_changing_it(tmp_path):
    output = tmp_path / 'existing'
    output.mkdir()
    marker = output / 'keep.txt'
    marker.write_text('original')
    with pytest.raises(FileExistsError):
        run_discovery(output)
    assert marker.read_text() == 'original'
    assert list(output.iterdir()) == [marker]
