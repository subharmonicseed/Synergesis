"""Live, policy-constrained source adapters for SYN-ROAM.

These adapters are read-only sensory organs. They fetch public metadata/content
from fixed or explicitly configured sources and convert it to ``RetrievedItem``.
They do not execute instructions found in remote content and do not expose a
general-purpose browser to the model.

Network invariants
------------------
- HTTPS only.
- Destination host allowlist.
- Redirects are revalidated against the allowlist.
- Explicit response-size cap.
- Explicit timeout/retry/backoff policy.
- Sequential per-host pacing.
- Optional persistent GET cache.
- Authentication secrets never enter RetrievedItem/Glyph content.
"""
from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import base64
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
import xml.etree.ElementTree as ET

import requests

from synergesis_roam import RetrievedItem


# ---------------------------------------------------------------------------
# HTTP substrate
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    url: str


class HttpTransport(Protocol):
    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        ...


class RequestsTransport:
    """Small requests-based transport with redirects disabled."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        response = self.session.get(
            url,
            headers=dict(headers),
            timeout=timeout_seconds,
            allow_redirects=False,
        )
        return HttpResponse(
            status_code=int(response.status_code),
            headers={str(k).lower(): str(v) for k, v in response.headers.items()},
            body=bytes(response.content),
            url=str(response.url),
        )


class Clock(Protocol):
    def monotonic(self) -> float:
        ...

    def epoch(self) -> float:
        ...

    def sleep(self, seconds: float) -> None:
        ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def epoch(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


@dataclass(frozen=True)
class HttpPolicy:
    allowed_hosts: frozenset[str]
    min_interval_seconds: float
    timeout_seconds: float
    max_response_bytes: int
    max_retries: int
    retry_backoff_seconds: float
    max_redirects: int
    cache_ttl_seconds: float

    def __post_init__(self):
        if not self.allowed_hosts or any(not h.strip() for h in self.allowed_hosts):
            raise ValueError("allowed_hosts must be explicit and non-empty")
        numeric = {
            "min_interval_seconds": self.min_interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "retry_backoff_seconds": self.retry_backoff_seconds,
            "cache_ttl_seconds": self.cache_ttl_seconds,
        }
        for name, value in numeric.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{name} must be numeric")
            if value < 0:
                raise ValueError(f"{name} must be >= 0")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if self.max_response_bytes < 1:
            raise ValueError("max_response_bytes must be >= 1")
        if self.max_retries < 0 or self.max_redirects < 0:
            raise ValueError("retry/redirect limits must be >= 0")


class DiskHttpCache:
    """Persistent response cache keyed without persisting authorization secrets."""

    def __init__(self, root: str | Path, *, clock: Optional[Clock] = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.clock = clock or SystemClock()

    @staticmethod
    def _key(url: str, headers: Mapping[str, str]) -> str:
        # Authorization affects response visibility but must never be persisted.
        auth = headers.get("Authorization") or headers.get("authorization")
        auth_fingerprint = ""
        if auth:
            import hashlib
            auth_fingerprint = hashlib.sha256(auth.encode("utf-8")).hexdigest()
        material = json.dumps(
            {"url": url, "auth_fingerprint": auth_fingerprint},
            sort_keys=True,
            separators=(",", ":"),
        )
        import hashlib
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        ttl_seconds: float,
    ) -> Optional[HttpResponse]:
        if ttl_seconds <= 0:
            return None
        path = self.root / f"{self._key(url, headers)}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if self.clock.epoch() - float(payload["stored_at"]) > ttl_seconds:
            return None
        return HttpResponse(
            status_code=int(payload["status_code"]),
            headers=dict(payload["headers"]),
            body=base64.b64decode(payload["body_b64"]),
            url=payload["url"],
        )

    def put(
        self,
        *,
        request_url: str,
        request_headers: Mapping[str, str],
        response: HttpResponse,
    ) -> None:
        path = self.root / f"{self._key(request_url, request_headers)}.json"
        payload = {
            "stored_at": self.clock.epoch(),
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body_b64": base64.b64encode(response.body).decode("ascii"),
            "url": response.url,
        }
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


class PoliteHttpClient:
    """Allowlisted GET client with pacing, cache and bounded retries."""

    REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})

    def __init__(
        self,
        *,
        policy: HttpPolicy,
        transport: Optional[HttpTransport] = None,
        cache: Optional[DiskHttpCache] = None,
        clock: Optional[Clock] = None,
    ):
        self.policy = policy
        self.transport = transport or RequestsTransport()
        self.clock = clock or SystemClock()
        self.cache = cache
        self._next_allowed: dict[str, float] = {}

    def _validate_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            raise ValueError("network policy requires HTTPS")
        host = (parsed.hostname or "").lower()
        if host not in {x.lower() for x in self.policy.allowed_hosts}:
            raise ValueError(f"network host is not allowlisted: {host}")
        if parsed.username or parsed.password:
            raise ValueError("userinfo in URLs is forbidden")
        return host

    def _pace(self, host: str) -> None:
        now = self.clock.monotonic()
        delay = self._next_allowed.get(host, now) - now
        if delay > 0:
            self.clock.sleep(delay)
        self._next_allowed[host] = (
            self.clock.monotonic() + self.policy.min_interval_seconds
        )

    def _retry_delay(self, response: HttpResponse, attempt: int) -> Optional[float]:
        headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
        retry_after = headers.get("retry-after")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                try:
                    dt = parsedate_to_datetime(retry_after)
                    return max(0.0, dt.timestamp() - self.clock.epoch())
                except Exception:
                    pass

        if (
            headers.get("x-ratelimit-remaining") == "0"
            and headers.get("x-ratelimit-reset")
        ):
            try:
                return max(
                    0.0,
                    float(headers["x-ratelimit-reset"]) - self.clock.epoch(),
                )
            except ValueError:
                pass

        if response.status_code in {429, 403} or 500 <= response.status_code <= 599:
            return self.policy.retry_backoff_seconds * (2 ** attempt)
        return None

    def get(
        self,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
    ) -> HttpResponse:
        request_headers = dict(headers or {})
        # Validate before cache access as well: a stale cache entry must never
        # bypass a tightened network allowlist.
        self._validate_url(url)
        cached = (
            self.cache.get(
                url=url,
                headers=request_headers,
                ttl_seconds=self.policy.cache_ttl_seconds,
            )
            if self.cache
            else None
        )
        if cached is not None:
            if len(cached.body) > self.policy.max_response_bytes:
                raise ValueError("cached response exceeds max_response_bytes")
            return cached

        current_url = url
        redirects = 0
        attempt = 0

        while True:
            host = self._validate_url(current_url)
            self._pace(host)
            response = self.transport.get(
                url=current_url,
                headers=request_headers,
                timeout_seconds=self.policy.timeout_seconds,
            )

            if len(response.body) > self.policy.max_response_bytes:
                raise ValueError("response exceeds max_response_bytes")

            if response.status_code in self.REDIRECT_CODES:
                location = (
                    response.headers.get("location")
                    or response.headers.get("Location")
                )
                if not location:
                    raise ValueError("redirect response missing Location")
                if redirects >= self.policy.max_redirects:
                    raise ValueError("redirect limit exceeded")
                next_url = urljoin(current_url, location)
                self._validate_url(next_url)
                current_url = next_url
                redirects += 1
                continue

            if 200 <= response.status_code <= 299:
                if self.cache:
                    self.cache.put(
                        request_url=url,
                        request_headers=request_headers,
                        response=response,
                    )
                return response

            delay = self._retry_delay(response, attempt)
            if delay is not None and attempt < self.policy.max_retries:
                self.clock.sleep(delay)
                attempt += 1
                continue

            raise RuntimeError(
                f"HTTP request failed with status {response.status_code}"
            )


def _url_with_query(base: str, params: Mapping[str, Any]) -> str:
    parsed = urlparse(base)
    query = urlencode(
        [(str(k), str(v)) for k, v in params.items() if v is not None],
        doseq=True,
    )
    return urlunparse(parsed._replace(query=query))



def arxiv_documented_http_policy(
    *,
    timeout_seconds: float,
    max_response_bytes: int,
    max_retries: int,
    retry_backoff_seconds: float,
    max_redirects: int,
    cache_ttl_seconds: float,
) -> HttpPolicy:
    """arXiv API policy using its documented 3-second inter-call courtesy delay."""
    return HttpPolicy(
        allowed_hosts=frozenset({"export.arxiv.org"}),
        min_interval_seconds=3.0,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        max_redirects=max_redirects,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def crossref_polite_http_policy(
    *,
    timeout_seconds: float,
    max_response_bytes: int,
    max_retries: int,
    retry_backoff_seconds: float,
    max_redirects: int,
    cache_ttl_seconds: float,
) -> HttpPolicy:
    """Sequential Crossref polite-pool list-query policy.

    Current Crossref documentation applies 3 list requests/second to the polite
    pool. This client is sequential, so 1/3 second pacing stays within that
    documented ceiling before dynamic response headers/backoff are considered.
    """
    return HttpPolicy(
        allowed_hosts=frozenset({"api.crossref.org"}),
        min_interval_seconds=1.0 / 3.0,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        max_redirects=max_redirects,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def github_http_policy(
    *,
    min_interval_seconds: float,
    timeout_seconds: float,
    max_response_bytes: int,
    max_retries: int,
    retry_backoff_seconds: float,
    max_redirects: int,
    cache_ttl_seconds: float,
) -> HttpPolicy:
    """GitHub policy.

    GitHub search has its own rate-limit bucket, so pacing remains explicit and
    response headers drive additional backoff/reset waiting.
    """
    return HttpPolicy(
        allowed_hosts=frozenset({"api.github.com"}),
        min_interval_seconds=min_interval_seconds,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        max_redirects=max_redirects,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def rss_http_policy(
    *,
    allowed_hosts: Sequence[str],
    min_interval_seconds: float,
    timeout_seconds: float,
    max_response_bytes: int,
    max_retries: int,
    retry_backoff_seconds: float,
    max_redirects: int,
    cache_ttl_seconds: float,
) -> HttpPolicy:
    """Explicit policy for configured RSS/Atom feed hosts."""
    return HttpPolicy(
        allowed_hosts=frozenset(allowed_hosts),
        min_interval_seconds=min_interval_seconds,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        max_redirects=max_redirects,
        cache_ttl_seconds=cache_ttl_seconds,
    )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _text(element: Optional[ET.Element]) -> str:
    if element is None or element.text is None:
        return ""
    return " ".join(element.text.split())


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _strip_html(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    parser.close()
    return html.unescape(" ".join(parser.parts)).strip()


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

class ArxivSearchAdapter:
    ENDPOINT = "https://export.arxiv.org/api/query"
    ATOM = {"a": "http://www.w3.org/2005/Atom"}

    def __init__(
        self,
        *,
        client: PoliteHttpClient,
        cost_units_per_item: float,
        user_agent: str,
    ):
        if cost_units_per_item < 0:
            raise ValueError("cost_units_per_item must be >= 0")
        if not user_agent.strip():
            raise ValueError("user_agent is required")
        self.client = client
        self.cost_units_per_item = float(cost_units_per_item)
        self.user_agent = user_agent

    def search(self, *, query: str, max_items: int) -> Sequence[RetrievedItem]:
        if max_items < 1:
            raise ValueError("max_items must be >= 1")
        if max_items > 2000:
            raise ValueError("arXiv max_items must be <= 2000 per API slice")
        safe_query = query.replace('"', " ")
        url = _url_with_query(
            self.ENDPOINT,
            {
                "search_query": f'all:"{safe_query}"',
                "start": 0,
                "max_results": max_items,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
        )
        response = self.client.get(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/atom+xml"},
        )
        try:
            root = ET.fromstring(response.body)
        except ET.ParseError as exc:
            raise ValueError("invalid arXiv Atom response") from exc

        out = []
        for entry in root.findall("a:entry", self.ATOM)[:max_items]:
            source_ref = _text(entry.find("a:id", self.ATOM))
            title = _text(entry.find("a:title", self.ATOM))
            summary = _text(entry.find("a:summary", self.ATOM))
            if not source_ref or not title or not summary:
                continue
            authors = [
                _text(author.find("a:name", self.ATOM))
                for author in entry.findall("a:author", self.ATOM)
            ]
            categories = [
                cat.attrib.get("term", "")
                for cat in entry.findall("a:category", self.ATOM)
                if cat.attrib.get("term")
            ]
            content = json.dumps(
                {
                    "summary": summary,
                    "authors": authors,
                    "published": _text(entry.find("a:published", self.ATOM)),
                    "updated": _text(entry.find("a:updated", self.ATOM)),
                    "categories": categories,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            out.append(
                RetrievedItem(
                    source_ref=source_ref,
                    title=title,
                    content=content,
                    source_type="arxiv",
                    cost_units=self.cost_units_per_item,
                )
            )
        return tuple(out)


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

class CrossrefSearchAdapter:
    ENDPOINT = "https://api.crossref.org/works"

    def __init__(
        self,
        *,
        client: PoliteHttpClient,
        mailto: str,
        user_agent: str,
        cost_units_per_item: float,
    ):
        if "@" not in mailto:
            raise ValueError("Crossref polite-pool mailto must be an email address")
        if not user_agent.strip():
            raise ValueError("user_agent is required")
        if cost_units_per_item < 0:
            raise ValueError("cost_units_per_item must be >= 0")
        self.client = client
        self.mailto = mailto
        self.user_agent = user_agent
        self.cost_units_per_item = float(cost_units_per_item)

    def search(self, *, query: str, max_items: int) -> Sequence[RetrievedItem]:
        if max_items < 1:
            raise ValueError("max_items must be >= 1")
        url = _url_with_query(
            self.ENDPOINT,
            {
                "query.bibliographic": query,
                "rows": max_items,
                "mailto": self.mailto,
            },
        )
        response = self.client.get(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
        )
        try:
            payload = json.loads(response.body.decode("utf-8"))
            items = payload["message"]["items"]
        except Exception as exc:
            raise ValueError("invalid Crossref JSON response") from exc

        out = []
        for item in items[:max_items]:
            titles = item.get("title") or []
            title = str(titles[0]).strip() if titles else ""
            doi = str(item.get("DOI") or "").strip()
            source_ref = (
                f"https://doi.org/{doi}"
                if doi
                else str(item.get("URL") or "").strip()
            )
            if not source_ref or not title:
                continue
            authors = []
            for author in item.get("author") or []:
                name = " ".join(
                    x for x in [
                        str(author.get("given") or "").strip(),
                        str(author.get("family") or "").strip(),
                    ] if x
                )
                if name:
                    authors.append(name)

            # Abstract text is deliberately not copied here. Crossref warns that
            # some abstracts can be subject to publisher/author copyright.
            metadata = {
                "doi": doi or None,
                "publisher": item.get("publisher"),
                "type": item.get("type"),
                "authors": authors,
                "subjects": item.get("subject") or [],
                "published": item.get("published")
                or item.get("published-print")
                or item.get("published-online"),
                "is_referenced_by_count": item.get("is-referenced-by-count"),
                "references_count": item.get("references-count"),
            }
            out.append(
                RetrievedItem(
                    source_ref=source_ref,
                    title=title,
                    content=json.dumps(
                        metadata, ensure_ascii=False, sort_keys=True
                    ),
                    source_type="crossref",
                    cost_units=self.cost_units_per_item,
                )
            )
        return tuple(out)


# ---------------------------------------------------------------------------
# GitHub repository search
# ---------------------------------------------------------------------------

class GitHubRepositorySearchAdapter:
    ENDPOINT = "https://api.github.com/search/repositories"

    def __init__(
        self,
        *,
        client: PoliteHttpClient,
        user_agent: str,
        api_version: str,
        cost_units_per_item: float,
        token: Optional[str] = None,
    ):
        if not user_agent.strip() or not api_version.strip():
            raise ValueError("GitHub user_agent and api_version are required")
        if cost_units_per_item < 0:
            raise ValueError("cost_units_per_item must be >= 0")
        self.client = client
        self.user_agent = user_agent
        self.api_version = api_version
        self.cost_units_per_item = float(cost_units_per_item)
        self.token = token

    def search(self, *, query: str, max_items: int) -> Sequence[RetrievedItem]:
        if max_items < 1:
            raise ValueError("max_items must be >= 1")
        if max_items > 100:
            raise ValueError("GitHub repository search max_items must be <= 100")
        url = _url_with_query(
            self.ENDPOINT,
            {"q": query, "per_page": max_items},
        )
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.api_version,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        response = self.client.get(url, headers=headers)
        try:
            payload = json.loads(response.body.decode("utf-8"))
            items = payload["items"]
        except Exception as exc:
            raise ValueError("invalid GitHub search JSON response") from exc

        out = []
        for item in items[:max_items]:
            source_ref = str(item.get("html_url") or "").strip()
            title = str(item.get("full_name") or item.get("name") or "").strip()
            if not source_ref or not title:
                continue
            license_obj = item.get("license") or {}
            metadata = {
                "description": item.get("description"),
                "language": item.get("language"),
                "topics": item.get("topics") or [],
                "stargazers_count": item.get("stargazers_count"),
                "forks_count": item.get("forks_count"),
                "open_issues_count": item.get("open_issues_count"),
                "archived": item.get("archived"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "pushed_at": item.get("pushed_at"),
                "license_spdx_id": license_obj.get("spdx_id"),
                "homepage": item.get("homepage"),
            }
            out.append(
                RetrievedItem(
                    source_ref=source_ref,
                    title=title,
                    content=json.dumps(
                        metadata, ensure_ascii=False, sort_keys=True
                    ),
                    source_type="github_repository",
                    cost_units=self.cost_units_per_item,
                )
            )
        return tuple(out)


# ---------------------------------------------------------------------------
# RSS / Atom feeds
# ---------------------------------------------------------------------------

class RssAtomSearchAdapter:
    """Fetch a configured feed URL; local query is used only for filtering."""

    def __init__(
        self,
        *,
        client: PoliteHttpClient,
        feed_url: str,
        source_type: str,
        user_agent: str,
        cost_units_per_item: float,
    ):
        if not source_type.strip() or not user_agent.strip():
            raise ValueError("source_type and user_agent are required")
        if cost_units_per_item < 0:
            raise ValueError("cost_units_per_item must be >= 0")
        # Validate immediately; no dynamically supplied model URL is accepted.
        client._validate_url(feed_url)
        self.client = client
        self.feed_url = feed_url
        self.source_type = source_type
        self.user_agent = user_agent
        self.cost_units_per_item = float(cost_units_per_item)

    def search(self, *, query: str, max_items: int) -> Sequence[RetrievedItem]:
        if max_items < 1:
            raise ValueError("max_items must be >= 1")
        response = self.client.get(
            self.feed_url,
            headers={"User-Agent": self.user_agent, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
        )
        try:
            root = ET.fromstring(response.body)
        except ET.ParseError as exc:
            raise ValueError("invalid RSS/Atom XML response") from exc

        tokens = [x.casefold() for x in re.findall(r"[\w-]+", query) if x]
        candidates: list[RetrievedItem] = []

        if root.tag.endswith("feed"):  # Atom
            ns = {"a": "http://www.w3.org/2005/Atom"}
            entries = root.findall("a:entry", ns)
            for entry in entries:
                title = _text(entry.find("a:title", ns))
                summary = _text(entry.find("a:summary", ns)) or _text(entry.find("a:content", ns))
                ref = _text(entry.find("a:id", ns))
                if not ref:
                    for link in entry.findall("a:link", ns):
                        href = link.attrib.get("href")
                        if href:
                            ref = href
                            break
                if title and ref:
                    body = _strip_html(summary)
                    haystack = f"{title} {body}".casefold()
                    if tokens and not all(t in haystack for t in tokens):
                        continue
                    candidates.append(
                        RetrievedItem(
                            source_ref=ref,
                            title=title,
                            content=json.dumps(
                                {
                                    "summary": body,
                                    "published": _text(entry.find("a:published", ns)),
                                    "updated": _text(entry.find("a:updated", ns)),
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            source_type=self.source_type,
                            cost_units=self.cost_units_per_item,
                        )
                    )
        else:  # RSS 2.x
            channel = root.find("channel")
            items = channel.findall("item") if channel is not None else root.findall(".//item")
            for item in items:
                title = _text(item.find("title"))
                link = _text(item.find("link"))
                guid = _text(item.find("guid"))
                ref = link or guid
                description = _strip_html(_text(item.find("description")))
                if title and ref:
                    haystack = f"{title} {description}".casefold()
                    if tokens and not all(t in haystack for t in tokens):
                        continue
                    candidates.append(
                        RetrievedItem(
                            source_ref=ref,
                            title=title,
                            content=json.dumps(
                                {
                                    "summary": description,
                                    "published": _text(item.find("pubDate")),
                                    "guid": guid or None,
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            source_type=self.source_type,
                            cost_units=self.cost_units_per_item,
                        )
                    )

        return tuple(candidates[:max_items])
