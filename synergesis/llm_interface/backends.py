from __future__ import annotations

import json
from typing import Any, Dict


class BaseLLM:
    """Minimal interface for LLM backends."""

    def __init__(self, **config: Any) -> None:
        self.config = config

    def generate(self, prompt: str, max_tokens: int = 256, **kwargs: Any) -> str:
        """Return a text completion for the given prompt."""
        raise NotImplementedError


class StubLLM(BaseLLM):
    """Simple backend that returns an empty JSON list."""

    def generate(self, prompt: str, max_tokens: int = 256, **kwargs: Any) -> str:
        return "[]"


class HFLocalLLM(BaseLLM):
    """Placeholder backend for HuggingFace local models."""

    def generate(self, prompt: str, max_tokens: int = 256, **kwargs: Any) -> str:
        # Real implementation would call a local model; return stubbed response.
        return "[]"


class TinyLLM(BaseLLM):
    """Deterministic backend used in tests."""

    def generate(self, prompt: str, max_tokens: int = 256, **kwargs: Any) -> str:
        # Echo a deterministic JSON payload regardless of the prompt.
        data = [
            {"id": "tiny-g1", "concept_type": "POTENTIAL_ACTION"},
            {"id": "tiny-g2", "concept_type": "MEMORY_TRACE"},
        ]
        return json.dumps(data)


def get_llm(name: str, **config: Any) -> BaseLLM:
    """Factory returning an LLM backend by name."""
    name = name.lower()
    if name == "tiny":
        return TinyLLM(**config)
    if name == "stub":
        return StubLLM(**config)
    if name == "hf_local":
        return HFLocalLLM(**config)
    raise ValueError(f"Unknown LLM backend: {name}")


__all__ = ["BaseLLM", "StubLLM", "HFLocalLLM", "TinyLLM", "get_llm"]
