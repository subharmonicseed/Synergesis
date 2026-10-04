"""Explicit, read-only arXiv research for the conversation profile."""
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlparse

from synergesis_live_sources import (
    ArxivSearchAdapter, PoliteHttpClient, arxiv_documented_http_policy,
)


class ArxivWebResearch:
    """One HTTPS request per search; no page following, tools or model queries."""
    def __init__(self):
        self.adapter = ArxivSearchAdapter(
            client=PoliteHttpClient(policy=arxiv_documented_http_policy(
                timeout_seconds=15, max_response_bytes=262144, max_retries=0,
                retry_backoff_seconds=0, max_redirects=0, cache_ttl_seconds=0,
                max_total_seconds=20)),
            cost_units_per_item=0,
            user_agent='Synergesis/1.0 (https://github.com/subharmonicseed/Synergesis)',
        )

    def search(self, query):
        items = self.adapter.search(query=query, max_items=3)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        evidence = []
        for item in items:
            ref = urlparse(item.source_ref)
            if (ref.scheme not in {'http', 'https'} or ref.hostname != 'arxiv.org'
                    or ref.username or ref.password or ref.port or ref.query or ref.fragment
                    or not re.fullmatch(r'/abs/(?:[0-9]{4}\.[0-9]{4,5}|[a-z-]+/[0-9]{7})(?:v[0-9]+)?', ref.path)):
                raise ValueError('Invalid arXiv source reference')
            metadata = json.loads(item.content)
            summary = metadata['summary']
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError('Invalid summary')
            excerpt = summary[:700]
            while len(json.dumps(excerpt, ensure_ascii=False).encode('utf-8')) > 2000:
                excerpt = excerpt[:len(excerpt) // 2]
            title = item.title[:180]
            while len(json.dumps(title, ensure_ascii=False).encode('utf-8')) > 512:
                title = title[:len(title) // 2]
            evidence.append({
                'path': 'https://arxiv.org' + ref.path,
                'line': 1,  # first line of a normalized abstract, not the paper/PDF
                'title': title,
                'text': excerpt,
                'sha256': hashlib.sha256(excerpt.encode('utf-8')).hexdigest(),
                'hash_scope': 'stored_excerpt_utf8',
                'excerpt_truncated': len(excerpt) < len(summary),
                'published_at': str(metadata.get('published', ''))[:40],
                'retrieved_at': retrieved_at,
                'claim_status': 'remote_abstract_unverified',
            })
        return evidence
