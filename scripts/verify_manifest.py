"""Check recorded source bytes without importing project modules."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
    errors = []
    for name, expected in manifest.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            errors.append(f'missing or invalid path: {name}')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f'hash mismatch: {name}')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'{len(manifest)} source manifest entries verified')


if __name__ == '__main__':
    main()
