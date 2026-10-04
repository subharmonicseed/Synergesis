"""HTTP integration with a controlled local server, not a real language model."""
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from synergesis_chat import main
from synergesis_initiative import InitiativeProfile
from synergesis_ollama_backend import OllamaBackend


@pytest.fixture
def server():
    requests = []
    response = {"status": 200, "body": {"done": True, "message": {
        "content": "Réponse contrôlée du serveur de test."}}}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path, json.loads(self.rfile.read(
                int(self.headers['Content-Length'])))))
            data = json.dumps(response['body']).encode()
            self.send_response(response['status'])
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_port, requests, response
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def arguments(tmp_path, port, session='session'):
    return ['--provider', 'ollama', '--model', 'test-local', '--port', str(port),
            '--output', str(tmp_path / session)]


def test_text_history_and_turn_limit(server, tmp_path, monkeypatch, capsys):
    port, requests, _ = server
    monkeypatch.delenv('SYN_OPENAI_API_KEY', raising=False)
    monkeypatch.setattr('sys.stdin', io.StringIO('Bonjour\nEt ensuite ?\nUn tour en trop\n'))
    assert main(arguments(tmp_path, port) + ['--max-turns', '2']) == 0
    assert len(requests) == 2
    assert all(path == '/api/chat' for path, _ in requests)
    first, second = [body for _, body in requests]
    assert first['model'] == 'test-local'
    assert first['stream'] is False
    assert 'format' not in first and 'tools' not in first
    assert first['options']['num_predict'] == 512
    assert second['messages'][0]['role'] == 'system'
    assert first['messages'][0] == second['messages'][0]
    assert second['messages'][1:] == [
        {'role': 'user', 'content': 'Bonjour'},
        {'role': 'assistant', 'content': 'Réponse contrôlée du serveur de test.'},
        {'role': 'user', 'content': 'Et ensuite ?'},
    ]
    output = capsys.readouterr().out
    assert output.count('Trace :') == 2
    assert 'Mode Ollama' in output
    assert list((tmp_path / 'session').rglob('glyph_ledger.jsonl'))


def test_persistent_profile_reaches_local_model(server, tmp_path, capsys):
    port, requests, _ = server
    profile = tmp_path / 'profile'
    common = ['--profile', str(profile)]
    assert main(arguments(tmp_path, port, 'first') + common + [
        '--message', '/memoriser Mon atelier est à Jarrie.']) == 0
    assert not requests  # local commands do not call the provider
    assert main(arguments(tmp_path, port, 'second') + common + [
        '--message', 'Où est mon atelier ?']) == 0
    assert len(requests) == 1
    supplied = requests[0][1]['messages'][-1]['content']
    assert 'Mon atelier est à Jarrie.' in supplied
    assert 'non vérifiées' in supplied
    assert not InitiativeProfile(profile).recall('Réponse contrôlée')
    assert 'Trace :' in capsys.readouterr().out


@pytest.mark.parametrize('body,status', [
    ({'error': 'private-sentinel'}, 500),
    ({'done': False, 'message': {'content': 'private-sentinel'}}, 200),
    ({'done': True, 'message': {'content': 'private-sentinel', 'tool_calls': [{}]}}, 200),
])
def test_failure_is_not_retried_or_delivered(server, tmp_path, capsys, body, status):
    port, requests, response = server
    response.update(body=body, status=status)
    assert main(arguments(tmp_path, port) + ['--message', 'Bonjour']) == 1
    assert len(requests) == 1
    output = capsys.readouterr()
    assert 'private-sentinel' not in output.out + output.err
    assert 'Syn >' not in output.out
    assert 'Trace :' not in output.out


@pytest.mark.parametrize('config', [
    ['--provider', 'ollama'],
    ['--provider', 'ollama', '--model', ' '],
    ['--provider', 'ollama', '--model', 'x' * 129],
    ['--provider', 'ollama', '--model', 'test', '--port', '0'],
    ['--provider', 'ollama', '--model', 'test', '--port', '65536'],
    ['--provider', 'demo', '--port', '11434'],
    ['--provider', 'openai', '--model', 'test', '--port', '11434'],
])
def test_invalid_configuration_creates_no_profile_or_session(config, tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(config + ['--output', str(tmp_path / 'session'),
                       '--profile', str(tmp_path / 'profile'), '--message', 'Bonjour'])
    assert exc.value.code == 2
    assert not (tmp_path / 'session').exists()
    assert not (tmp_path / 'profile').exists()


def test_benchmark_keeps_json_default(server):
    port, requests, _ = server
    backend = OllamaBackend('test-local', port=port)
    backend.reply([{'role': 'user', 'content': 'Return JSON'}])
    assert requests[0][1]['format'] == 'json'


def test_unknown_format_rejected():
    with pytest.raises(ValueError, match='Format'):
        OllamaBackend('test-local', response_format='xml')
