"""First bounded terminal conversation with Syn; demonstration is offline."""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import sys
import unicodedata

from synergesis_conversation import open_conversation


class DemoBackend:
    """Deterministic echo, deliberately not presented as a language model."""
    def reply(self, messages):
        return ("[Démonstration programmée, sans appel à un modèle] "
                "Syn a reçu : " + messages[-1]["content"] +
                "\nLe contrôle porte sur la remise de cette réponse, pas sur sa vérité.")


def terminal_text(text):
    """Do not let untrusted model text inject terminal escapes or bidi controls."""
    return ''.join(c for c in text if c in '\n\t' or not unicodedata.category(c).startswith('C'))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Première conversation texte bornée avec Syn")
    parser.add_argument('--provider', choices=('demo', 'openai', 'ollama'), default='demo')
    parser.add_argument('--model', help="Identifiant API ou nom exact du modèle installé dans Ollama")
    parser.add_argument('--port', type=int, help="Port Ollama sur 127.0.0.1 (défaut : 11434)")
    parser.add_argument('--output', type=Path, required=True, help="Nouveau dossier de journaux")
    parser.add_argument('--message', help="Un seul message, puis quitter")
    parser.add_argument('--max-turns', type=int, default=10)
    parser.add_argument('--profile', type=Path, help="Dossier persistant de souvenirs et questions explicites")
    parser.add_argument('--internet', action='store_true',
                        help="Autoriser /web SUJET : recherche arXiv en lecture seule")
    parser.add_argument('--document', action='append', type=Path, default=[],
                        help="Document .txt/.md autorisé pour /initiative (maximum 16)")
    args = parser.parse_args(argv)
    if args.internet and args.profile is None:
        parser.error('--internet nécessite --profile pour conserver les sources')
    if args.profile is not None and args.profile.expanduser().resolve() == args.output.expanduser().resolve():
        parser.error('Le profil et le dossier de session doivent être distincts')
    if args.document and args.profile is None:
        parser.error('--document nécessite --profile')
    if len(args.document) > 16:
        parser.error('Maximum 16 documents explicitement autorisés')
    if not 1 <= args.max_turns <= 20:
        parser.error('--max-turns doit être compris entre 1 et 20')
    if args.message is not None and (not args.message.strip() or len(args.message) > 8192):
        parser.error('Le message doit contenir entre 1 et 8192 caractères')
    if args.output.exists():
        parser.error('Le dossier de sortie doit être nouveau')
    if args.provider in ('openai', 'ollama') and (not args.model or not args.model.strip()):
        parser.error('--model est obligatoire avec --provider openai ou ollama')
    if args.provider == 'demo' and args.model is not None:
        parser.error('--model nécessite --provider openai ou ollama')
    if args.port is not None and args.provider != 'ollama':
        parser.error('--port nécessite --provider ollama')
    if sys.platform == 'win32':
        parser.error('Utiliser Linux, macOS ou Ubuntu dans WSL sous Windows')
    local_backend = None
    if args.provider == 'ollama':
        from synergesis_ollama_backend import OllamaBackend
        try:
            # Validate before creating a profile or session. No connection here.
            local_backend = OllamaBackend(args.model,
                port=args.port if args.port is not None else 11434,
                response_format=None, conversation=True, timeout=180)
        except ValueError:
            parser.error('Configuration Ollama invalide : modèle de 1 à 128 caractères, port de 1 à 65535')
    try:
        profile = None
        if args.profile is not None:
            from synergesis_initiative import InitiativeProfile
            profile = InitiativeProfile(args.profile)
            print('Profil persistant actif : souvenirs déclarés et questions.\n'
                  'Les souvenirs retrouvés seront transmis au modèle choisi.\n'
                  'Commandes : /memoriser TEXTE, /memoire MOTS, /question TEXTE, /initiative')
        if args.internet:
            print('Internet actif : /web SUJET recherche sur arXiv (résumés scientifiques).\n'
                  'Seul le texte de la requête est envoyé à arXiv, pas vos souvenirs.\n'
                  'Maximum trois recherches par session, partagées avec /initiative.')
        if args.provider == 'openai':
            from synergesis_responses_backend import OpenAIResponsesBackend
            print('Mode API OpenAI : les messages et leur historique seront envoyés au fournisseur.\n'
                  'Chaque tour appelle le modèle une fois ; les appels sont facturés par votre compte API.')
            api_key = os.environ.get('SYN_OPENAI_API_KEY')
            if not api_key:
                if not sys.stdin.isatty():
                    parser.error('SYN_OPENAI_API_KEY requis en mode non interactif')
                # Never fall back to an echoed password prompt.
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter('error', getpass.GetPassWarning)
                    api_key = getpass.getpass('Clé API neuve (saisie masquée, hors dépôt) : ')
            backend = OpenAIResponsesBackend(api_key, args.model, max_calls=args.max_turns)
            del api_key
        elif args.provider == 'ollama':
            backend = local_backend
            print('Mode Ollama : messages, historique et souvenirs retrouvés envoyés au serveur '
                  'sur 127.0.0.1.\n'
                  'Utiliser un modèle installé localement ; Syn ne télécharge aucun modèle '
                  'et ne demande aucune clé API.\n'
                  'Le modèle produit du texte ; les recherches /web sont déclenchées par vous.')
        else:
            backend = DemoBackend()
            print('Mode démonstration : réponse programmée, sans modèle ; /web utilise Internet.'
                  if args.internet else 'Mode démonstration : réponse programmée, sans modèle ni réseau.')
        print('Les échanges sont conservés dans les journaux locaux.\n'
              'REALITY vérifie la remise du texte au programme, pas sa véracité.\n'
              'Pour quitter : /quitter')
        with open_conversation(args.output, backend, max_turns=args.max_turns, profile=profile) as session:
            print('Dossier : ' + terminal_text(str(args.output.resolve())))
            turns = 0
            profile_commands = 0
            while True:
                if args.message is not None:
                    message = args.message
                else:
                    print('Vous > ', end='', flush=True)
                    line = sys.stdin.readline(8194)
                    if not line:
                        break
                    message = line.rstrip('\r\n')
                    if message.strip() in ('/quitter', '/exit'):
                        break
                    if not message.strip():
                        continue
                    if len(message) > 8192:
                        print('Message trop long : session terminée avant appel au modèle.')
                        return 1
                if message == '/web' or message.startswith('/web '):
                    if not args.internet:
                        print('Recherche désactivée : relancer avec --internet et --profile.')
                        if args.message is not None:
                            return 1
                        continue
                    if turns >= args.max_turns:
                        break
                    query = message.partition(' ')[2].strip()
                    if not query:
                        print('Usage : /web MOTS-CLÉS (arXiv, de préférence en anglais).')
                        if args.message is not None:
                            return 1
                        continue
                    result = profile.web_search(query)
                    print('Recherche arXiv : ' + result['status'] + '\nReçu : ' + result['receipt_id'])
                    for source in result['evidence']:
                        print(terminal_text(source['title'] + '\n' + source['path']
                              + '\nConsulté : ' + source['retrieved_at'] + '\n' + source['text']))
                    if result['status'] != 'evidence_found':
                        print('Source indisponible.' if result['status'] == 'failed'
                              else 'Aucun résultat pour ces mots-clés. Essayez une expression plus courte en anglais.')
                        if args.message is not None:
                            return 1 if result['status'] == 'failed' else 0
                        continue
                    message = ('Résume en français les extraits de la recherche suivante : ' + query
                        + '. Cite les URL présentes dans le contexte et distingue les hypothèses '
                          'des résultats. Les résumés arXiv ne prouvent pas que leurs conclusions sont vraies.')
                if message.startswith(('/memoriser ', '/memoire', '/question ', '/initiative')):
                    if profile is None:
                        raise ValueError('Ces commandes nécessitent --profile')
                    if profile_commands >= 32:
                        print('Limite de 32 commandes de profil atteinte : session terminée.')
                        break
                    import json
                    command, _, body = message.partition(' ')
                    if command == '/memoriser':
                        result = profile.remember(body)
                    elif command == '/memoire':
                        result = profile.recall(body)
                    elif command == '/question':
                        result = profile.add_question(body)
                    elif command == '/initiative' and not body.strip():
                        result = profile.step(args.document)
                    else:
                        raise ValueError('Commande de profil inconnue')
                    profile_commands += 1
                    print('Profil > ' + terminal_text(json.dumps(result, ensure_ascii=False, default=str)))
                    if args.message is not None:
                        break
                    continue
                if turns >= args.max_turns:
                    break
                receipt = session.turn(message)
                turns += 1
                print('Syn > ' + terminal_text(receipt['text']))
                for reference in receipt.get('source_references', []):
                    target = (reference['path'] + ':' + str(reference['line'])
                              if reference['kind'] in {'document', 'web'} else reference['id'])
                    print(terminal_text('Source fournie [' + reference['alias'] + '] : ' + target
                          + (' ; citée dans le texte' if reference['cited'] else ' ; non citée')))
                print('Trace : ' + terminal_text(receipt['cycle_glyph_id']))
                if args.message is not None:
                    break
        return 0
    except (KeyboardInterrupt, EOFError):
        print('\nSession arrêtée.')
        return 0
    except Exception:
        # Providers and filesystem errors may carry prompts, keys or response bodies.
        print('Session arrêtée sans nouvelle tentative automatique. Vérifiez la configuration, '
              'les limites et la disponibilité du modèle. Les traces déjà écrites restent dans le dossier.',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
