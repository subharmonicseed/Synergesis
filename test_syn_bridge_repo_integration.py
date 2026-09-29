"""Exercise the bridge against actual repository symbols and its mixed manifest."""
import hashlib
import json
from pathlib import Path

from synergesis_model_context_bridge import SliceRequest, build_context_pack


def test_actual_aegis_slices_share_file_and_reference_real_test():
    root = Path(__file__).resolve().parent
    pinned = hashlib.sha256((root / 'MANIFEST_SHA256.json').read_bytes()).hexdigest()
    result = build_context_pack(
        root=root,
        # This test exercises caller-supplied labels, not Git attestation.
        source_commit='a' * 40,
        manifest_sha256=pinned,
        objective='Review signed resource matching boundaries; test references are not execution receipts.',
        slices=[SliceRequest('synergesis_aegis.py', '_resource_matches'),
                SliceRequest('synergesis_aegis.py', 'AegisGuard._grant_valid_for'),
                SliceRequest('test_syn_resource_contract.py',
                             'test_path_contract_respects_component_boundaries_and_traversal', 'test')],
        counter=lambda text: len(text.encode('utf-8')),
        counter_identity='test/utf8-byte-counter-v1', budget=100_000, reserve=64,
    )
    payload = json.loads(result.text)
    assert len(payload['slices']) == 3
    assert payload['slices'][2]['test_status'] == 'referenced_not_run'
    for item in payload['slices']:
        raw = (root / item['path']).read_bytes()
        assert item['sha256'] == hashlib.sha256(raw).hexdigest()
        if item['role'] != 'interface':
            start, end = item['linenos']
            assert item['code'] == ''.join(raw.decode().splitlines(keepends=True)[start-1:end])
    assert result.accounting['measured'] == len(result.text.encode('utf-8'))
    assert result.accounting['total_with_reserve'] == result.accounting['measured'] + 64
    assert 'test/utf8-byte-counter-v1' in result.text
