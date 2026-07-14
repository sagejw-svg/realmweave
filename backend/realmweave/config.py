"""Load Realmweave configuration from config.json (with sane defaults)."""
from __future__ import annotations
import json
import os
from typing import Any, Dict

_DEFAULT: Dict[str, Any] = {
    "ollama_host": "http://127.0.0.1:11434",
    "force_stub": False,
    "embed_model": "nomic-embed-text",
    "models": {
        "reflex": "qwen2.5:1.5b-instruct",
        "dialogue": "qwen2.5:7b-instruct",
        "narrative": "qwen2.5:14b-instruct",
    },
    "reflex_max_importance": 3.0,
    "dialogue_max_importance": 7.0,
    "sim": {"minutes_per_tick": 10, "seed": 7, "social_chance": 0.5, "reflection_interval": 720},
    "server": {"host": "127.0.0.1", "port": 8765, "broadcast_hz": 4, "ticks_per_second": 8},
}


def load_config(path: str = "") -> Dict[str, Any]:
    cfg = json.loads(json.dumps(_DEFAULT))  # deep copy
    path = path or os.environ.get("REALMWEAVE_CONFIG", "")
    if not path:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(here, "config.json")
        if os.path.exists(candidate):
            path = candidate
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
        _deep_merge(cfg, user)
    if os.environ.get("REALMWEAVE_FORCE_STUB") == "1":
        cfg["force_stub"] = True
    return cfg


def _deep_merge(base: dict, over: dict) -> None:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
