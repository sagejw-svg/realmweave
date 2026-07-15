"""Multi-model LLM router.

Every generation request carries an `importance` and a `tier` hint. The router
maps that to a concrete model:

    reflex    -> tiny model  (ambient one-liners, background chatter)
    dialogue  -> mid model   (real conversations players will read)
    narrative -> strong model (deaths, betrayals, world-shaping moments;
                               may be a remote API model)

Behaviour is fully config-driven (see config.json). If Ollama is unreachable or
a model errors, the router transparently falls back to the deterministic stub so
the world never freezes. A remote/API backend for the `narrative` tier is
pluggable via `set_api_backend()` but off by default (local-first).
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Optional
import time

from .ollama_client import OllamaClient, OllamaUnavailable
from .stub import StubLLM


class Tier(str, Enum):
    REFLEX = "reflex"
    DIALOGUE = "dialogue"
    NARRATIVE = "narrative"


@dataclass
class LLMRequest:
    prompt: str
    system: str = ""
    importance: float = 3.0          # 0-10; drives tier selection if tier is None
    tier: Optional[Tier] = None
    temperature: float = 0.8
    num_predict: int = 120
    other: str = "friend"            # convenience for the stub
    meta: Optional[dict] = None


@dataclass
class LLMResponse:
    text: str
    tier: Tier
    model: str
    backend: str                     # "ollama" | "stub" | "api"
    latency_ms: int


# API backend signature: (request, model) -> str
ApiBackend = Callable[[LLMRequest, str], str]


class LLMRouter:
    def __init__(self, config: dict, ollama: Optional[OllamaClient] = None):
        self.cfg = config
        self.models: Dict[str, str] = config.get("models", {
            "reflex": "qwen2.5:1.5b",
            "dialogue": "qwen2.5:7b-instruct",
            "narrative": "qwen2.5:14b-instruct",
        })
        self.embed_model: str = config.get("embed_model", "nomic-embed-text")
        self.ollama = ollama or OllamaClient(host=config.get("ollama_host", "http://127.0.0.1:11434"))
        self.stub = StubLLM()
        self.force_stub: bool = bool(config.get("force_stub", False))
        self.api_backend: Optional[ApiBackend] = None
        # importance thresholds -> tier
        self.reflex_max = config.get("reflex_max_importance", 3.0)
        self.dialogue_max = config.get("dialogue_max_importance", 7.0)
        self._ollama_ok: Optional[bool] = None
        # optional remote API model (Claude / OpenAI-compatible / any endpoint),
        # applied to the configured tiers. Off unless config.api.enabled + a key.
        api_cfg = config.get("api", {}) or {}
        self.api_tiers = set(api_cfg.get("tiers", ["narrative"]))
        from .api_backend import make_api_backend
        backend = make_api_backend(api_cfg)
        if backend is not None:
            self.api_backend = backend

    # ---- configuration -------------------------------------------------
    def set_api_backend(self, backend: ApiBackend) -> None:
        self.api_backend = backend

    def choose_tier(self, req: LLMRequest) -> Tier:
        if req.tier is not None:
            return req.tier
        if req.importance <= self.reflex_max:
            return Tier.REFLEX
        if req.importance <= self.dialogue_max:
            return Tier.DIALOGUE
        return Tier.NARRATIVE

    def _ollama_available(self) -> bool:
        if self._ollama_ok is None:
            self._ollama_ok = (not self.force_stub) and self.ollama.available()
        return self._ollama_ok

    # ---- generation ----------------------------------------------------
    def generate(self, req: LLMRequest) -> LLMResponse:
        tier = self.choose_tier(req)
        model = self.models.get(tier.value, self.models.get("dialogue", "qwen2.5:7b-instruct"))
        t0 = time.time()

        # configured tiers may use a remote API backend (Claude / OpenAI / etc.)
        if self.api_backend is not None and tier.value in self.api_tiers:
            try:
                text = self.api_backend(req, model)
                if text:
                    return LLMResponse(text.strip(), tier, model, "api", int((time.time() - t0) * 1000))
            except Exception:
                pass  # fall through to local/stub

        if self._ollama_available():
            try:
                text = self.ollama.generate(
                    model=model, prompt=req.prompt, system=req.system or None,
                    temperature=req.temperature, num_predict=req.num_predict,
                )
                if text:
                    return LLMResponse(text, tier, model, "ollama", int((time.time() - t0) * 1000))
            except OllamaUnavailable:
                self._ollama_ok = False  # stop retrying this session

        text = self.stub.generate(req.prompt, req.system, other=req.other)
        return LLMResponse(text, tier, "stub", "stub", int((time.time() - t0) * 1000))

    # ---- embeddings ----------------------------------------------------
    def embedder(self):
        """Return an embed function, or None if embeddings unavailable."""
        if not self._ollama_available():
            return None

        def _embed(text: str):
            return self.ollama.embed(self.embed_model, text)
        return _embed
