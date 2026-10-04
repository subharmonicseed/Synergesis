#!/usr/bin/env bash
set -euo pipefail
umask 077
source_dir=/home/gabriel/Synergesis-LocalUI-final
python=/home/gabriel/syn-ollama51-venv/bin/python
profile=/home/gabriel/synergesis-ollama51/profil-utilisateur
root=/home/gabriel/synergesis-ollama51/interface-locale
expected=''
check_only=false
while (($#)); do
    case "$1" in
        --expected-manifest) expected="${2:?empreinte requise}"; shift 2 ;;
        --check) check_only=true; shift ;;
        *) printf 'Argument inconnu.\n' >&2; exit 1 ;;
    esac
done
if [[ ! -x "$python" || ! -d "$source_dir" ]]; then
    printf 'Installation Syn introuvable dans Ubuntu-24.04.\n' >&2
    exit 1
fi
cd -- "$source_dir"
if [[ -n "$expected" ]]; then
    [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || exit 1
    actual=$(sha256sum MANIFEST_SHA256.json)
    if [[ "${actual%% *}" != "$expected" ]]; then
        printf 'La version installée diffère des sources vérifiées.\n' >&2
        exit 1
    fi
fi
"$python" scripts/verify_manifest.py
if $check_only; then exit 0; fi
exec "$python" -m synergesis_ui --profile "$profile" --root "$root" \
    --model syn-mistral-import:latest --port 8765 --ollama-port 11434 --internet
