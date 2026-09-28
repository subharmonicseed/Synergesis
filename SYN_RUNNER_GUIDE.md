# Portable research runners

The historical stress and SYN-ROAM endurance runners now execute only when run as commands. Importing them and requesting `--help` have no experiment or filesystem side effects. Each accepts `--output PATH`; the path must not exist. If omitted, a unique temporary directory is created. Existing output is never recursively removed.

Install optional plotting dependencies first with `python -m pip install ".[runners]"`.
`--help` and importing the runners do not require those extras.

Run a local stress experiment from this directory, for example:

```sh
python run_syn_reality_state_stress.py --output ./results/reality-state
```

The archived long-run live-web corpus experiment requires its actual input file and will fail clearly if it is absent:

```sh
python run_syn_roam_live_web_longrun.py --corpus /path/to/live_web_corpus.json --output ./results/live-web
```

No corpus is bundled or synthesized here. The runner copies the supplied corpus into its new output folder before analyzing it.

An optional bounded Internet connectivity check is available as a separate, explicit command. It sends a read-only arXiv query through the existing `synergesis_live_sources` HTTPS allowlist, timeout, response-size, and polite-pacing policy. It requests at most three results, makes no retries or redirects, and writes results/cache only beneath its new output folder. It is not run by the tests.

```sh
python run_syn_live_source_smoke.py --query "robotics" --max-items 1 --output ./results/arxiv-smoke
```

Check its arguments without network access using `python run_syn_live_source_smoke.py --help`.
