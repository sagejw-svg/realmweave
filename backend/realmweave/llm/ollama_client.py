"""Minimal Ollama HTTP client using only the standard library.

Talks to a local Ollama server (default http://127.0.0.1:11434). Supports
/api/generate (completion) and /api/embeddings. Raises OllamaUnavailable on
any connection/HTTP problem so callers can fall back to the stub.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import List, Optional


class OllamaUnavailable(Exception):
    pass


class OllamaClient:
    def __init__(self, host: str = "http://127.0.0.1:11434", timeout: float = 60.0):
        self.host = host.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.host}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
            raise OllamaUnavailable(str(e)) from e

    def generate(self, model: str, prompt: str, system: Optional[str] = None,
                 temperature: float = 0.8, num_predict: int = 120,
                 stop: Optional[List[str]] = None) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        if system:
            payload["system"] = system
        if stop:
            payload["options"]["stop"] = stop
        out = self._post("/api/generate", payload)
        return (out.get("response") or "").strip()

    def embed(self, model: str, text: str) -> List[float]:
        out = self._post("/api/embeddings", {"model": model, "prompt": text})
        return out.get("embedding", [])

    def available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                resp.read()
            return True
        except Exception:
            return False
