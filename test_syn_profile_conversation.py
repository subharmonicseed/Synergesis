import json
import pytest
from synergesis_conversation import open_conversation
from synergesis_initiative import InitiativeProfile


class Backend:
    def __init__(self): self.calls=[]
    def reply(self,messages):
        self.calls.append([dict(m) for m in messages])
        return 'Réponse contrôlée de test, sans prétention de vérité.'


def test_profile_restored_and_injected_without_auto_accepting_reply(tmp_path):
    profile=InitiativeProfile(tmp_path/'profile')
    ref=profile.remember('Le nom du projet est Synergesis.')
    profile.add_question('Comment vérifier les résultats de Synergesis ?')
    backend=Backend()
    restored=InitiativeProfile(tmp_path/'profile')
    with open_conversation(tmp_path/'session',backend,profile=restored) as session:
        session.turn('Quel est le nom du projet Synergesis ?')
        supplied=backend.calls[0][-1]['content']
        assert 'Le nom du projet est Synergesis.' in supplied
        assert 'non vérifiées' in supplied
        assert session._history[0]['content']=='Quel est le nom du projet Synergesis ?'
        contents=[g.content for g in session._stack.graph.ledger.glyphs()]
        assert any('retrieved_profile_context' in json.dumps(c) for c in contents)
    assert not restored.recall('Réponse contrôlée')


def test_oversized_injected_context_refused_before_model(tmp_path):
    class Profile:
        def packet(self,query): return {'text':'x'*4097}
    backend=Backend()
    with open_conversation(tmp_path/'session',backend,profile=Profile()) as session:
        with pytest.raises(ValueError,match='4096'):
            session.turn('Bonjour')
    assert not backend.calls


def test_cli_remembers_then_new_invocation_recalls(tmp_path,capsys):
    from synergesis_chat import main
    profile=tmp_path/'profile'
    assert main(['--profile',str(profile),'--output',str(tmp_path/'first'),
                 '--message','/memoriser Mon atelier est à Jarrie.'])==0
    assert main(['--profile',str(profile),'--output',str(tmp_path/'second'),
                 '--message','/memoire Jarrie'])==0
    output=capsys.readouterr().out
    assert 'Mon atelier est à Jarrie.' in output
    assert 'Syn >' not in output


def test_document_receipt_reaches_next_chat_after_restart(tmp_path):
    doc=tmp_path/'allowed.md'
    doc.write_text('QUOTA-EXEMPLE : le plafond est trois recherches locales.\n')
    profile=InitiativeProfile(tmp_path/'profile')
    qid=profile.add_question('QUOTA-EXEMPLE')
    result=profile.step([doc])
    assert result['status']=='evidence_found' and not result['solved']
    restored=InitiativeProfile(tmp_path/'profile')
    backend=Backend()
    with open_conversation(tmp_path/'session',backend,profile=restored) as session:
        session.turn('Explique QUOTA-EXEMPLE en citant la source disponible.')
    supplied=backend.calls[0][-1]['content']
    assert result['receipt_id'] in supplied
    assert result['evidence'][0]['sha256'] in supplied
    assert 'le plafond est trois recherches locales.' in supplied
    assert 'local_snapshot_unverified' in supplied


def test_long_valid_user_message_keeps_original_text_with_profile(tmp_path):
    backend=Backend()
    original='Quotas '+('x'*3000)
    with open_conversation(tmp_path/'session',backend,
                           profile=InitiativeProfile(tmp_path/'profile')) as session:
        session.turn(original)
        assert session._history[0]['content']==original
    assert original in backend.calls[0][-1]['content']
