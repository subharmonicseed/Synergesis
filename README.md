# Synergesis v1.1 — light working pack
This bundle is a **clean, minimal set** of files you can drop in place of `syndump` to get the engine back up without the overhead.


## Files

| file | role |
|------|------|
| `SynergesisCore_DeepSeek_Pro_Complete.py` | minimal FastAPI stub |
| `Synergesis_Complete_Compilation_v2.txt`  | consolidated reference |
| `README.md`                              | this guide             |

## Quick start

```bash
# Option A – install packages directly
pip install --upgrade pip setuptools wheel
pip install numpy scipy scikit-learn qiskit spacy fastapi uvicorn

# Option B – via requirements.txt
pip install -r requirements.txt

python SynergesisCore_DeepSeek_Pro_Complete.py
```

The first run downloads the large English SpaCy model automatically.
You can also pre-install it:

```bash
python -m spacy download en_core_web_lg
```

Once you read **“Uvicorn running…”** browse [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
You can also launch manually:

```bash
uvicorn SynergesisCore_DeepSeek_Pro_Complete:app --host 0.0.0.0 --reload
```

Press `Ctrl +C` to stop the server.

---

Need the full dashboard or glyph modules? Just ask and I’ll package a heavier archive.

## Troubleshooting

```bash
python - <<'PY'
import importlib
mods = ["numpy","scipy","scikit-learn","qiskit","spacy","fastapi","uvicorn"]
for m in mods:
    try:
        importlib.import_module("sklearn" if m=="scikit-learn" else m)
        print("✅", m)
    except ModuleNotFoundError:
        print("❌", m, "missing")
PY
```

Install any missing package with `pip install <name>`.

### License

MIT — see [LICENSE](LICENSE).
