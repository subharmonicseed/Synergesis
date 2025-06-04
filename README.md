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
pip install numpy pandas qiskit spacy fastapi uvicorn
python SynergesisCore_DeepSeek_Pro_Complete.py
```

Once it says *"Uvicorn running..."* you can query `http://127.0.0.1:8000/docs` to test.
The file exposes a FastAPI application named `app` if you prefer launching `uvicorn` manually:

```bash
uvicorn SynergesisCore_DeepSeek_Pro_Complete:app --reload
```

---
Need the full dashboard or glyph modules? Just ask and I'll package a heavier archive.
