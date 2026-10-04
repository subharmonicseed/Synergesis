"""Explicitly synthetic HTTP contracts; no test performs a public network call."""
import json
from urllib.parse import urlsplit,parse_qs
import pytest
from synergesis_geo_source import RegionQuery,UsgsSource,source_registry,MAX_BYTES
from synergesis_live_sources import HttpResponse


class Client:
    def __init__(self,response):
        self.response,self.calls = response,[]
    def get(self,url,**kwargs):
        self.calls.append(url)
        if isinstance(self.response,Exception): raise self.response
        return self.response


def response(body=b'',status=200):
    return HttpResponse(status,{},body,RegionQuery().url)


@pytest.mark.parametrize('reply,status',[
    (response(b''),'empty_response'),
    (response(b'',204),'ok_no_events'),
    (response(b'{"type":"FeatureCollection","features":[]}'),'ok_no_events'),
    (response(b'{"type":"FeatureCollection","features":[{"fixture":"simulation"}]}'),'ok_events'),
    (ConnectionError('synthetic offline'),'unavailable'),
    (response(b'not JSON'),'unavailable'),
    (response(b'[]'),'unavailable'),
    (response(b'x'*(MAX_BYTES+1)),'unavailable'),
])
def test_empty_body_no_matches_and_source_failure_are_distinct(reply,status):
    fake=Client(reply)
    source=UsgsSource(source_registry(enabled=True),client=fake)
    result=source.fetch(RegionQuery())
    assert result['status']==status and source.attempts==1 and len(fake.calls)==1
    assert 'collected_at' in result and 'source_url' in result


def test_permission_is_checked_before_network_or_quota_consumption():
    fake=Client(response())
    source=UsgsSource(source_registry(),client=fake)
    with pytest.raises(PermissionError): source.fetch(RegionQuery())
    assert not fake.calls and source.attempts==0


def test_failures_consume_call_budget_and_no_automatic_retry():
    fake=Client(TimeoutError('synthetic timeout'))
    source=UsgsSource(source_registry(enabled=True),max_calls=2,client=fake)
    assert source.fetch(RegionQuery())['status']=='unavailable'
    assert source.fetch(RegionQuery())['status']=='unavailable'
    with pytest.raises(RuntimeError,match='budget'): source.fetch(RegionQuery())
    assert len(fake.calls)==2


def test_only_fixed_https_official_destination_and_documented_parameters():
    parsed=urlsplit(RegionQuery().url)
    params=parse_qs(parsed.query)
    assert (parsed.scheme,parsed.hostname,parsed.path)==('https','earthquake.usgs.gov','/fdsnws/event/1/query')
    assert params['nodata']==['204'] and params['limit']==['12'] and params['eventtype']==['earthquake']
    source=UsgsSource(source_registry(enabled=True))
    assert source.client.policy.max_retries==source.client.policy.max_redirects==0
    assert source.client.policy.max_response_bytes==MAX_BYTES
    assert source.client.transport.session.trust_env is False


@pytest.mark.parametrize('kwargs',[{'limit':101},{'limit':True},{'max_lat':91},{'min_lon':140},
    {'min_magnitude':float('nan')},{'start':'2024-01-01'},{'end':'2023-01-01T00:00:00Z'},
    {'historical':'true'}])
def test_invalid_query_cannot_reach_the_network(kwargs):
    with pytest.raises(ValueError): RegionQuery(**kwargs)


def test_generic_roam_search_has_no_implicit_permission_to_fetch():
    source=UsgsSource(source_registry(enabled=True),client=Client(response()))
    with pytest.raises(PermissionError): source.search(query='some instruction',max_items=1)
    assert source.attempts==0


def test_source_exceeding_result_cap_is_unavailable_not_silently_truncated():
    fake=Client(response(json.dumps({'type':'FeatureCollection','features':[{}]*13}).encode()))
    assert UsgsSource(source_registry(enabled=True),client=fake).fetch(RegionQuery())['status']=='unavailable'
