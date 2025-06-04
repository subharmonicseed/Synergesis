# Synergesis v1.1 — light working pack
This bundle is a **clean, minimal set** of files you can drop in place of `syndump` to get the engine back up without the overhead.

## Files

| file | role |
|------|------|
| SynergesisCore_DeepSeek_Pro_Complete.py | minimal FastAPI stub |
| Synergesis_Complete_Compilation_v2.txt | consolidated reference |
| README.md | this guide |

## quick start

```bash
pip install --upgrade pip setuptools wheel
pip install numpy scipy scikit-learn qiskit spacy fastapi uvicorn
python SynergesisCore_DeepSeek_Pro_Complete.py
```

The first run will download the large English Spacy model automatically if it
isn't already installed.
You can also pre-install it manually with:
```bash
python -m spacy download en_core_web_lg
```

Once it says *"Uvicorn running..."* you can query `http://127.0.0.1:8000/docs` to test.
The file exposes a FastAPI application named `app` if you prefer launching `uvicorn` manually:

```bash
uvicorn SynergesisCore_DeepSeek_Pro_Complete:app --host 0.0.0.0 --reload
```
Press `Ctrl+C` to stop the server when you're done.

---
Need the full dashboard or glyph modules? Just ask and I'll package a heavier archive.

## troubleshooting

If the script fails because a module is missing, run this quick check:

```bash
python - <<'PY'
import importlib, pkg_resources
mods = ["numpy", "scipy", "scikit-learn", "qiskit", "spacy", "fastapi", "uvicorn"]
for m in mods:
    try:
        importlib.import_module(m if m != "scikit-learn" else "sklearn")
        print("OK", m)
    except Exception as e:
        print("MISSING", m, e)
PY
```

Then install any missing package with `pip install <name>`.
