"""Optional remote-API LLM backend (Claude, OpenAI-compatible, or any endpoint).

Realmweave is local-first: by default it uses Ollama with the GPU-free stub as a
fallback. But a player can bring their own model, including a hosted one, by
enabling the `api` block in config.json. This wires that block into an
ApiBackend the router uses for the chosen tiers (deaths, big moments by default).

The key is read from an environment variable, never stored in the repo or save.
Stdlib only (urllib) so nothing extra needs installing.
"""
from __future__ import annotations
import json
import os
import urllib.request
from typing import Callable, Optional


def make_api_backend(api_cfg: Optional[dict]) -> Optional[Callable]:
    """Return an ApiBackend callable (request, model)->str, or None if the API
    is disabled or not configured (missing key or model)."""
    if not api_cfg or not api_cfg.get("enabled"):
        return None
    provider = (api_cfg.get("provider") or "anthropic").lower()
    model = api_cfg.get("model") or ""
    key = os.environ.get(api_cfg.get("api_key_env", "ANTHROPIC_API_KEY"), "")
    base = api_cfg.get("base_url") or ""
    timeout = float(api_cfg.get("timeout", 60))
    if not model or not key:
        return None

    def _post(url: str, body: dict, headers: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def backend(request, _tier_model: str) -> str:
        system = request.system or ""
        prompt = request.prompt
        max_tokens = request.num_predict or 120
        if provider == "anthropic":
            url = base or "https://api.anthropic.com/v1/messages"
            out = _post(url,
                        {"model": model, "max_tokens": max_tokens, "system": system,
                         "messages": [{"role": "user", "content": prompt}]},
                        {"x-api-key": key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"})
            return "".join(p.get("text", "") for p in out.get("content", [])).strip()
        # openai-compatible (OpenAI, OpenRouter, local gateways, etc.)
        url = (base or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        out = _post(url,
                    {"model": model, "max_tokens": max_tokens,
                     "messages": [{"role": "system", "content": system},
                                  {"role": "user", "content": prompt}]},
                    {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        return (out["choices"][0]["message"]["content"] or "").strip()

    return backend
