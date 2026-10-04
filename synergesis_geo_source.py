"""Bounded, opt-in, read-only USGS catalogue adapter (GEV's official source)."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from urllib.parse import urlencode
import requests

from synergesis_live_sources import HttpPolicy, PoliteHttpClient, RequestsTransport
from synergesis_roam import SourcePolicy, SourceRegistry

SOURCE_ID = 'geo:usgs'
ENDPOINT = 'https://earthquake.usgs.gov/fdsnws/event/1/query'
MAX_BYTES = 1024 * 1024


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


@dataclass(frozen=True)
class RegionQuery:
    start: str = '2024-01-01T00:00:00+00:00'
    end: str = '2024-01-03T00:00:00+00:00'
    min_lat: float = 36
    max_lat: float = 38
    min_lon: float = 135
    max_lon: float = 138
    min_magnitude: float = 6
    limit: int = 12
    historical: bool = True

    def __post_init__(self):
        start, end = (datetime.fromisoformat(v.replace('Z', '+00:00')) for v in (self.start, self.end))
        if start.tzinfo is None or end.tzinfo is None or start >= end or (end-start).days > 366:
            raise ValueError('A timezone-aware window of at most 366 days is required')
        for name, lo, hi in [('min_lat',-90,90),('max_lat',-90,90),('min_lon',-180,180),
                             ('max_lon',-180,180),('min_magnitude',-10,12)]:
            value = getattr(self, name)
            if type(value) not in (int,float) or not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(f'Invalid {name}')
        if self.min_lat >= self.max_lat or self.min_lon >= self.max_lon:
            raise ValueError('Region bounds must increase; date-line crossing is unsupported')
        if type(self.limit) is not int or not 1 <= self.limit <= 100 or type(self.historical) is not bool:
            raise ValueError('Invalid result limit or historical mode')

    @property
    def url(self):
        return ENDPOINT + '?' + urlencode({'format':'geojson','starttime':self.start,'endtime':self.end,
            'minlatitude':self.min_lat,'maxlatitude':self.max_lat,'minlongitude':self.min_lon,
            'maxlongitude':self.max_lon,'minmagnitude':self.min_magnitude,'limit':self.limit,
            'orderby':'time-asc','eventtype':'earthquake','nodata':204})


def source_registry(*, enabled=False):
    registry = SourceRegistry()
    registry.register(SourcePolicy(SOURCE_ID, 'geojson', ('geography',), 100, True, enabled))
    return registry


class UsgsSource:
    """Explicit SourceRegistry permission plus existing Syn HTTP policies.

    One attempt consumes one call even on failure. No retries, proxy, redirect,
    cookies or credentials. Quota is per manual process, not a lifetime quota.
    """
    def __init__(self, registry, *, max_calls=4, client=None):
        if type(max_calls) is not int or not 1 <= max_calls <= 4:
            raise ValueError('Source call limit must be 1..4')
        self.registry, self.max_calls, self.attempts = registry, max_calls, 0
        if client is None:
            session = requests.Session()
            session.trust_env = False
            client = PoliteHttpClient(policy=HttpPolicy(
                allowed_hosts=frozenset({'earthquake.usgs.gov'}), min_interval_seconds=1,
                timeout_seconds=10, max_response_bytes=MAX_BYTES, max_retries=0,
                retry_backoff_seconds=0, max_redirects=0, cache_ttl_seconds=0,
                max_total_seconds=12), transport=RequestsTransport(session, max_response_bytes=MAX_BYTES))
        self.client = client

    def search(self, *, query, max_items):
        # Registration joins the existing source permission registry. Generic
        # ROAM search is deliberately unavailable: a manual typed RegionQuery
        # is required, and no automatic research method is registered.
        raise PermissionError('USGS requires an explicit manual RegionQuery; generic research is disabled')

    def fetch(self, query):
        policy = self.registry.get(SOURCE_ID)
        if not policy.enabled or not policy.external_untrusted or 'geography' not in policy.domains:
            raise PermissionError('USGS observation source is not explicitly enabled')
        if not isinstance(query, RegionQuery) or query.limit > policy.max_items_per_query:
            raise ValueError('Query exceeds source item permission')
        if self.attempts >= self.max_calls:
            raise RuntimeError('Source call budget exhausted')
        self.attempts += 1
        result = {'kind':'geo_fetch','source_id':SOURCE_ID,'source_url':query.url,'collected_at':utc_now(),
                  'query':asdict(query),'attempt':self.attempts,'features':[],
                  'data_path':'USGS catalogue adapter -> Syn perception -> GEV earthquake layer'}
        try:
            response = self.client.get(query.url, headers={'Accept':'application/geo+json, application/json'})
            result.update(http_status=response.status_code, response_bytes=len(response.body),
                          response_sha256=sha256(response.body).hexdigest())
            if len(response.body) > MAX_BYTES:
                raise ValueError('Response exceeds byte budget')
            if not response.body.strip():
                # Explicit nodata=204 is the catalogue's successful no-match
                # contract. An unexpected empty HTTP 200 is a different state.
                result['status'] = 'ok_no_events' if response.status_code == 204 else 'empty_response'
                return result
            data = json.loads(response.body)
            if not isinstance(data,dict) or data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'),list):
                raise ValueError('Invalid source GeoJSON')
            if len(data['features']) > query.limit:
                raise ValueError('Source exceeded requested event limit')
            result.update(status='ok_events' if data['features'] else 'ok_no_events',features=data['features'],
                          possibly_truncated=len(data['features']) == query.limit)
        except Exception as exc:
            # Never retain arbitrary provider errors, HTTP bodies or credentials.
            result.update(status='unavailable', error_type=type(exc).__name__)
        return result
