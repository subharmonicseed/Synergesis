import json
import pytest
from synergesis_ollama_backend import OllamaBackend, _NoRedirect


class Response:
    def __init__(self, content):
        self.content = content
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, limit):
        return self.content[:limit]


def test_local_request_and_usage():
    backend = OllamaBackend("mistral")
    captured = {}
    def open_request(req, timeout):
        captured.update(url=req.full_url, body=json.loads(req.data), timeout=timeout)
        return Response(json.dumps({"done": True, "message": {"content": "{}"},
                                    "eval_count": 2}).encode())
    backend._opener.open = open_request
    assert backend.reply([{"role": "user", "content": "bonjour"}]) == "{}"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["body"]["stream"] is False
    assert captured["body"]["options"]["temperature"] == 0
    assert "tools" not in captured["body"]
    assert backend.usage == {"eval_count": 2}


@pytest.mark.parametrize("body", [b"not json", b"x" * 262145,
    b'{"done":false,"message":{"content":"hello"}}',
    b'{"done":true,"message":{"content":"hello","tool_calls":[{}]}}'])
def test_invalid_response_is_generic(body):
    backend = OllamaBackend("mistral")
    backend._opener.open = lambda *args, **kwargs: Response(body)
    with pytest.raises(RuntimeError, match="Échec du modèle local Ollama"):
        backend.reply([{"role": "user", "content": "question"}])


@pytest.mark.parametrize("kwargs", [{"port": 0}, {"port": True}, {"seed": -1},
                                     {"timeout": 61}])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        OllamaBackend("mistral", **kwargs)


def test_redirects_disabled():
    assert _NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com") is None
