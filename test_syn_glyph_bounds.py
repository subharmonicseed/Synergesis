import pytest
from synergesis_glyph_protocol import GlyphLedger


def test_oversized_append_preserves_existing_journal(tmp_path):
    p = tmp_path / 'glyphs.jsonl'
    ledger = GlyphLedger(p, max_event_bytes=1200)
    ledger.append_glyph(glyph_type='observation', actor='test', content={'small': True})
    before = p.read_bytes()
    with pytest.raises(ValueError, match='event exceeds'):
        ledger.append_glyph(glyph_type='observation', actor='test', content={'large': 'é' * 1200})
    assert p.read_bytes() == before
    assert ledger.verify().event_count == 1


def test_total_append_cap_preserves_chain(tmp_path):
    p = tmp_path / 'glyphs.jsonl'
    ledger = GlyphLedger(p)
    ledger.append_glyph(glyph_type='observation', actor='test', content={})
    before = p.read_bytes()
    limited = GlyphLedger(p, max_journal_bytes=len(before)+1)
    with pytest.raises(ValueError, match='journal exceeds'):
        limited.append_glyph(glyph_type='observation', actor='test', content={})
    assert p.read_bytes() == before
    assert limited.verify().event_count == 1


@pytest.mark.parametrize('raw,kwargs,error', [
    (b'x'*33, {'max_event_bytes':32}, 'event exceeds'),
    (b'x'*33, {'max_journal_bytes':32}, 'journal exceeds'),
    (b'{}', {}, 'unterminated'),
])
def test_reads_are_bounded_and_incomplete_records_refused(tmp_path, raw, kwargs, error):
    p = tmp_path / 'glyphs.jsonl'; p.write_bytes(raw)
    with pytest.raises(ValueError, match=error):
        GlyphLedger(p, **kwargs).verify()
    assert p.read_bytes() == raw
