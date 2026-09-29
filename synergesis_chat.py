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
        return ("[Démonstration programmée, sans IA ni réseau] "
                "Syn a reçu : " + messages[-1]["content"] +
                "\nLe contrôle porte sur la remise de cette réponse, pas sur sa vérité.")


def terminal_text(text):
    """Do not let untrusted model text inject terminal escapes or bidi controls."""
    return ''.join(c for c in text if c in '\n\t' or not unicodedata.category(c).startswith('C'))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Première conversation texte bornée avec Syn")
    parser.add_argument('--provider', choices=('demo', 'openai'), default='demo')
    parser.add_argument('--model', help="Identifiant du modèle disponible sur votre compte API")
    parser.add_argument('--output', type=Path, required=True, help="Nouveau dossier de journaux")
    parser.add_argument('--message', help="Un seul message, puis quitter")
    parser.add_argument('--max-turns', type=int, default=10)
    args = parser.parse_args(argv)
    if not 1 <= args.max_turns <= 20:
        parser.error('--max-turns doit être compris entre 1 et 20')
    if args.message is not None and (not args.message.strip() or len(args.message) > 8192):
        parser.error('Le message doit contenir entre 1 et 8192 caractères')
    if args.output.exists():
        parser.error('Le dossier de sortie doit être nouveau')
    if args.provider == 'openai' and not args.model:
        parser.error('--model est obligatoire avec --provider openai')
    if args.provider == 'demo' and args.model:
        parser.error('--model ne sert que pour --provider openai')
    if sys.platform == 'win32':
        parser.error('Utiliser Linux, macOS ou Ubuntu dans WSL sous Windows')
    try:
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
        else:
            backend = DemoBackend()
            print('Mode démonstration : réponse programmée, sans modèle ni réseau.')
        print('Les échanges sont conservés dans les journaux locaux.\n'
              'REALITY vérifie la remise du texte au programme, pas sa véracité.\n'
              'Pour quitter : /quitter')
        with open_conversation(args.output, backend, max_turns=args.max_turns) as session:
            print('Dossier : ' + terminal_text(str(args.output.resolve())))
            for _ in range(args.max_turns):
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
                        print('Message vide : session terminée.')
                        break
                    if len(message) > 8192:
                        print('Message trop long : session terminée avant appel au modèle.')
                        return 1
                receipt = session.turn(message)
                print('Syn > ' + terminal_text(receipt['text']))
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
