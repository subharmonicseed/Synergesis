# Synergesis v1.1 — light working pack
This bundle is a **clean, minimal set** of files you can drop in place of `syndump` to get the engine back up without the overhead.

## Files

| file | role |
|------|------|
| SynergesisCore_DeepSeek_Pro_Complete.py | minimal FastAPI stub |
| Synergesis_Complete_Compilation_v2.txt | consolidated reference (not runnable) |
| README.md | this guide |
| [docs/architecture_v8.md](docs/architecture_v8.md) | architecture overview |
| [docs/glyph_schema.md](docs/glyph_schema.md) | glyph specification (WIP) |

The architecture document explains how each "agent" of Synergesis is implemented
as a Python class within its module rather than as a standalone service. It
provides the full directory tree and the role of every file.

## quick start

```bash
pip install -r requirements.txt

python SynergesisCore_DeepSeek_Pro_Complete.py
python scripts/run_agent_loop.py
```

The script only launches a very small demo API. Once it says *"Uvicorn running..."*
you can query `http://127.0.0.1:8000/docs` to test.

If you prefer to start Uvicorn manually, the file exposes an application named
`app`:

```bash
uvicorn SynergesisCore_DeepSeek_Pro_Complete:app --reload
```

---
Need the full dashboard or glyph modules? Just ask and I'll package a heavier archive.

## License
This project is licensed under the [MIT License](LICENSE).

## Contributing
Please ensure the test suite runs before opening a pull request:

```bash
pytest
```

