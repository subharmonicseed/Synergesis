# Synergesis

Synergesis is a flat-module Python distribution for quantitative reasoning,
Glyph Protocol records, provenance, policy, and bounded source adapters. The
maintained modules are installed explicitly; the retired `SynergesisCore_DeepSeek_Pro_Complete.py`
prototype and one-off stress runners are not part of the advertised package API.

## Install

```bash
python -m pip install .
# Include the test-only tools when developing:
python -m pip install ".[test]"
```

For the dependency versions validated on CPython 3.12 / Linux:

```bash
python -m pip install -c constraints-py312.txt ".[test]"
```

The runtime dependencies are limited to the imports used by the maintained
modules: NumPy, FastAPI (for the compatibility API modules), Requests,
Psutil, and Cryptography. JSON Schema, Pytest and HTTPX are test extras.

## Agent stack

The integrated agent stack is assembled with
`synergesis_secure_roam_stack_v2.build_secure_roam_reality_stack`.
Its caller must supply reasoning/planning providers, executors, identity and
capability stores, observation policies, reality probes and source adapters.
Installing the package does not start an agent or grant network/action access.
`test_synergesis_secure_roam_stack_v2.py` contains executable integration examples.

Persistent journals generally require a single writer. The risk-budget journal
now serializes cooperating readers/writers on a local POSIX filesystem; this does
not make a shared Glyph graph or the full stack safe for concurrent writers.
Risk-budget locking requires POSIX `fcntl` (native Windows is unsupported); use
spawned workers, not inherited fork state. See `SYN_RISK_CONCURRENCY_VALIDATION.md`.
Keep an intact backup before upgrading; recovery is not an atomic multi-store
transaction or a guarantee against power loss.
The restoration and hardening branches are review drafts, not a released service.

## Use the maintained API

The quantitative and symbolic building blocks are ordinary flat-module imports:

```python
from synergesis_production import build_topology, fuse_glyphs_production
```

`synergesis_canonical` and `synergesis_production` are explicit-data builders;
they do not provide an agent, language model, or autonomous decision service.
For applications that already import the FastAPI compatibility modules, run the
compatibility boundary with an explicitly installed ASGI server:

```bash
python -m pip install uvicorn
python -m uvicorn SynergesisCore_Production:app --host 127.0.0.1
```

`SynergesisCore_MathVerified:app` remains available for the verified quantum
compatibility endpoints. Neither compatibility module is a claim that the
retired prototype is a production implementation.

## Tests

From a checkout, run:

```bash
python -m pip install ".[test]"
python -m pytest -q
```

The CI workflow is configured for Python 3.11 and 3.12. Its remote result must
be checked on the pull request; local validation is not a CI receipt.
