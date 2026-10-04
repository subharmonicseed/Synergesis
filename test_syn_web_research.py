import io
import json
import pytest
from synergesis_initiative import InitiativeProfile, InitiativeError
from synergesis_web_research import ArxivWebResearch
from synergesis_roam import RetrievedItem
from synergesis_chat import main


class Adapter:
    def search(self, **kwargs):
        assert kwargs == {'query': 'quantum', 'max_items': 3}
        return [RetrievedItem('http://arxiv.org/abs/2401.12345v1', 'Quantum test',
            json.dumps({'summary': 'quantum controlled abstract', 'published': '2024-01-01'}), 'arxiv', 0)]


def research():
    r = ArxivWebResearch()
    r.adapter = Adapter()
    return r


def test_normalization_and_persistence(tmp_path):
    p = InitiativeProfile(tmp_path)
    p._web_research = research()
    result = p.web_search('quantum')
    assert result['status'] == 'evidence_found'
    e = result['evidence'][0]
    assert e['path'] == 'https://arxiv.org/abs/2401.12345v1'
    assert e['retrieved_at'] and e['sha256']
    restored = InitiativeProfile(tmp_path).packet('quantum')
    assert restored['receipts'][0]['receipt_id'] == result['receipt_id']
    assert restored['receipts'][0]['evidence'][0]['text'] == e['text']


def test_failed_requests_consume_budget_and_do_not_leak(tmp_path):
    class Failure:
        def search(self, query):
            raise RuntimeError('private-sentinel')
    p = InitiativeProfile(tmp_path, max_steps=1)
    p._web_research = Failure()
    assert p.web_search('quantum')['status'] == 'failed'
    assert 'private-sentinel' not in p.path.read_text()
    with pytest.raises(InitiativeError, match='budget'):
        p.web_search('quantum')


def test_interrupted_attempt_blocks_replay(tmp_path):
    class Interrupted:
        def search(self, query):
            raise KeyboardInterrupt()
    p = InitiativeProfile(tmp_path)
    p._web_research = Interrupted()
    with pytest.raises(KeyboardInterrupt):
        p.web_search('quantum')
    with pytest.raises(InitiativeError, match='unfinished'):
        InitiativeProfile(tmp_path).web_search('quantum')


def test_invalid_query_does_not_write(tmp_path):
    p = InitiativeProfile(tmp_path)
    for q in [' ', 'x'*301, 'query\nsecond']:
        with pytest.raises(InitiativeError):
            p.web_search(q)
    assert not p.ledger.glyphs()


def test_no_results_are_distinct(tmp_path):
    class Empty:
        def search(self, query): return []
    p = InitiativeProfile(tmp_path)
    p._web_research = Empty()
    assert p.web_search('quantum')['status'] == 'no_evidence'


def test_cli_web_passes_source_to_model(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr('synergesis_web_research.ArxivWebResearch', research)
    assert main(['--internet', '--profile', str(tmp_path/'profile'),
        '--output', str(tmp_path/'session'), '--message', '/web quantum']) == 0
    output = capsys.readouterr().out
    assert 'https://arxiv.org/abs/2401.12345v1' in output
    assert 'quantum controlled abstract' in output
    assert 'Trace :' in output


def test_cli_requires_opt_in(tmp_path, capsys):
    assert main(['--output', str(tmp_path/'session'), '--message', '/web quantum']) == 1
    assert 'Recherche désactivée' in capsys.readouterr().out


def test_blank_line_does_not_exit(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr('sys.stdin', io.StringIO('\nbonjour\n/quitter\n'))
    assert main(['--output', str(tmp_path/'session')]) == 0
    assert 'Trace :' in capsys.readouterr().out
