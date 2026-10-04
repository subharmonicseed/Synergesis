"""A bounded comparison of text evidence handling; no network implementation here.

Synthetic private fixtures measure task success, not intelligence. matched_context
receives exactly Syn's model input, isolating context from delivery orchestration.
Factory/configuration equality relies on the trusted caller; no weight attestation.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import re
import string
import time

from synergesis_conversation import open_conversation
from synergesis_initiative import InitiativeProfile

ARMS = ('bare_model', 'matched_context', 'syn')
KINDS = ('memory_positive', 'memory_positive', 'document_positive',
         'document_positive', 'memory_negative', 'document_negative')


class DemoBackend:
    """SCRIPTED parser for harness checks. No LLM, inference or intelligence test."""

    def reply(self, messages):
        content = messages[-1]['content']
        query = content.split('Message utilisateur :\n')[-1]
        key = re.search(r'KEY[a-zA-Z0-9]{24}', query).group()
        missing = {'answer': 'unknown', 'source_ids': []}
        if '\nMessage utilisateur :\n' not in content:
            return _json(missing)
        packet = json.loads(content.split('\n', 1)[1].split('\nMessage utilisateur :\n')[0])
        sources = [(m['text'], m['id']) for m in packet['memories']]
        sources += [(e['text'], r['receipt_id']) for r in packet['receipts'] for e in r['evidence']]
        for text, ref in sources:
            match = re.search(re.escape(key) + r'=(VAL[a-zA-Z0-9]{24})', text)
            if match:
                return _json({'answer': match.group(1), 'source_ids': [ref]})
        return _json(missing)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _score(raw, expected, source_ids, available_ids):
    result = {'success': False, 'parse_failure': False, 'abstained': False,
              'wrong_answer': False, 'fabricated_citation': False,
              'citation_failure': False}
    try:
        def unique_fields(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError('duplicate JSON field')
                value[key] = item
            return value
        value = json.loads(raw, object_pairs_hook=unique_fields)
        if (not isinstance(value, dict) or set(value) != {'answer', 'source_ids'}
                or not isinstance(value['answer'], str)
                or not isinstance(value['source_ids'], list)
                or any(not isinstance(s, str) for s in value['source_ids'])
                or len(set(value['source_ids'])) != len(value['source_ids'])):
            raise ValueError('schema')
    except (ValueError, TypeError):
        result['parse_failure'] = True
        return result
    answer, cites = value['answer'], value['source_ids']
    result['abstained'] = answer == 'unknown' and cites == []
    result['wrong_answer'] = answer not in {expected, 'unknown'}
    result['fabricated_citation'] = any(s not in available_ids for s in cites)
    result['citation_failure'] = (set(cites) != set(source_ids))
    result['success'] = answer == expected and not result['citation_failure']
    return result


class _Capture:
    def __init__(self, backend):
        self.backend = backend
        self.messages = None
        self.raw = None
        self.seconds = None

    def reply(self, messages):
        self.messages = deepcopy(messages)
        started = time.perf_counter()
        try:
            self.raw = self.backend.reply(deepcopy(messages))
            return self.raw
        finally:
            self.seconds = time.perf_counter() - started


def _references(packet):
    return ([m['id'] for m in packet['memories']]
            + [r['receipt_id'] for r in packet['receipts'] if r['evidence']])


def _call(factory, messages, *, session=None, profile=None):
    started = time.perf_counter()
    record = {'status': 'failed', 'failure_stage': None, 'messages': None,
              'output': None, 'backend_seconds': None, 'wall_seconds': None,
              'delivery': None, 'input_characters': None,
              'serialized_messages_bytes': None}
    proxy = None
    stage = 'backend_factory'
    try:
        proxy = _Capture(factory())
        record['scripted_demo_backend'] = isinstance(proxy.backend, DemoBackend)
        if session is None:
            stage = 'backend_reply'
            proxy.reply(messages)
        else:
            stage = 'syn_session_or_delivery'
            with open_conversation(session, proxy, profile=profile, max_turns=1,
                                   profile_format='json') as syn:
                delivered = syn.turn(messages[-1]['content'])
            record['delivery'] = {k: delivered[k] for k in
                                  ('cycle_glyph_id', 'reality_status',
                                   'effective_success', 'verification_scope')}
        if not isinstance(proxy.raw, str) or not proxy.raw.strip() or len(proxy.raw) > 16000:
            stage = 'invalid_backend_text'
            raise ValueError('invalid backend text')
        proxy.raw.encode('utf-8')
        record['status'] = 'completed'
    except Exception:
        # Exception messages may contain credentials or remote request contents.
        record['failure_stage'] = stage
    finally:
        record['wall_seconds'] = time.perf_counter() - started
        if proxy is not None:
            record['messages'] = proxy.messages
            record['backend_seconds'] = proxy.seconds
            # Retain bounded valid text only; a supplied backend remains trusted.
            if isinstance(proxy.raw, str) and len(proxy.raw) <= 16000:
                try:
                    proxy.raw.encode('utf-8')
                    record['output'] = proxy.raw
                except UnicodeEncodeError:
                    pass
        if record['messages'] is not None:
            record['input_characters'] = sum(len(m['content']) for m in record['messages'])
            record['serialized_messages_bytes'] = len(_json(record['messages']).encode('utf-8'))
    return record


def run_comparison(output: Path, backend_factory, identity: dict,
                   seed=20261001, repeats=1) -> dict:
    """Write fresh private artifacts, with at most 18 calls per repeat (cap 5).

    identity is supplied metadata (model, settings and demo marker), not verified
    hardware/weight identity. Outputs include exact inputs and synthetic answers.
    """
    if type(seed) is not int or type(repeats) is not int or not 1 <= repeats <= 5:
        raise ValueError('integer seed and repeats in 1..5 required')
    if not callable(backend_factory) or not isinstance(identity, dict):
        raise ValueError('backend_factory and identity required')
    identity_text = _json(identity)
    if len(identity_text) > 8192:
        raise ValueError('identity metadata too large')
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    rng = random.Random(seed)
    cases = []
    report = {'schema': 'syn-comparison-v1', 'identity': deepcopy(identity),
              'configuration_sha256': hashlib.sha256(identity_text.encode()).hexdigest(),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'seed': seed, 'repeats': repeats, 'planned_model_calls': 18 * repeats,
              'case_count': 6 * repeats, 'cases': cases,
              'scope': 'synthetic evidence recall after profile reload and local document retrieval; not reasoning superiority',
              'limitations': ['bare model has no memory/documents; positive abstention is honest but unanswered',
                  'matched_context receives exactly captured Syn input and necessarily runs after Syn',
                  'bare order alternates by case; fresh backend object per arm but provider caching/state cannot be ruled out',
                  'profile reconstructed in same process, not an OS process restart',
                  'input characters and serialized message bytes are proxies, not provider tokens, billed requests, or money',
                  'REALITY checks delivery only; deterministic scorer separately checks synthetic answers',
                  'model outputs/expected answers are retained locally; do not publish private real-world data']}
    started = time.perf_counter()
    alphabet = string.ascii_letters + string.digits
    used = set()
    def unique(prefix):
        while True:
            value = prefix + ''.join(rng.choice(alphabet) for _ in range(24))
            if value not in used:
                used.add(value)
                return value
    def checkpoint():
        path = output / 'report.json'
        path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')
        path.chmod(0o600)
    for index, kind in enumerate(KINDS * repeats):
        key, value = unique('KEY'), unique('VAL')
        prompt = (f'Retrieve the value assigned to {key} from available evidence. '
                  'Return only a JSON object with exactly two fields: "answer" (string), '
                  '"source_ids" (list of evidence IDs). Cite the memory ID or document receipt ID. '
                  'If evidence is missing, return {"answer":"unknown","source_ids":[]}.')
        case_root = output / f'case-{index:03d}'
        case_root.mkdir()
        setup = time.perf_counter()
        profile = InitiativeProfile(case_root / 'profile')
        positive = kind.endswith('positive')
        if kind.startswith('memory'):
            profile.remember(f'{key if positive else unique("KEY")}={value}')
        else:
            doc = case_root / 'fixture.md'
            doc.write_text(f'{key if positive else unique("KEY")}={value}\n', encoding='utf-8')
            profile.add_question(key)
            profile.step([doc])
        del profile
        restored = InitiativeProfile(case_root / 'profile')
        packet = restored.packet(prompt)
        refs = _references(packet)
        expected_refs = refs if positive else []
        case = {'id': index, 'kind': kind, 'query_key': key,
                'expected_answer': value if positive else 'unknown',
                'expected_source_ids': expected_refs, 'retrieved_packet': packet,
                'profile_reloaded': True, 'setup_seconds': time.perf_counter() - setup,
                'order': [], 'arms': {}}
        cases.append(case)
        bare_messages = [{'role': 'user', 'content': prompt}]
        def bare():
            case['order'].append('bare_model')
            case['arms']['bare_model'] = _call(backend_factory, bare_messages)
        if index % 2 == 0:
            bare()
        case['order'].append('syn')
        syn_result = _call(backend_factory, bare_messages,
                           session=case_root / 'conversation', profile=restored)
        case['arms']['syn'] = syn_result
        case['order'].append('matched_context')
        if syn_result['messages'] is not None:
            case['arms']['matched_context'] = _call(backend_factory, syn_result['messages'])
        else:
            case['arms']['matched_context'] = {'status': 'skipped', 'failure_stage': 'no_syn_input_capture'}
        if index % 2:
            bare()
        for arm, record in case['arms'].items():
            if record['status'] == 'completed':
                available = [] if arm == 'bare_model' else refs
                record['score'] = _score(record['output'], case['expected_answer'], expected_refs, available)
            else:
                record['score'] = {'success': False}
        checkpoint()
    report['summary'] = {}
    for arm in ARMS:
        records = [c['arms'][arm] for c in cases]
        summary = {'cases': len(records), 'completed': sum(r['status'] == 'completed' for r in records),
                   'failed': sum(r['status'] == 'failed' for r in records),
                   'skipped': sum(r['status'] == 'skipped' for r in records)}
        for metric in ('success', 'parse_failure', 'abstained', 'wrong_answer',
                       'fabricated_citation', 'citation_failure'):
            summary[metric + '_count'] = sum(r['score'].get(metric, False) for r in records)
            summary[metric + '_rate_all_cases'] = summary[metric + '_count'] / len(records)
        summary['wall_seconds'] = sum(r.get('wall_seconds', 0) for r in records)
        summary['input_characters'] = sum(r.get('input_characters') or 0 for r in records)
        summary['serialized_messages_bytes'] = sum(r.get('serialized_messages_bytes') or 0 for r in records)
        report['summary'][arm] = summary
    report['total_wall_seconds'] = time.perf_counter() - started
    report['contains_scripted_demo'] = any(
        record.get('scripted_demo_backend', False)
        for case in cases for record in case['arms'].values())
    checkpoint()
    return report
