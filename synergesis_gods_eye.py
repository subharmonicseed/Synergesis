"""Manual USGS -> Syn perception/evidence/agenda -> GEV read-only globe.

One existing secure runtime owns all persistence. The HTTP server only exposes
an in-memory projection; it cannot ingest, invoke a model or run commands.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import signal
import sys
import threading
from uuid import uuid4

from synergesis_aegis import ActionSecurityProfile, CapabilityStore, IdentityRegistry, IdentitySigner
from synergesis_agent_loop_v4 import ActionTypeResourceResolver, NoCapabilities, TrustedSourceObservationClassifier
from synergesis_chat import terminal_text
from synergesis_conversation import ConversationSession, _config, _DisabledPlanner
from synergesis_geo_model import LocalGeoBackend, MODEL
from synergesis_geo_observations import GeoObservationStore, GeoDomainAdapter, geo_source_policy, geo_knowledge_rule, SOURCE_ID, MODALITY
from synergesis_geo_source import RegionQuery, UsgsSource, source_registry, utc_now
from synergesis_reality import FunctionRealityProbe, RealityAssertion, RealityProbeBinding, RealityProfile
from synergesis_runtime_session import secure_roam_runtime_session

SYN_BASE = '0b92fce71f96cb6dd912d542a86832bf8234279e'
GEV_BASE = 'aa16b7c3b0166a89d8c7a6089e0aff53a22faaee'
QUESTION = "Qu'as-tu observé dans cette région, qu'est-ce qui a changé et sur quelles données t'appuies-tu ?"
LIMITATIONS = ['Rapports du catalogue USGS, pas une vérification scientifique indépendante.',
    'Magnitude et position sont des estimations de catalogue ; profondeur en kilomètres, coordonnées en degrés.',
    'Question déclenchée par une règle programmée ; cause et prochaines secousses inconnues.',
    'Lecture manuelle bornée, aucun suivi continu ; données historiques signalées comme anciennes.',
    'GEV MCP ne fournit pas de recherche historique : données reçues directement du même fournisseur USGS.']


class GeoProfile:
    store = None
    changes = None
    query = None
    fixed_packet = None
    def packet(self, query):
        if self.fixed_packet is not None:
            return self.fixed_packet
        # This profile is explicitly geography-scoped; the generic French
        # question refers to the configured region, not arbitrary old memories.
        events = region_events(self.store.latest(),self.query) if self.query else []
        retrieval_query = query.encode('utf-8')[:680].decode('utf-8',errors='ignore')+' USGS earthquake'
        packet = self.store.packet(retrieval_query,limit=2,max_bytes=1800,
            allowed_glyph_ids={r['normalized_glyph_id'] for r in events})
        packet['changes'] = self.changes or {}
        packet['question_rule'] = f'Magnitude déclarée >= {self.store.threshold:g} : ouvrir une question, sans recherche automatique.'
        references = {e['evidence_glyph_id'] for e in events}
        packet['open_questions'] = [q['id'] for q in self.store.snapshot()['questions']
            if references.intersection(q['source_glyph_ids'])][:2]
        return packet


class SourcedGeoBackend:
    """Deterministic source fields accompany, but never certify, model prose."""
    def __init__(self,delegate,profile):
        self.delegate,self.profile=delegate,profile
    def reply(self,messages):
        comment=self.delegate.reply(messages)
        packet=self.profile.fixed_packet
        facts=[f"{e['event_id']} : M{e['magnitude']:g}, {e['place']}, {e['event_at']} ({e['freshness']}, {e['nature']})."
            for e in packet['evidence'] if e['magnitude'] is not None]
        changes=', '.join(f'{k}={v}' for k,v in packet['changes'].items()) or 'aucune comparaison disponible'
        return ('Relevé exact du catalogue USGS :\n'+'\n'.join(facts or ['Aucune observation pertinente fournie.'])
            +'\nDernier lot : '+changes+'.\nRègle programmée : '+packet['question_rule']
            +'\nLes causes, les dommages et les prochaines secousses restent inconnus.\n'
            +'Commentaire Mistral non vérifié :\n'+comment)


def region_events(records,query):
    return [r for r in records if r['status'] == 'source_report'
        and query['min_lat'] <= r['latitude'] <= query['max_lat']
        and query['min_lon'] <= r['longitude'] <= query['max_lon']
        and datetime.fromisoformat(query['start'].replace('Z','+00:00')) <= datetime.fromisoformat(r['event_at'])
            <= datetime.fromisoformat(query['end'].replace('Z','+00:00'))
        and r['magnitude'] is not None and r['magnitude'] >= query['min_magnitude']]


@contextmanager
def open_geo_session(root, backend, *, enabled=False, threshold=6, max_turns=10):
    """Same secure stack as conversations, with existing perception bridge.

    Persistent observations/agenda resume; conversational history starts empty.
    No capability for external writes, arbitrary commands or model tools.
    """
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True,exist_ok=True)
    profile = GeoProfile()
    conversation = ConversationSession(SourcedGeoBackend(backend,profile),max_turns=max_turns,profile=profile)
    identities = IdentityRegistry(root/'identities.jsonl')
    observer = 'runtime:reply-mailbox'
    registry = source_registry(enabled=enabled)
    source = UsgsSource(registry)
    with secure_roam_runtime_session(config=_config(root),reasoner=conversation,
        planning_provider=_DisabledPlanner(),executors={'emit_reply':conversation._emit},
        identity_registry=identities,capability_store=CapabilityStore(root/'capabilities.jsonl'),
        trusted_capability_issuers=frozenset(),
        action_security_profiles=(ActionSecurityProfile('emit_reply',False,frozenset()),),
        observation_classifier=TrustedSourceObservationClassifier(frozenset({'user'})),
        capability_resolver=NoCapabilities(),resource_resolver=ActionTypeResourceResolver(),
        reality_probe_bindings=(RealityProbeBinding(observer,'runtime_attested',
            FunctionRealityProbe(observer_id=observer,callback=conversation._observe)),),
        reality_profiles=(RealityProfile('emit_reply',(observer,),(
            RealityAssertion(observer,'present','eq',True),
            RealityAssertion(observer,'turn_id','eq_parameter',parameter_key='turn_id'),
            RealityAssertion(observer,'sha256','sha256_parameter_utf8',parameter_key='text'),)),),
        source_registry=registry,source_adapters={SOURCE_ID:source},research_methods=(),
        perception_source_policies=(geo_source_policy(),),
        perception_adapters={(SOURCE_ID,MODALITY):GeoDomainAdapter()},
        perception_knowledge_rules=(geo_knowledge_rule(),)) as stack:
        if identities.get_optional('SYN-CONVERSATION') is None:
            signer = IdentitySigner('SYN-CONVERSATION')
            identities.register(signer.identity_id,signer.public_key)
        profile.store = GeoObservationStore(stack,magnitude_threshold=threshold)
        conversation._stack, conversation._active = stack, True
        try:
            yield GeoSession(stack,profile,conversation,source)
        finally:
            conversation._active = False
            conversation._history.clear()


class GeoSession:
    def __init__(self,stack,profile,conversation,source):
        self.stack,self.profile,self.conversation = stack,profile,conversation
        self.store = profile.store
        self.source = source

    def _last(self,kind):
        matches = [g for g in self.stack.graph.ledger.glyphs() if g.content.get('kind') == kind]
        return matches[-1] if matches else None

    def collect(self, source, query):
        if source.registry is not self.stack.source_registry:
            raise PermissionError('Collection must use this runtime source permission registry')
        fetched = source.fetch(query)
        metadata = {k:v for k,v in fetched.items() if k != 'features'}
        trace = self.stack.graph.create('observation',actor='SYN-GEO',content=metadata)
        if fetched['status'] not in {'ok_events','ok_no_events'}:
            return metadata
        try:
            result = self.store.ingest_events(fetched['features'],collected_at=fetched['collected_at'],
                source_ref=fetched['source_url'],historical=query.historical)
        except ValueError:
            metadata.update(status='invalid_observations')
            self.stack.graph.create('outcome',actor='SYN-GEO',content={**metadata,'kind':'geo_ingestion_failure'},derived_from=(trace.glyph_id,))
            return metadata
        outcome = self.stack.graph.create('outcome',actor='SYN-GEO',
            content={'kind':'geo_batch_result','counts':result['counts'],'collected_at':result['collected_at'],
                     'source_url':fetched['source_url']},derived_from=(trace.glyph_id,result['collection_glyph_id']))
        self.stack.graph.relate(result['collection_glyph_id'],trace.glyph_id,'derived_from',actor='SYN-GEO')
        self.profile.changes = result['counts']
        return {**metadata,'counts':result['counts'],'batch_glyph_id':outcome.glyph_id}

    def answer(self, question):
        if not isinstance(question,str) or not question.strip() or len(question.encode('utf-8')) > 700:
            raise ValueError('Question limitée à 700 octets UTF-8')
        batch = self._last('geo_batch_result')
        fetch = self._last('geo_fetch')
        self.profile.query = dict(fetch.content['query']) if fetch else None
        self.profile.changes = dict(batch.content['counts']) if batch else {}
        packet = self.profile.packet(question)
        parents = [e['glyph_id'] for e in packet['evidence']]
        context = self.stack.graph.create('observation',actor='SYN-GEO',
            content={'kind':'geo_model_context','packet':packet,'question':question},derived_from=parents)
        self.profile.fixed_packet = packet
        try:
            receipt = self.conversation.turn(question)
        finally:
            self.profile.fixed_packet = None
        # Link the actual audited cycle and the exact bounded source context.
        self.stack.graph.relate(receipt['cycle_glyph_id'],context.glyph_id,'derived_from',actor='SYN-GEO')
        answer = {**receipt,'context_glyph_id':context.glyph_id,'model':MODEL,
                  'sources':[{k:e[k] for k in ('event_id','source_url','glyph_id','evidence_id')} for e in packet['evidence']]}
        self.stack.graph.create('outcome',actor='SYN-GEO',content={'kind':'geo_answer','answer':answer},
            derived_from=(receipt['cycle_glyph_id'],context.glyph_id))
        self.stack.graph.ledger.verify()
        return answer

    def projection(self):
        snapshot = self.store.snapshot()
        fetch = self._last('geo_fetch')
        failure = self._last('geo_ingestion_failure')
        batch = self._last('geo_batch_result')
        answer = self._last('geo_answer')
        status = dict(fetch.content) if fetch else {'status':'not_collected'}
        if failure and fetch and failure.content['collected_at'] == fetch.content['collected_at']:
            status['status'] = 'invalid_observations'
        query = status.get('query')
        events = [r for r in snapshot['observations'] if r['status'] == 'source_report']
        if query:
            events = region_events(events,query)
        for event in events:
            event.update(id=event['event_id'],version=event['revision'],provider='USGS')
        questions = [q for q in snapshot['questions'] if {e['evidence_glyph_id'] for e in events}.intersection(q['source_glyph_ids'])]
        features = [{'type':'Feature','id':e['id'],'geometry':{'type':'Point','coordinates':[e['longitude'],e['latitude'],e['depth_km']]},
            'properties':{'mag':e['magnitude'],'place':e['place'],'time':int(datetime.fromisoformat(e['event_at']).timestamp()*1000),
                          'updated':int(datetime.fromisoformat(e['updated_at']).timestamp()*1000),'url':e['source_url'],
                          'type':'earthquake','magType':e['magnitude_type'],'nature':e['nature'],'syn':e}} for e in events]
        return {'status':{**status,'syn_base':SYN_BASE,'gev_base':GEV_BASE,
                         'budgets':{'source_calls_per_process':4,'response_bytes':1048576,'model_calls_per_process':10,'model_context_bytes':4000}},
            'observations':{'geojson':{'type':'FeatureCollection','features':features},'events':events,
                'observed_at':max((e['collected_at'] for e in events if e['collected_at']),default=None),
                'attempted_at':status.get('collected_at'),'source_url':status.get('source_url'),
                'focus_event_id':events[0]['id'] if events else None,
                'changes':dict(batch.content['counts']) if batch else {},
                'question':({'text':questions[0]['question'],'need_id':questions[0]['id'],
                    'source_glyph_ids':questions[0]['source_glyph_ids']} if questions else None),
                'answer':dict(answer.content['answer']) if answer else None,'limitations':LIMITATIONS,
                'conflicts':[r for r in snapshot['observations'] if r['status'] == 'simultaneous_conflict']}}


class ProjectionServer:
    def __init__(self,projection, *, port=8765):
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError('Invalid local port')
        self._lock = threading.Lock()
        self.update(projection)
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.headers.get('Host') not in {f'127.0.0.1:{port}',f'localhost:{port}'}:
                    self.send_error(403); return
                if self.path not in {'/api/observations','/api/status'}:
                    self.send_error(404); return
                with owner._lock:
                    payload = owner._observations if self.path == '/api/observations' else owner._status
                self.send_response(200)
                self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('Content-Length',str(len(payload)))
                self.send_header('Access-Control-Allow-Origin','http://127.0.0.1:5173')
                self.send_header('Cache-Control','no-store')
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self,*args):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
    def update(self, projection):
        payloads = [json.dumps(projection[k],ensure_ascii=False,allow_nan=False).encode('utf-8') for k in ('observations','status')]
        if any(len(p) > 1048576 for p in payloads):
            raise ValueError('Projection exceeds byte budget')
        with self._lock:
            self._observations,self._status = payloads
    def start(self):
        self.thread.start()
    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Syn : observations USGS et globe GEV, lancement manuel')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--allow-usgs',action='store_true',help='Autorise uniquement GET USGS pour la collecte explicite')
    parser.add_argument('--collect',action='store_true')
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--interactive',action='store_true')
    parser.add_argument('--message')
    parser.add_argument('--receipt',type=Path)
    parser.add_argument('--start',default=RegionQuery.start)
    parser.add_argument('--end',default=RegionQuery.end)
    parser.add_argument('--bbox',type=float,nargs=4,default=[36,38,135,138],metavar=('SUD','NORD','OUEST','EST'))
    parser.add_argument('--min-magnitude',type=float,default=6)
    parser.add_argument('--threshold',type=float,default=6)
    parser.add_argument('--recent',action='store_true',help='Mode récent : fraîcheur dépend aussi de la date de l’événement')
    args = parser.parse_args(argv)
    if args.collect and not args.allow_usgs:
        parser.error('--collect exige --allow-usgs')
    query = RegionQuery(args.start,args.end,*args.bbox,args.min_magnitude,historical=not args.recent)
    backend = LocalGeoBackend()
    server = None
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        with open_geo_session(args.root,backend,enabled=args.allow_usgs,threshold=args.threshold) as syn:
            source = syn.source
            if args.collect:
                result = syn.collect(source,query)
                print('Collecte : '+result['status']+' ; changements : '+json.dumps(result.get('counts',{})),flush=True)
            if args.message:
                try:
                    answer = syn.answer(args.message)
                    print('Syn > '+terminal_text(answer['text'])+'\nTrace : '+answer['cycle_glyph_id'],flush=True)
                except Exception as exc:
                    from synergesis_geo_model import GeoModelError
                    diagnostic = str(exc) if isinstance(exc,GeoModelError) else type(exc).__name__
                    print('Modèle non testé : '+diagnostic+' ; observations conservées.',flush=True)
            projection = syn.projection()
            if args.receipt:
                args.receipt.parent.mkdir(parents=True,exist_ok=True)
                args.receipt.write_text(json.dumps(projection,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            if args.serve:
                server = ProjectionServer(projection); server.start()
                print('Globe : http://127.0.0.1:5173/syn.html ; données locales : http://127.0.0.1:8765/api/observations',flush=True)
                print('Questionnez Syn ici. /quitter arrête proprement ; /actualiser effectue une lecture USGS autorisée.',flush=True)
                if args.interactive:
                    for _ in range(14):
                        line = input('Vous > ').strip()
                        if line == '/quitter': break
                        try:
                            if line == '/actualiser':
                                print(json.dumps(syn.collect(source,query),ensure_ascii=False))
                            elif line:
                                answer = syn.answer(line)
                                print('Syn > '+terminal_text(answer['text'])+'\nTrace : '+answer['cycle_glyph_id'])
                            server.update(syn.projection())
                        except Exception as exc:
                            print('Action arrêtée : '+type(exc).__name__+' ; aucune nouvelle tentative automatique.')
                else:
                    threading.Event().wait()
    except (KeyboardInterrupt,EOFError):
        print('Syn arrêté ; mémoire conservée.',flush=True)
    finally:
        if server: server.close()
        backend.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
