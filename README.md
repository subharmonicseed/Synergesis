# Synergesis v1.1 — light working pack
This bundle is a **clean, minimal set** of files you can drop in place of `syndump` to get the engine back up without the overhead.

## Files

| file | role |
|------|------|
| SynergesisCore_DeepSeek_Pro_Complete.py | minimal FastAPI stub |
| Synergesis_Complete_Compilation_v2.txt | consolidated reference |
| README.md | this guide |

`Synergesis_Complete_Compilation_v2.txt` collects many earlier modules in one
place. It is meant for context only and **is not directly runnable**; parts of
the described system remain placeholders.

## quick start

```bash
pip install numpy qiskit scikit-learn spacy fastapi uvicorn
python SynergesisCore_DeepSeek_Pro_Complete.py
```

This script is only a basic stub of the full Synergesis engine. It runs a very
simple FastAPI application; advanced features described in the compilation file
are not implemented.

Once it says *"Uvicorn running..."* you can query `http://127.0.0.1:8000/docs` to test.
The file exposes a FastAPI application named `app` if you prefer launching `uvicorn` manually:

```bash
uvicorn SynergesisCore_DeepSeek_Pro_Complete:app --reload
```

---
Need the full dashboard or glyph modules? Just ask and I'll package a heavier archive.
