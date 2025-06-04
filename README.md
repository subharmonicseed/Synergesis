# Synergesis v1.1 — light working pack
This bundle is a **clean, minimal set** of files you can drop in place of `syndump` to get the engine back up without the overhead.

## Files

| file | role |
|------|------|
| SynergesisCore_DeepSeek_Pro_Complete.py | core engine (FastAPI + algorithms) |
| Synergesis_Complete_Compilation_v2.txt | consolidated reference |
| README.md | this guide |

## quick start

```bash
pip install -r requirements.txt
uvicorn SynergesisCore_DeepSeek_Pro_Complete:SynergesisAPI(your_core).app
```

When Uvicorn starts you can browse to `http://127.0.0.1:8000/docs` to test the API.

---
Need the full dashboard or glyph modules? Just ask and I'll package a heavier archive.
