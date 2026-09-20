import json
from pathlib import Path

import pytest

from synergesis_live_sources import (
    ArxivSearchAdapter,
    CrossrefSearchAdapter,
    DiskHttpCache,
    GitHubRepositorySearchAdapter,
    HttpPolicy,
    HttpResponse,
    PoliteHttpClient,
    RssAtomSearchAdapter,
    arxiv_documented_http_policy,
    crossref_polite_http_policy,
)


class FakeClock:
    def __init__(self):
        self.mono = 0.0
        self.wall = 1_700_000_000.0
        self.sleeps = []

    def monotonic(self):
        return self.mono

    def epoch(self):
        return self.wall

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.mono += seconds
        self.wall += seconds


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, *, url, headers, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self.responses:
            raise AssertionError("no fake response remaining")
        response = self.responses.pop(0)
        if callable(response):
            return response(url, headers)
        return response


def response(body=b"ok", status=200, headers=None, url="https://api.example.test/x"):
    return HttpResponse(
        status_code=status,
        headers=headers or {},
        body=body,
        url=url,
    )


def policy(**overrides):
    values = dict(
        allowed_hosts=frozenset({"api.example.test"}),
        min_interval_seconds=0.0,
        timeout_seconds=5.0,
        max_response_bytes=1024 * 1024,
        max_retries=0,
        retry_backoff_seconds=1.0,
        max_redirects=0,
        cache_ttl_seconds=0.0,
    )
    values.update(overrides)
    return HttpPolicy(**values)


def test_http_client_blocks_plain_http_before_transport():
    transport = FakeTransport([])
    client = PoliteHttpClient(policy=policy(), transport=transport)
    with pytest.raises(ValueError, match="HTTPS"):
        client.get("http://api.example.test/x")
    assert transport.calls == []


def test_http_client_blocks_non_allowlisted_host_before_transport():
    transport = FakeTransport([])
    client = PoliteHttpClient(policy=policy(), transport=transport)
    with pytest.raises(ValueError, match="not allowlisted"):
        client.get("https://127.0.0.1/private")
    assert transport.calls == []


def test_redirect_cannot_escape_allowlist():
    transport = FakeTransport(
        [
            response(
                b"",
                status=302,
                headers={"location": "https://169.254.169.254/latest/meta-data"},
            )
        ]
    )
    client = PoliteHttpClient(
        policy=policy(max_redirects=2),
        transport=transport,
    )
    with pytest.raises(ValueError, match="not allowlisted"):
        client.get("https://api.example.test/start")
    assert len(transport.calls) == 1


def test_response_size_cap_is_enforced():
    transport = FakeTransport([response(b"x" * 11)])
    client = PoliteHttpClient(
        policy=policy(max_response_bytes=10),
        transport=transport,
    )
    with pytest.raises(ValueError, match="max_response_bytes"):
        client.get("https://api.example.test/x")


def test_retry_after_is_respected_then_request_succeeds():
    clock = FakeClock()
    transport = FakeTransport(
        [
            response(b"rate", status=429, headers={"retry-after": "2"}),
            response(b"ok", status=200),
        ]
    )
    client = PoliteHttpClient(
        policy=policy(max_retries=1),
        transport=transport,
        clock=clock,
    )
    got = client.get("https://api.example.test/x")
    assert got.body == b"ok"
    assert 2.0 in clock.sleeps
    assert len(transport.calls) == 2


def test_per_host_minimum_interval_is_applied():
    clock = FakeClock()
    transport = FakeTransport([response(), response()])
    client = PoliteHttpClient(
        policy=policy(min_interval_seconds=3.0),
        transport=transport,
        clock=clock,
    )
    client.get("https://api.example.test/a")
    client.get("https://api.example.test/b")
    assert clock.sleeps == [3.0]


def test_cache_avoids_repeat_network_call_and_never_stores_auth_secret(tmp_path):
    clock = FakeClock()
    transport = FakeTransport([response(b"cached")])
    cache = DiskHttpCache(tmp_path / "cache", clock=clock)
    client = PoliteHttpClient(
        policy=policy(cache_ttl_seconds=60.0),
        transport=transport,
        cache=cache,
        clock=clock,
    )
    headers = {"Authorization": "Bearer SUPER-SECRET"}
    first = client.get("https://api.example.test/x", headers=headers)
    second = client.get("https://api.example.test/x", headers=headers)
    assert first.body == second.body == b"cached"
    assert len(transport.calls) == 1
    disk_text = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (tmp_path / "cache").glob("*.json")
    )
    assert "SUPER-SECRET" not in disk_text


def test_arxiv_policy_encodes_documented_three_second_pacing():
    p = arxiv_documented_http_policy(
        timeout_seconds=10,
        max_response_bytes=1_000_000,
        max_retries=2,
        retry_backoff_seconds=1,
        max_redirects=1,
        cache_ttl_seconds=60,
    )
    assert p.allowed_hosts == frozenset({"export.arxiv.org"})
    assert p.min_interval_seconds == 3.0


def test_crossref_polite_list_policy_is_sequential_three_per_second_ceiling():
    p = crossref_polite_http_policy(
        timeout_seconds=10,
        max_response_bytes=1_000_000,
        max_retries=2,
        retry_backoff_seconds=1,
        max_redirects=1,
        cache_ttl_seconds=60,
    )
    assert p.allowed_hosts == frozenset({"api.crossref.org"})
    assert p.min_interval_seconds == pytest.approx(1 / 3)


class StubClient:
    def __init__(self, payload, allowed_hosts=()):
        self.payload = payload
        self.calls = []
        self.policy = type("P", (), {"allowed_hosts": frozenset(allowed_hosts)})()

    def _validate_url(self, url):
        from urllib.parse import urlparse
        host = urlparse(url).hostname
        if self.policy.allowed_hosts and host not in self.policy.allowed_hosts:
            raise ValueError("network host is not allowlisted")
        if not url.startswith("https://"):
            raise ValueError("network policy requires HTTPS")
        return host

    def get(self, url, *, headers=None):
        self.calls.append((url, dict(headers or {})))
        return HttpResponse(200, {}, self.payload, url)


ARXIV_XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>https://arxiv.org/abs/2601.01234v1</id>
    <updated>2026-01-02T00:00:00Z</updated>
    <published>2026-01-01T00:00:00Z</published>
    <title>Auditable Agents</title>
    <summary>A paper about auditable autonomous agents.</summary>
    <author><name>Alice Example</name></author>
    <category term="cs.AI"/>
  </entry>
</feed>'''


def test_arxiv_adapter_parses_atom_into_retrieved_item():
    client = StubClient(ARXIV_XML)
    adapter = ArxivSearchAdapter(
        client=client,
        cost_units_per_item=0.2,
        user_agent="Synergesis/1 contact@example.test",
    )
    items = adapter.search(query="auditable agents", max_items=1)
    assert len(items) == 1
    assert items[0].source_type == "arxiv"
    assert items[0].source_ref == "https://arxiv.org/abs/2601.01234v1"
    content = json.loads(items[0].content)
    assert content["authors"] == ["Alice Example"]
    assert content["categories"] == ["cs.AI"]


def test_arxiv_adapter_rejects_oversized_api_slice_before_network():
    client = StubClient(ARXIV_XML)
    adapter = ArxivSearchAdapter(
        client=client,
        cost_units_per_item=0.2,
        user_agent="Synergesis/1",
    )
    with pytest.raises(ValueError, match="<= 2000"):
        adapter.search(query="x", max_items=2001)
    assert client.calls == []


CROSSREF_JSON = json.dumps(
    {
        "message": {
            "items": [
                {
                    "DOI": "10.1234/example",
                    "title": ["Research Metadata"],
                    "abstract": "<jats:p>copyrighted abstract should not be copied</jats:p>",
                    "publisher": "Example Publisher",
                    "type": "journal-article",
                    "author": [{"given": "A", "family": "Researcher"}],
                    "subject": ["AI"],
                    "is-referenced-by-count": 12,
                    "references-count": 30,
                }
            ]
        }
    }
).encode("utf-8")


def test_crossref_adapter_uses_polite_identification_and_does_not_copy_abstract():
    client = StubClient(CROSSREF_JSON)
    adapter = CrossrefSearchAdapter(
        client=client,
        mailto="contact@example.test",
        user_agent="Synergesis/1 contact@example.test",
        cost_units_per_item=0.1,
    )
    items = adapter.search(query="research metadata", max_items=1)
    assert len(items) == 1
    assert items[0].source_ref == "https://doi.org/10.1234/example"
    assert "copyrighted abstract" not in items[0].content
    url, headers = client.calls[0]
    assert "mailto=contact%40example.test" in url
    assert headers["User-Agent"].startswith("Synergesis/")


GITHUB_JSON = json.dumps(
    {
        "items": [
            {
                "full_name": "openai/example",
                "html_url": "https://github.com/openai/example",
                "description": "Example repository",
                "language": "Python",
                "topics": ["agents"],
                "stargazers_count": 100,
                "forks_count": 5,
                "open_issues_count": 2,
                "archived": False,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
                "pushed_at": "2026-01-02T00:00:00Z",
                "license": {"spdx_id": "MIT"},
                "homepage": None,
            }
        ]
    }
).encode("utf-8")


def test_github_token_stays_in_transport_header_not_retrieved_content():
    client = StubClient(GITHUB_JSON)
    adapter = GitHubRepositorySearchAdapter(
        client=client,
        user_agent="Synergesis/1",
        api_version="2026-03-10",
        cost_units_per_item=0.2,
        token="GH-SECRET",
    )
    items = adapter.search(query="agents", max_items=1)
    assert len(items) == 1
    url, headers = client.calls[0]
    assert headers["Authorization"] == "Bearer GH-SECRET"
    assert "GH-SECRET" not in items[0].content
    assert "GH-SECRET" not in items[0].source_ref
    assert headers["X-GitHub-Api-Version"] == "2026-03-10"


def test_github_adapter_rejects_more_than_api_page_cap():
    client = StubClient(GITHUB_JSON)
    adapter = GitHubRepositorySearchAdapter(
        client=client,
        user_agent="Synergesis/1",
        api_version="2026-03-10",
        cost_units_per_item=0.2,
    )
    with pytest.raises(ValueError, match="<= 100"):
        adapter.search(query="agents", max_items=101)


RSS_XML = b'''<?xml version="1.0"?>
<rss version="2.0">
<channel>
  <title>Science feed</title>
  <item>
    <title>Quantum sensor breakthrough</title>
    <link>https://news.example.test/item-1</link>
    <guid isPermaLink="false">item-1</guid>
    <pubDate>Sat, 12 Sep 2026 06:00:00 GMT</pubDate>
    <description><![CDATA[<p>New quantum sensor result.</p>]]></description>
  </item>
  <item>
    <title>Unrelated gardening</title>
    <link>https://news.example.test/item-2</link>
    <description>Plants</description>
  </item>
</channel>
</rss>'''


def test_rss_adapter_filters_locally_and_strips_markup():
    client = StubClient(RSS_XML, allowed_hosts={"feeds.example.test"})
    adapter = RssAtomSearchAdapter(
        client=client,
        feed_url="https://feeds.example.test/science.xml",
        source_type="rss_science",
        user_agent="Synergesis/1",
        cost_units_per_item=0.05,
    )
    items = adapter.search(query="quantum sensor", max_items=5)
    assert len(items) == 1
    assert items[0].source_ref == "https://news.example.test/item-1"
    content = json.loads(items[0].content)
    assert content["summary"] == "New quantum sensor result."
    assert "<p>" not in items[0].content


def test_rss_feed_url_is_fixed_and_validated_at_construction():
    client = StubClient(RSS_XML, allowed_hosts={"feeds.example.test"})
    with pytest.raises(ValueError, match="not allowlisted"):
        RssAtomSearchAdapter(
            client=client,
            feed_url="https://evil.example/feed.xml",
            source_type="rss",
            user_agent="Synergesis/1",
            cost_units_per_item=0.1,
        )


def test_invalid_source_payload_is_explicit_error():
    client = StubClient(b"not xml")
    adapter = ArxivSearchAdapter(
        client=client,
        cost_units_per_item=0.1,
        user_agent="Synergesis/1",
    )
    with pytest.raises(ValueError, match="invalid arXiv"):
        adapter.search(query="x", max_items=1)
