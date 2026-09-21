import math

import pytest

from synergesis_live_sources import (
    HttpPolicy,
    HttpResponse,
    PoliteHttpClient,
    RequestsTransport,
)


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def epoch(self):
        return 1_700_000_000 + self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, *, url, headers, timeout_seconds):
        self.calls.append((url, dict(headers), timeout_seconds))
        return self.responses.pop(0)


def response(status=200, body=b"ok", headers=None, url="https://a.test/x"):
    return HttpResponse(status, headers or {}, body, url)


def policy(**kwargs):
    values = dict(
        allowed_hosts=frozenset({"a.test", "b.test"}),
        min_interval_seconds=0,
        timeout_seconds=5,
        max_response_bytes=100,
        max_retries=1,
        retry_backoff_seconds=1,
        max_redirects=2,
        cache_ttl_seconds=0,
    )
    values.update(kwargs)
    return HttpPolicy(**values)


def test_cross_origin_redirect_removes_sensitive_headers_and_compares_ports():
    transport = Transport([
        response(302, headers={"Location": "https://b.test:443/next"}),
        response(url="https://b.test:443/next"),
    ])
    client = PoliteHttpClient(policy=policy(), transport=transport)
    client.get(
        "https://a.test/start",
        headers={"aUtHoRiZaTiOn": "Bearer secret", "COOKIE": "sid=secret", "Accept": "x"},
    )
    assert transport.calls[1][1] == {"Accept": "x"}


def test_redirect_between_ports_on_same_host_is_cross_origin():
    transport = Transport([
        response(302, headers={"location": "https://a.test:444/next"}),
        response(url="https://a.test:444/next"),
    ])
    client = PoliteHttpClient(policy=policy(), transport=transport)
    client.get("https://a.test:443/start", headers={"Authorization": "secret"})
    assert "Authorization" not in transport.calls[1][1]


def test_retry_after_is_capped_by_request_budget():
    clock = Clock()
    transport = Transport([response(429, headers={"Retry-After": "86400"})])
    client = PoliteHttpClient(
        policy=policy(max_retries=1, max_total_seconds=2, max_retry_after_seconds=2),
        transport=transport,
        clock=clock,
    )
    with pytest.raises(TimeoutError, match="max_total_seconds"):
        client.get("https://a.test/x")
    assert clock.sleeps == [2]


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_non_finite_policy_budgets_are_rejected(value):
    with pytest.raises(ValueError):
        policy(max_total_seconds=value)
    with pytest.raises(ValueError):
        policy(max_retry_after_seconds=value)


class StreamingResponse:
    status_code = 200
    headers = {}
    url = "https://a.test/x"

    def __init__(self):
        self.closed = False

    def iter_content(self, chunk_size):
        yield b"1234"
        yield b"5678"

    def close(self):
        self.closed = True


class FailingStreamingResponse(StreamingResponse):
    def iter_content(self, chunk_size):
        yield b"1234"
        raise OSError("read failed")


class Session:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def get(self, url, **kwargs):
        self.kwargs = kwargs
        return self.response


def test_requests_transport_streams_and_closes_response_at_cap():
    response_obj = StreamingResponse()
    session = Session(response_obj)
    transport = RequestsTransport(session, max_response_bytes=7, chunk_size=4)
    with pytest.raises(ValueError, match="max_response_bytes"):
        transport.get(url="https://a.test/x", headers={}, timeout_seconds=1)
    assert response_obj.closed
    assert session.kwargs["stream"] is True
    assert session.kwargs["allow_redirects"] is False


def test_requests_transport_closes_response_when_read_fails():
    response_obj = FailingStreamingResponse()
    transport = RequestsTransport(Session(response_obj), max_response_bytes=100)
    with pytest.raises(OSError, match="read failed"):
        transport.get(url="https://a.test/x", headers={}, timeout_seconds=1)
    assert response_obj.closed


class LateTransport(Transport):
    def __init__(self, clock):
        super().__init__([response()])
        self.clock = clock

    def get(self, *, url, headers, timeout_seconds):
        self.clock.now += timeout_seconds
        return super().get(url=url, headers=headers, timeout_seconds=timeout_seconds)


def test_client_rejects_response_returned_after_total_deadline():
    clock = Clock()
    client = PoliteHttpClient(
        policy=policy(max_total_seconds=1, timeout_seconds=1),
        transport=LateTransport(clock),
        clock=clock,
    )
    with pytest.raises(TimeoutError, match="max_total_seconds"):
        client.get("https://a.test/x")


@pytest.mark.parametrize("credential", ["auth", "headers", "cookies"])
def test_session_credentials_block_cross_origin_redirect(credential):
    class Redirect(StreamingResponse):
        status_code = 302
        headers = {"Location": "https://b.test/next"}

    session = Session(Redirect())
    session.auth = None
    session.headers = {}
    session.cookies = {}
    if credential == "auth":
        session.auth = ("synthetic", "secret")
    elif credential == "headers":
        session.headers = {"AUTHORIZATION": "synthetic"}
    else:
        session.cookies = {"session": "synthetic"}
    client = PoliteHttpClient(policy=policy(), transport=RequestsTransport(session))
    with pytest.raises(ValueError, match="credentialed session"):
        client.get("https://a.test/start")


def test_transport_deadline_includes_connection_setup(monkeypatch):
    import synergesis_live_sources as live
    clock = Clock()
    monkeypatch.setattr(live.time, "monotonic", clock.monotonic)
    response_obj = StreamingResponse()

    class SlowSession(Session):
        def get(self, url, **kwargs):
            clock.now += 2
            return super().get(url, **kwargs)

    with pytest.raises(TimeoutError):
        RequestsTransport(SlowSession(response_obj)).get(
            url="https://a.test/x", headers={}, timeout_seconds=1,
        )
    assert response_obj.closed
