"""Record one actual CLI or direct Ollama run; no simulated provider or retries.

Uses a fresh process per invocation. Input/output may contain conversation data;
use a test profile and explicit test inputs when sharing a receipt.
"""
import argparse
from dataclasses import asdict
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import os
import urllib.request

source = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(source))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--model', default='syn-mistral-import:latest')
    parser.add_argument('--internet', action='store_true')
    parser.add_argument('--document', type=Path)
    parser.add_argument('--direct', action='store_true', help='Input is a JSON list of messages, supplied unchanged')
    args = parser.parse_args()
    if args.receipt.exists() or args.session.exists():
        parser.error('Receipt and session must be new')
    from synergesis_ollama_backend import OllamaBackend
    from synergesis_conversation import ConversationSession
    from synergesis_initiative import InitiativeProfile
    from synergesis_chat import main as chat_main
    report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
              'source': str(source), 'model': args.model, 'direct': args.direct,
              'profile': str(args.profile), 'session': str(args.session),
              'http_calls': [], 'turn_receipts': [], 'web_results': [], 'complete': False,
              'code_sha256': {name: hashlib.sha256((source/name).read_bytes()).hexdigest()
                              for name in ('synergesis_chat.py', 'synergesis_conversation.py',
                                           'synergesis_initiative.py', 'synergesis_ollama_backend.py',
                                           'synergesis_web_research.py')}}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    def save():
        args.receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    save()

    class Response:
        def __init__(self, original, record): self.original, self.record = original, record
        def __enter__(self): self.original.__enter__(); return self
        def __exit__(self, *a): return self.original.__exit__(*a)
        def read(self, n):
            raw = self.original.read(n)
            self.record['response_sha256'] = hashlib.sha256(raw).hexdigest()
            self.record['response'] = json.loads(raw)
            save()
            return raw

    class Opener:
        def __init__(self, original): self.original = original
        def open(self, request, timeout):
            record = {'url': request.full_url, 'payload': json.loads(request.data), 'timeout': timeout}
            report['http_calls'].append(record)
            save()
            try:
                response = self.original.open(request, timeout=timeout)
                record['http_status'] = response.status
                return Response(response, record)
            except Exception as exc:
                record['error_type'] = type(exc).__name__
                save()
                raise

    original_init, original_turn = OllamaBackend.__init__, ConversationSession.turn
    original_web = InitiativeProfile.web_search
    def init(self, *a, **kw):
        original_init(self, *a, **kw)
        self._opener = Opener(self._opener)
    def turn(self, message):
        result = original_turn(self, message)
        report['turn_receipts'].append(result)
        save()
        return result
    def web(self, query):
        result = original_web(self, query)
        report['web_results'].append(result)
        save()
        return result
    OllamaBackend.__init__, ConversationSession.turn, InitiativeProfile.web_search = init, turn, web
    captured = io.StringIO()
    previous_stdin = sys.stdin
    try:
        raw_input = args.input.read_text(encoding='utf-8')
        report['input'] = raw_input
        with redirect_stdout(captured), redirect_stderr(captured):
            if args.direct:
                backend = OllamaBackend(args.model, response_format=None)
                report['direct_response'] = backend.reply(json.loads(raw_input))
                code = 0
            else:
                sys.stdin = io.StringIO(raw_input)
                argv = ['--provider', 'ollama', '--model', args.model,
                        '--profile', str(args.profile), '--output', str(args.session), '--max-turns', '10']
                if args.internet: argv.append('--internet')
                if args.document: argv.extend(['--document', str(args.document)])
                code = chat_main(argv)
        report['returncode'] = code
        report['terminal'] = captured.getvalue()
        if args.profile.exists():
            profile = InitiativeProfile(args.profile)
            report['profile_glyphs'] = [{'id': g.glyph_id, 'content': g.content}
                                        for g in profile.ledger.glyphs()]
            report['profile_checkpoint'] = asdict(profile.ledger.verify())
        report['complete'] = code == 0 and all(c.get('http_status') == 200 for c in report['http_calls'])
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        report['terminal'] = captured.getvalue()
        code = 1
    finally:
        sys.stdin = previous_stdin
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    print(report.get('terminal', ''))
    print('Real run receipt: '+str(args.receipt))
    return code

if __name__ == '__main__': raise SystemExit(main())
