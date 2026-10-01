import json
import re
import pytest
from synergesis_benchmark import run_comparison

class EvidenceBackend:
    def __init__(self, calls): self.calls = calls
    def reply(self, messages):
        self.calls.append(messages)
        content = messages[-1]['content']
        query = content.split('Message utilisateur :\n')[-1]
        key = re.search(r'KEY[a-zA-Z0-9]{24}', query).group()
        if '\nMessage utilisateur :\n' not in content:
            return json.dumps({'answer': 'unknown', 'source_ids': []})
        packet = json.loads(content.split('\n', 1)[1].split('\nMessage utilisateur :\n')[0])
        sources = [(m['text'], m['id']) for m in packet['memories']]
        sources += [(e['text'], r['receipt_id']) for r in packet['receipts'] for e in r['evidence']]
        for text, ref in sources:
            match = re.search(re.escape(key) + r'=(VAL[a-zA-Z0-9]{24})', text)
            if match: return json.dumps({'answer': match.group(1), 'source_ids': [ref]})
        return json.dumps({'answer': 'unknown', 'source_ids': []})


def test_evidence_comparison_exact_matched_input_and_honest_baseline(tmp_path):
    calls = []
    result = run_comparison(tmp_path/'run', lambda: EvidenceBackend(calls), {'demo': True})
    assert len(calls) == 18
    assert result['summary']['syn']['success_count'] == 6
    assert result['summary']['matched_context']['success_count'] == 6
    assert result['summary']['bare_model']['success_count'] == 2
    assert result['summary']['bare_model']['abstained_count'] == 6
    assert result['summary']['bare_model']['wrong_answer_count'] == 0
    assert result['summary']['bare_model']['fabricated_citation_count'] == 0
    assert result['cases'][0]['order'] == ['bare_model', 'syn', 'matched_context']
    assert result['cases'][1]['order'] == ['syn', 'matched_context', 'bare_model']
    for case in result['cases']:
        assert case['arms']['syn']['messages'] == case['arms']['matched_context']['messages']
        assert case['arms']['syn']['delivery']['effective_success']
        assert case['profile_reloaded']
        assert case['expected_answer'] not in case['arms']['bare_model']['messages'][0]['content'] or case['expected_answer'] == 'unknown'
    persisted = json.loads((tmp_path/'run'/'report.json').read_text())
    assert persisted['configuration_sha256'] == result['configuration_sha256']
    with pytest.raises(FileExistsError): run_comparison(tmp_path/'run', lambda: EvidenceBackend(calls), {'demo': True})


@pytest.mark.parametrize('answer', ['```json\n{}\n```', '{"answer":"unknown","source_ids":["invented"]}', '{"answer":"wrong","answer":"unknown","source_ids":[]}'])
def test_malformed_or_fabricated_citations_never_score(tmp_path, answer):
    class Bad:
        def reply(self, messages): return answer
    result = run_comparison(tmp_path/'run', Bad, {'demo': True})
    assert all(s['success_count'] == 0 for s in result['summary'].values())
    metric = 'fabricated_citation_count' if 'invented' in answer else 'parse_failure_count'
    assert result['summary']['syn'][metric] == 6


def test_failures_preserve_reports_and_do_not_expose_exception_messages(tmp_path):
    class Failure:
        def reply(self, messages): raise RuntimeError('sensitive-test-exception')
    result = run_comparison(tmp_path/'run', Failure, {'demo': True})
    assert all(s['failed'] == 6 for s in result['summary'].values())
    assert 'sensitive-test-exception' not in (tmp_path/'run'/'report.json').read_text()
    assert result['cases'][0]['arms']['syn']['messages']


def test_factory_failure_skips_matched_without_model_input(tmp_path):
    def failing_factory(): raise RuntimeError('private')
    result = run_comparison(tmp_path/'run', failing_factory, {'demo': True})
    assert result['summary']['matched_context']['skipped'] == 6
    assert result['summary']['bare_model']['failed'] == 6


def test_invalid_unicode_output_is_failed_without_losing_report(tmp_path):
    class InvalidText:
        def reply(self, messages):
            return chr(0xD800)
    result = run_comparison(tmp_path/'run', InvalidText, {'scripted_demo': True})
    assert all(s['failed'] == 6 for s in result['summary'].values())
    persisted = json.loads((tmp_path/'run'/'report.json').read_text())
    for case in persisted['cases']:
        assert all(record['output'] is None for record in case['arms'].values())


@pytest.mark.parametrize('repeats', [0, 6, True, 1.5])
def test_repeat_budget_rejected_before_creating_output(tmp_path, repeats):
    with pytest.raises(ValueError): run_comparison(tmp_path/'run', lambda: None, {}, repeats=repeats)
    assert not (tmp_path/'run').exists()
