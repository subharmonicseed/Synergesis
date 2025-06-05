"""LLM backend abstractions."""
from __future__ import annotations

from typing import Any, Dict, Optional


class BaseLLM:
    """Abstract language model interface."""

    def generate(self, prompt: str, max_tokens: int, **kwargs: Any) -> str:  # pragma: no cover - base
        raise NotImplementedError


class StubLLM(BaseLLM):
    """Simple deterministic backend returning a fixed glyph JSON."""

    def generate(self, prompt: str, max_tokens: int, **kwargs: Any) -> str:
        return "[{\"id\": \"stub-glyph\", \"concept_type\": \"TEST\"}]"


class HFLocalLLM(BaseLLM):
    """Placeholder for a local HuggingFace model."""

    def __init__(self, model_name: str, **config: Any) -> None:
        self.model_name = model_name
        self.config = config
        # loading code would go here

    def generate(self, prompt: str, max_tokens: int, **kwargs: Any) -> str:  # pragma: no cover - stub
        # actual model inference should be implemented
        return ""


def get_llm(name: str, config: Optional[Dict[str, Any]] = None) -> BaseLLM:
    """Factory returning a backend instance."""
    if name == "stub":
        return StubLLM()
    if name == "hf_local":
        return HFLocalLLM(config.get("model_name", ""))
    raise ValueError(f"Unknown LLM backend: {name}")
