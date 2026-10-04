"""Regression tests for routing and citations; no real model inference claimed."""
import hashlib
from pathlib import Path
import pytest
from synergesis_conversation import open_conversation
from synergesis_initiative import InitiativeProfile
from synergesis_ollama_backend import OllamaBackend

class RecordingUnitBackend:
    def __init__(self, reply='unit response'): self.calls=[]; self.text=reply
    def reply(self,messages):
        self.calls.append(messages)
        return self.text

@pytest.mark.parametrize('message', ['bonjour Syn', 'Pourquoi le ciel est-il bleu ?'])
def test_unrelated_profile_does_not_constrain_ordinary_dialogue(tmp_path,message):
    profile=InitiativeProfile(tmp_path/'profile')
    profile.remember('Mon atelier est à Jarrie.')
    profile.add_question('Noto earthquake')
    before=profile.path.read_bytes()
    backend=RecordingUnitBackend()
    with open_conversation(tmp_path/'session',backend,profile=profile) as session:
        result=session.turn(message)
    assert backend.calls[0]==[{'role':'user','content':message}]
    assert result['source_references']==[]
    assert profile.path.read_bytes()==before

def test_citation_resolves_to_actual_file_and_persisted_receipt(tmp_path):
    doc=tmp_path/'fiche.md'
    doc.write_text('FICTIF-Z : code CORAIL-721.\n',encoding='utf-8')
    profile=InitiativeProfile(tmp_path/'profile')
    profile.add_question('FICTIF-Z')
    searched=profile.step([doc])
    backend=RecordingUnitBackend('CORAIL-721 [D1]')
    with open_conversation(tmp_path/'new-session',backend,
                           profile=InitiativeProfile(tmp_path/'profile')) as session:
        result=session.turn('Quel code pour FICTIF-Z ?')
    reference=result['source_references'][0]
    assert reference['cited'] and reference['alias']=='D1'
    assert reference['path']==str(doc) and reference['line']==1
    assert reference['sha256']==hashlib.sha256(doc.read_bytes()).hexdigest()
    assert reference['receipt_id']==searched['receipt_id']
    assert 'CORAIL-721' in backend.calls[0][-1]['content']

def test_failed_search_is_supplied_as_failed_not_absence_of_fact(tmp_path):
    profile=InitiativeProfile(tmp_path/'profile')
    profile.add_question('objet KORAIL')
    assert profile.step([tmp_path/'missing.md'])['status']=='failed'
    backend=RecordingUnitBackend()
    with open_conversation(tmp_path/'session',backend,profile=profile) as session:
        result=session.turn('objet KORAIL')
    assert 'failed' in backend.calls[0][-1]['content']
    assert result['source_references']==[]

def test_web_citation_keeps_remote_hash_scope_and_source_label(tmp_path):
    class ControlledResearch:
        def search(self,query):
            return [{'path':'https://arxiv.org/abs/2401.12345v1','line':1,
                     'title':'Controlled source','text':'quantum controlled abstract',
                     'sha256':'a'*64,'hash_scope':'stored_excerpt_utf8',
                     'retrieved_at':'2026-10-04T00:00:00Z',
                     'claim_status':'remote_abstract_unverified'}]
    profile=InitiativeProfile(tmp_path/'profile')
    profile._web_research=ControlledResearch()
    profile.web_search('quantum')
    backend=RecordingUnitBackend('controlled [W1]')
    with open_conversation(tmp_path/'session',backend,profile=profile) as session:
        result=session.turn('quantum')
    reference=result['source_references'][0]
    assert reference['kind']=='web' and reference['cited']
    assert reference['claim_status']=='remote_abstract_unverified'
    assert reference['hash_scope']=='stored_excerpt_utf8'
    assert 'Controlled source' in backend.calls[0][-1]['content']
    assert 'local_snapshot_unverified' not in backend.calls[0][-1]['content']

def test_longer_cpu_timeout_only_for_explicit_text_conversation():
    assert OllamaBackend('test',conversation=True,response_format=None,timeout=180).timeout==180
    for kwargs in ({'timeout':61},{'conversation':True,'response_format':None,'timeout':181},
                   {'conversation':True}):
        with pytest.raises(ValueError): OllamaBackend('test',**kwargs)

def test_sources_do_not_reuse_aliases_across_different_turns(tmp_path):
    profile=InitiativeProfile(tmp_path/'profile')
    for key in ('ALPHA', 'BETA'):
        doc=tmp_path/(key+'.md')
        doc.write_text(key+' : fait fictif.\n')
        profile.add_question(key)
        profile.step([doc])
    backend=RecordingUnitBackend()
    with open_conversation(tmp_path/'session',backend,profile=profile) as session:
        first=session.turn('ALPHA')
        second=session.turn('BETA')
        again=session.turn('ALPHA')
    assert first['source_references'][0]['alias']=='D1'
    assert second['source_references'][0]['alias']=='D2'
    assert again['source_references'][0]['alias']=='D1'
