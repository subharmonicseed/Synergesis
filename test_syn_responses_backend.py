"""Offline contract tests; no actual keys or network calls."""
import json
import pytest
import requests
from synergesis_responses_backend import BackendError, OpenAIResponsesBackend

MESSAGES = [{"role": "user", "content": "Bonjour Syn"}]

def completed(text="Bonjour !"):
    return {"status": "completed", "output": [
        {"type": "reasoning", "summary": []},
        {"type": "message", "role": "assistant", "status": "completed",
         "content": [{"type": "output_text", "text": text}]}]}

class Response:
    def __init__(self, payload=None, status=200, raw=None):
        self.status_code = status
        self.raw = raw if raw is not None else json.dumps(payload or completed()).encode()
        self.closed = False
    def iter_content(self, chunk_size):
        for start in range(0, len(self.raw), chunk_size):
            yield self.raw[start:start + chunk_size]
    def close(self):
        self.closed = True

@pytest.fixture
def transport(monkeypatch):
    class Session:
        def __init__(self):
            self.trust_env = True
            self.closed = False
            self.calls = []
            self.response = Response()
            self.error = None
        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if self.error:
                raise self.error
            return self.response
        def close(self):
            self.closed = True
    session = Session()
    monkeypatch.setattr(requests, "Session", lambda: session)
    return session

def backend(**kwargs):
    return OpenAIResponsesBackend("test-key-not-a-real-credential", "explicit-model", **kwargs)

def test_fixed_endpoint_honest_instructions_no_tools_no_store(transport):
    engine = backend()
    assert engine.reply(MESSAGES) == "Bonjour !"
    url, options = transport.calls[0]
    assert url == "https://api.openai.com/v1/responses"
    assert options["allow_redirects"] is False
    assert options["stream"] is True
    assert options["timeout"] == 30
    assert transport.trust_env is False
    payload = json.loads(options["data"])
    assert payload["input"] == MESSAGES
    assert payload["model"] == "explicit-model"
    assert payload["store"] is False and payload["stream"] is False
    assert payload["tools"] == []
    assert "cannot execute" in payload["instructions"]
    assert payload["max_output_tokens"] == 1024
    assert options["headers"]["Authorization"].startswith("Bearer ")
    assert engine.attempts == 1
    assert transport.closed and transport.response.closed

def test_failed_request_consumes_budget_without_retry_or_secret_error(transport):
    transport.error = requests.Timeout("secret-key response-body")
    engine = backend(max_calls=1)
    with pytest.raises(BackendError, match="connection failed") as error:
        engine.reply(MESSAGES)
    assert "secret-key" not in str(error.value)
    with pytest.raises(BackendError, match="budget exhausted"):
        engine.reply(MESSAGES)
    assert len(transport.calls) == 1 and transport.closed

@pytest.mark.parametrize("status", [301, 302, 307, 400, 401, 429, 500])
def test_http_failures_never_parse_or_follow(transport, status):
    transport.response = Response(status=status, raw=b"private response body")
    with pytest.raises(BackendError, match="rejected"):
        backend().reply(MESSAGES)
    assert transport.response.closed

@pytest.mark.parametrize("kwargs", [
    {"max_calls": True}, {"max_calls": 0}, {"max_calls": 101},
    {"max_output_tokens": 4097}, {"max_output_tokens": 1.5},
    {"timeout": float("nan")}, {"timeout": float("inf")},
    {"timeout": 0}, {"timeout": True}, {"timeout": 121},
])
def test_constructor_bounds(kwargs):
    with pytest.raises(BackendError):
        backend(**kwargs)

@pytest.mark.parametrize("key,model", [("", "model"), ("key\nleak", "model"),
                                         ("key", ""), ("key", "model\n")])
def test_credential_and_model_validation(key, model):
    with pytest.raises(BackendError):
        OpenAIResponsesBackend(key, model)

@pytest.mark.parametrize("messages", [
    [], [{"role": "system", "content": "do actions"}],
    [{"role": "user", "content": ""}],
    [{"role": "user", "content": "hi", "tools": []}],
    MESSAGES * 42, MESSAGES * 2,
    MESSAGES + [{"role": "assistant", "content": "hello"}],
    [{"role": "user", "content": "x" * 32001}],
    [{"role": "user", "content": "\ud800"}],
    [{"role": "user", "content": "\x00" * 32000}],
])
def test_invalid_messages_do_not_attempt_transport(transport, messages):
    engine = backend()
    with pytest.raises(BackendError):
        engine.reply(messages)
    assert engine.attempts == 0 and transport.calls == []

@pytest.mark.parametrize("payload", [
    [], {"status": "incomplete", "output": []},
    {"status": "completed", "output": []},
    {"status": "completed", "output": [{"type": "function_call"}]},
    {"status": "completed", "error": {"message": "private"}},
    {"status": "completed", "output": [{"type": "reasoning"}]},
])
def test_reject_partial_and_nonconversation_output(transport, payload):
    transport.response = Response(raw=json.dumps(payload).encode())
    with pytest.raises(BackendError):
        backend().reply(MESSAGES)

def test_refusal_is_generic(transport):
    payload = completed()
    payload["output"][1]["content"] = [{"type": "refusal", "refusal": "private"}]
    transport.response = Response(payload)
    with pytest.raises(BackendError, match="declined") as error:
        backend().reply(MESSAGES)
    assert "private" not in str(error.value)

@pytest.mark.parametrize("raw", [b"not json private", b"\xff", b" " * (256 * 1024 + 1)])
def test_malformed_or_large_stream_is_bounded(transport, raw):
    transport.response = Response(raw=raw)
    with pytest.raises(BackendError):
        backend().reply(MESSAGES)
    assert transport.closed and transport.response.closed

def test_multiple_text_blocks_and_messages(transport):
    payload = completed("first")
    payload["output"][1]["content"].append({"type": "output_text", "text": "second"})
    payload["output"].append(completed("third")["output"][1])
    transport.response = Response(payload)
    assert backend().reply(MESSAGES) == "first\nsecond\nthird"

def test_elapsed_response_timeout(transport, monkeypatch):
    ticks = iter([0, 31])
    monkeypatch.setattr("synergesis_responses_backend.time.monotonic", lambda: next(ticks))
    with pytest.raises(BackendError, match="time limit"):
        backend().reply(MESSAGES)


def test_invalid_unicode_output_is_safe_error(transport):
    transport.response = Response(completed("\ud800"))
    with pytest.raises(BackendError, match="Unicode"):
        backend().reply(MESSAGES)
