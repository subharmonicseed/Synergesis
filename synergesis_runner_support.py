"""Safe command-line helpers shared by the Synergesis research runners."""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile


def runner_parser(description: str, *, corpus: bool = False) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--output", type=Path, help="new output directory (must not already exist)")
    if corpus:
        parser.add_argument("--corpus", type=Path, required=True, help="path to the supplied corpus JSON")
    return parser


def fresh_output_dir(requested: Path | None, name: str) -> Path:
    if requested is None:
        return Path(tempfile.mkdtemp(prefix=f"{name}_"))
    path = requested.expanduser().resolve()
    if path.exists():
        raise FileExistsError(f"output path already exists; choose a fresh path: {path}")
    path.mkdir(parents=True)
    return path
