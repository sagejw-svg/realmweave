"""Personality traits: the stable core that makes agents diverge.

Seven traits on a 0..1 axis. They bias goal generation and the utility weights
that drive moment-to-moment choices, so two agents in identical circumstances
pursue different lives. Traits are seeded per authored agent and drift only
slowly (drift is out of scope for Phase 2; the hooks are here).
"""
from __future__ import annotations
from typing import Dict

TRAITS = ["ambition", "sociability", "caution", "greed", "loyalty", "curiosity", "industry"]
DEFAULT = 0.5

# Authored personalities for the Oakhollow cast. Anything unset defaults to 0.5.
_SEEDS: Dict[str, Dict[str, float]] = {
    # gruff, content tavernkeeper: social, not ambitious
    "bram": {"ambition": 0.25, "sociability": 0.8, "greed": 0.35, "industry": 0.55, "caution": 0.5, "curiosity": 0.3},
    # restless stable hand who dreams of riding off
    "isla": {"ambition": 0.8, "curiosity": 0.85, "caution": 0.2, "sociability": 0.4, "industry": 0.6},
    # ambitious smith who owes money and wants more
    "toft": {"ambition": 0.85, "greed": 0.75, "industry": 0.8, "sociability": 0.5, "caution": 0.35},
    # quiet, watchful sweeper who keeps to himself
    "wren": {"ambition": 0.3, "sociability": 0.25, "curiosity": 0.55, "caution": 0.7, "industry": 0.6},
    # practical, rooted farmer, content and dutiful
    "dora": {"ambition": 0.3, "industry": 0.8, "loyalty": 0.75, "curiosity": 0.35, "sociability": 0.45},
    # dutiful, wary gate guard
    "guard": {"ambition": 0.35, "loyalty": 0.85, "caution": 0.75, "sociability": 0.4, "industry": 0.6},
    # restless, curious errand child
    "wander": {"curiosity": 0.95, "sociability": 0.85, "ambition": 0.5, "caution": 0.2, "industry": 0.35},
    # curious, industrious herbalist and keeper of memory
    "elda": {"curiosity": 0.8, "industry": 0.75, "loyalty": 0.6, "caution": 0.55, "sociability": 0.4},
}


def seed_personality(agent_id: str) -> Dict[str, float]:
    p = {t: DEFAULT for t in TRAITS}
    p.update(_SEEDS.get(agent_id, {}))
    return p
