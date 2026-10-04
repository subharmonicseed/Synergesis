"""Synthetic integration on the actual Syn secure stack and read-only HTTP API."""
import json
import socket
import requests
import pytest
from synergesis_geo_model import LocalGeoBackend,GeoModelError,ENDPOINT
from synergesis_geo_source import RegionQuery,UsgsSource
from synergesis_gods_eye import open_geo_session,ProjectionServer,QUESTION
from test_synergesis_geo_observations import feature,COLLECTED,SOURCE_URL,EVENT_ID


class CaptureBackend:
    def reply(self,messages):
        self.messages=messages
        return 'Réponse de fixture : simulation, aucune cause ni prédiction établie.'


def populate(syn):
    syn.store.ingest_events([feature()],collected_at=COLLECTED,source_ref=SOURCE_URL,nature='simulation',historical=True)
    syn.stack.graph.create('observation',actor='test:simulation',content={
        'kind':'geo_fetch','query':{**RegionQuery().__dict__,'start':'2025-01-10T00:00:00+00:00','end':'2025-01-11T00:00:00+00:00'},
        'status':'ok_events','source_url':SOURCE_URL,'collected_at':COLLECTED})


def test_context_reaches_model_and_audit_cycle_is_linked_to_exact_source_after_restart(tmp_path):
    root=tmp_path/'geo'
    backend=CaptureBackend()
    with open_geo_session(root,backend) as syn:
        populate(syn)
    with open_geo_session(root,backend) as syn:
        answer=syn.answer(QUESTION)
        assert EVENT_ID in backend.messages[-1]['content'] and 'simulation' in backend.messages[-1]['content']
        context=syn.stack.graph.ledger.get(answer['context_glyph_id'])
        assert all(e['glyph_id'] in backend.messages[-1]['content'] for e in context.content['packet']['evidence'])
        assert context.content['packet']['evidence']
        assert any(e.target==answer['context_glyph_id'] for e in syn.stack.graph.ledger.edges_from(answer['cycle_glyph_id']))
        assert answer['reality_status']=='confirmed'
        assert syn.projection()['observations']['answer']['cycle_glyph_id']==answer['cycle_glyph_id']
        syn.stack.graph.ledger.verify()


def test_region_change_excludes_old_events_and_old_questions_from_context_and_globe(tmp_path):
    backend=CaptureBackend()
    with open_geo_session(tmp_path/'geo',backend) as syn:
        populate(syn)
        latest=syn._last('geo_fetch')
        query={**dict(latest.content['query']),'min_lon':-10,'max_lon':10}
        syn.stack.graph.create('observation',actor='test:simulation',content={**dict(latest.content),'query':query})
        answer=syn.answer(QUESTION)
        assert not answer['sources']
        view=syn.projection()['observations']
        assert not view['events'] and view['question'] is None


def test_700_byte_question_is_accepted_and_original_is_not_truncated(tmp_path):
    backend=CaptureBackend()
    with open_geo_session(tmp_path/'geo',backend) as syn:
        syn.answer('a'*700)
        assert backend.messages[-1]['content'].endswith('a'*700)


def test_runtime_source_permission_cannot_be_replaced_by_another_registry(tmp_path):
    with open_geo_session(tmp_path/'geo',CaptureBackend()) as syn:
        from synergesis_geo_source import source_registry
        with pytest.raises(PermissionError): syn.collect(UsgsSource(source_registry(enabled=True)),RegionQuery())
        assert not syn._last('geo_fetch')


def test_projection_server_is_loopback_read_only_host_checked_and_cors_restricted(tmp_path):
    with open_geo_session(tmp_path/'geo',CaptureBackend()) as syn:
        populate(syn)
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
        server=ProjectionServer(syn.projection(),port=port);server.start()
        try:
            url=f'http://127.0.0.1:{port}/api/observations'
            r=requests.get(url,timeout=3)
            assert r.status_code==200 and r.json()['events'][0]['nature']=='simulation'
            assert r.headers['Access-Control-Allow-Origin']=='http://127.0.0.1:5173'
            assert requests.get(url,headers={'Host':'evil.invalid'},timeout=3).status_code==403
            assert requests.post(url,timeout=3).status_code==501
            assert server.server.server_address[0]=='127.0.0.1'
        finally: server.close()


class Reply:
    status_code=200
    closed=False
    def __init__(self,value):self.value=value
    def iter_content(self,chunk_size):yield json.dumps(self.value).encode()
    def close(self):self.closed=True
class Transport:
    def __init__(self,reply):self.response,self.calls=reply,[]
    def post(self,*args,**kwargs):self.calls.append((args,kwargs));return self.response
    def close(self):pass


@pytest.mark.parametrize('data',[[],{'choices':[1]}, {'choices':[{'finish_reason':'stop','message':None}]},
    {'choices':[{'finish_reason':'length','message':{'role':'assistant','content':'truncated'}}]}])
def test_malformed_model_output_is_a_controlled_failure(data):
    reply=Reply(data);transport=Transport(reply);backend=LocalGeoBackend(session=transport)
    with pytest.raises(GeoModelError):backend.reply([{'role':'user','content':'fixture simulation'}])
    assert reply.closed and backend.attempts==1


def test_model_input_is_bounded_grounded_and_has_no_tools_no_proxy_no_retry():
    reply=Reply({'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'fixture simulation'}}]})
    transport=Transport(reply);backend=LocalGeoBackend(max_calls=1,session=transport)
    assert backend.reply([{'role':'user','content':'old'},{'role':'assistant','content':'old assertion'},
        {'role':'user','content':'current supplied glyph reference'}])=='fixture simulation'
    args,kwargs=transport.calls[0]
    payload=json.loads(kwargs['data'])
    assert args[0]==ENDPOINT and not kwargs['allow_redirects'] and not transport.trust_env
    assert len(payload['messages'])==2 and 'old assertion' not in kwargs['data'].decode()
    assert 'tools' not in payload
    with pytest.raises(GeoModelError,match='budget'):backend.reply([{'role':'user','content':'next'}])
    assert len(transport.calls)==1
