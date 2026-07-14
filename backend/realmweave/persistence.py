"""Save and load the entire world to disk as JSON.

Captures the clock, world facts, every agent's dynamic state (position, needs,
health, relationships, current activity) and their full memory stream, so a
world can be resumed exactly where it left off. This is what makes "death has
lasting impact, no full restart" real across sessions: the dead stay dead and
everyone's memories survive a save/load cycle.

Format is a single versioned JSON document. Writes are atomic (temp file +
os.replace) so a crash mid-save can't corrupt an existing world.
"""
from __future__ import annotations
import json
import os

from .memory import MemoryEntry

SAVE_VERSION = 1


def save_world(sim, path: str) -> None:
    data = {
        "version": SAVE_VERSION,
        "clock_minutes": sim.clock.minutes,
        "tick_count": sim.tick_count,
        "world": {"weather": sim.world.weather, "rumors": list(sim.world.rumors)},
        "agents": {},
    }
    for aid, a in sim.agents.items():
        mem = a.memory.entries if a.memory else []
        data["agents"][aid] = {
            "x": a.x, "y": a.y,
            "health": a.health, "alive": a.alive,
            "activity": a.activity,
            "current_location": a.current_location,
            "target_location": a.target_location,
            "needs": {
                "energy": a.energy.value, "hunger": a.hunger.value,
                "thirst": a.thirst.value, "social": a.social.value,
            },
            "relationships": a.relationships,
            "say": a.say, "say_ttl": a.say_ttl,
            "memory": [
                {"text": e.text, "importance": e.importance, "created_at": e.created_at,
                 "last_accessed": e.last_accessed, "kind": e.kind}
                for e in mem
            ],
        }

    abspath = os.path.abspath(path)
    os.makedirs(os.path.dirname(abspath), exist_ok=True)
    tmp = abspath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, abspath)


def load_world(sim, path: str) -> bool:
    """Restore sim state in place. Returns False if no valid save exists."""
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("version") != SAVE_VERSION:
        return False

    sim.clock.minutes = int(data.get("clock_minutes", sim.clock.minutes))
    sim.tick_count = int(data.get("tick_count", 0))
    w = data.get("world", {})
    sim.world.weather = w.get("weather", sim.world.weather)
    sim.world.rumors = list(w.get("rumors", []))

    for aid, ad in data.get("agents", {}).items():
        a = sim.agents.get(aid)
        if not a:
            continue
        a.x, a.y = ad.get("x", a.x), ad.get("y", a.y)
        a.health = ad.get("health", a.health)
        a.alive = ad.get("alive", a.alive)
        a.activity = ad.get("activity", a.activity)
        a.current_location = ad.get("current_location", a.current_location)
        a.target_location = ad.get("target_location", a.target_location)
        needs = ad.get("needs", {})
        a.energy.value = needs.get("energy", a.energy.value)
        a.hunger.value = needs.get("hunger", a.hunger.value)
        a.thirst.value = needs.get("thirst", a.thirst.value)
        a.social.value = needs.get("social", a.social.value)
        a.relationships = {k: float(v) for k, v in ad.get("relationships", {}).items()}
        a.say = ad.get("say", "")
        a.say_ttl = int(ad.get("say_ttl", 0))
        if a.memory is not None:
            a.memory.entries = [
                MemoryEntry(
                    text=m["text"], importance=m["importance"],
                    created_at=m["created_at"],
                    last_accessed=m.get("last_accessed", m["created_at"]),
                    kind=m.get("kind", "observation"),
                )
                for m in ad.get("memory", [])
            ]
    return True
