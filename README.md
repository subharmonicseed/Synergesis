# Synergesis v1.1 — light working pack
This repository provides a clean, minimal set of files. The script `SynergesisCore_DeepSeek_Pro_Complete.py` is a lightweight demo stub; the full Synergesis engine is not included.


## Files

| file | role |
|------|------|
| `SynergesisCore_DeepSeek_Pro_Complete.py` | minimal FastAPI stub |
| `Synergesis_Complete_Compilation_v2.txt` | consolidated reference |
| `README.md` | this guide |

## Quick start

```bash
# option A – installer les paquets directement
pip install --upgrade pip setuptools wheel
pip install numpy scipy scikit-learn qiskit spacy fastapi uvicorn

# option B – via requirements.txt (si présent)
# pip install -r requirements.txt

python SynergesisCore_DeepSeek_Pro_Complete.py
```

Running the script will start a Uvicorn server on port `8000`. The
application object is exposed as `app` so you can also launch Uvicorn
manually if you prefer.

> The first run will download the large English SpaCy model automatically.
> You can also pre-install it manually with:
>
> ```bash
> python -m spacy download en_core_web_lg
> ```

Once it says “Uvicorn running…” you can browse [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
Prefer launching with Uvicorn directly?

```bash
uvicorn SynergesisCore_DeepSeek_Pro_Complete:app --host 0.0.0.0 --reload
```

Press `Ctrl+C` to stop the server.

---

Need the full dashboard or glyph modules? Just ask and I’ll package a heavier archive.

## Troubleshooting

If the script fails because a module is missing, run:

```bash
python - <<'PY'
import importlib, pkg_resources, sys
mods = ["numpy","scipy","scikit-learn","qiskit","spacy","fastapi","uvicorn"]
for m in mods:
    pkg = "sklearn" if m=="scikit-learn" else m
    try:
        importlib.import_module(pkg)
        print("✅", m)
    except Exception as e:
        print("❌", m, "missing")
PY
```

Then install any missing package with `pip install <name>`.

## License

This project is licensed under the [MIT License](LICENSE).
