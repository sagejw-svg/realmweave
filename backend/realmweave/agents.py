"""Agents (NPCs): autonomy, daily routines, needs, relationships, mortality.

An agent decides what to do each tick from three inputs, in priority order:
  1. Survival needs that have crossed a threshold (sleep, eat, drink).
  2. Their scheduled routine for the current time of day.
  3. Opportunistic social behaviour when co-located with others.

Movement is simple 2D steering toward the target location. When an agent
performs an activity it mutates its needs and may emit observations into memory
and events onto the sim bus. Death is permanent: a dead agent stops acting, but
its memory and others' memories of it persist (lasting impact, no restart).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math

from .memory import MemoryStream


@dataclass
class Need:
    value: float = 0.6      # 0 (empty/desperate) .. 1 (fully satisfied)
    decay: float = 0.02     # per tick

    def tick(self) -> None:
        self.value = max(0.0, self.value - self.decay)

    def satisfy(self, amount: float) -> None:
        self.value = min(1.0, self.value + amount)


@dataclass
class ScheduleBlock:
    start_hour: int
    activity: str            # sleep, work, eat, socialize, patrol, chores, wander
    location: str

    def to_dict(self) -> dict:
        return {"start_hour": self.start_hour, "activity": self.activity, "location": self.location}


@dataclass
class Agent:
    id: str
    name: str
    role: str
    home: str
    workplace: str
    x: float
    y: float
    schedule: List[ScheduleBlock] = field(default_factory=list)
    speed: float = 1.6
    # needs
    energy: Need = field(default_factory=lambda: Need(0.8, 0.010))
    hunger: Need = field(default_factory=lambda: Need(0.7, 0.015))
    thirst: Need = field(default_factory=lambda: Need(0.7, 0.020))
    social: Need = field(default_factory=lambda: Need(0.6, 0.008))
    # state
    health: float = 1.0
    alive: bool = True
    activity: str = "idle"
    target_location: str = ""
    current_location: str = ""
    say: str = ""            # last spoken line (for client display)
    say_ttl: int = 0
    relationships: Dict[str, float] = field(default_factory=dict)  # id -> affinity -1..1
    persona: str = ""        # short character brief fed to the LLM
    memory: Optional[MemoryStream] = None
    sheet: Optional["CharacterSheet"] = None  # rules character sheet (skills 1-100)
    personality: Dict[str, float] = field(default_factory=dict)  # cognition traits 0..1
    goal: Optional["Goal"] = None                                # current self-set aim
    coin: int = 0                                                # money
    inventory: List = field(default_factory=list)               # List[economy.Item]
    god_disposition: float = 0.0                                 # feeling toward the god -1..1

    # ---- scheduling ----------------------------------------------------
    def scheduled_block(self, hour: int) -> ScheduleBlock:
        best = self.schedule[0] if self.schedule else ScheduleBlock(0, "wander", self.home)
        for b in self.schedule:
            if b.start_hour <= hour:
                best = b
        # wrap: if earliest block starts after current hour, use last block (previous day)
        if self.schedule and hour < self.schedule[0].start_hour:
            best = self.schedule[-1]
        return best

    # ---- needs / decisions --------------------------------------------
    def urgent_need(self) -> Optional[Tuple[str, str]]:
        """Return (activity, location) if a survival need overrides routine."""
        if self.energy.value < 0.15:
            return ("sleep", self.home)
        if self.thirst.value < 0.15:
            return ("drink", "well")
        if self.hunger.value < 0.15:
            return ("eat", "tavern")
        return None

    def affinity(self, other_id: str) -> float:
        return self.relationships.get(other_id, 0.0)

    def adjust_affinity(self, other_id: str, delta: float) -> None:
        v = self.relationships.get(other_id, 0.0) + delta
        self.relationships[other_id] = max(-1.0, min(1.0, v))

    # ---- movement ------------------------------------------------------
    def step_toward(self, tx: float, ty: float) -> bool:
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist <= self.speed:
            self.x, self.y = tx, ty
            return True
        self.x += self.speed * dx / dist
        self.y += self.speed * dy / dist
        return False

    def speak(self, text: str, ttl: int = 6) -> None:
        self.say = text
        self.say_ttl = ttl

    def tick_needs(self) -> None:
        for n in (self.energy, self.hunger, self.thirst, self.social):
            n.tick()

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "role": self.role,
            "x": round(self.x, 2), "y": round(self.y, 2),
            "activity": self.activity, "alive": self.alive, "health": round(self.health, 2),
            "location": self.current_location, "target": self.target_location,
            "say": self.say if self.say_ttl > 0 else "",
            "needs": {
                "energy": round(self.energy.value, 2),
                "hunger": round(self.hunger.value, 2),
                "thirst": round(self.thirst.value, 2),
                "social": round(self.social.value, 2),
            },
            "char_class": self.sheet.emergent_class() if self.sheet else "",
            "top_skills": self.sheet.top_skills(3) if self.sheet else [],
            "goal": self.goal.description if self.goal else "",
            "goal_step": (self.goal.current_step.name if (self.goal and self.goal.current_step) else ""),
            "coin": self.coin,
            "disposition": round(self.god_disposition, 2),
        }


# ---- authored cast for Oakhollow --------------------------------------
def default_agents() -> List[Agent]:
    def sched(*blocks):
        return [ScheduleBlock(h, a, l) for (h, a, l) in blocks]

    cast = [
        Agent("bram", "Bram Cask", "Tavernkeeper", "home_bram", "tavern", 20, 18,
              persona="Gruff but kind tavernkeeper of the Gilded Stag. Proud of his ale, secretly lonely.",
              schedule=sched((0, "sleep", "home_bram"), (6, "chores", "tavern_kitchen"),
                             (8, "work", "tavern"), (13, "eat", "tavern_kitchen"),
                             (14, "work", "tavern"), (23, "sleep", "home_bram"))),
        Agent("isla", "Isla Fenn", "Stable hand", "home_isla", "stable", 46, 20,
              persona="Wiry young stable hand who loves horses more than people. Dreams of riding off.",
              schedule=sched((0, "sleep", "home_isla"), (5, "work", "stable"),
                             (12, "eat", "tavern"), (13, "work", "stable"),
                             (19, "socialize", "tavern"), (22, "sleep", "home_isla"))),
        Agent("toft", "Toft Bellow", "Blacksmith", "home_toft", "smithy", 44, 30,
              persona="Barrel-chested smith with a booming laugh and a bad knee. Owes Bram money.",
              schedule=sched((0, "sleep", "home_toft"), (7, "work", "smithy"),
                             (12, "eat", "tavern"), (13, "work", "smithy"),
                             (20, "socialize", "tavern"), (23, "sleep", "home_toft"))),
        Agent("wren", "Wren Pallet", "Street sweeper", "home_wren", "square", 24, 34,
              persona="Observant, quiet street sweeper who knows everyone's business and says little.",
              schedule=sched((0, "sleep", "home_wren"), (6, "chores", "square"),
                             (11, "chores", "well"), (13, "eat", "tavern"),
                             (14, "chores", "square"), (21, "socialize", "tavern"),
                             (23, "sleep", "home_wren"))),
        Agent("dora", "Dora Meel", "Farmer", "home_dora", "field", 38, 10,
              persona="Weathered farmer, blunt and practical, feeds half the village. Watches the weather.",
              schedule=sched((0, "sleep", "home_dora"), (5, "work", "field"),
                             (12, "eat", "tavern"), (13, "work", "field"),
                             (19, "socialize", "tavern"), (21, "sleep", "home_dora"))),
        Agent("guard", "Sergeant Hale", "Gate guard", "gate", "gate", 32, 44,
              persona="Dutiful, weary gate guard. Seen enough to distrust strangers, kind to locals.",
              schedule=sched((0, "patrol", "gate"), (6, "patrol", "square"),
                             (12, "eat", "tavern"), (13, "patrol", "gate"),
                             (20, "socialize", "tavern"), (23, "sleep", "gate"))),
        Agent("wander", "Pip Thorne", "Errand child", "home_wren", "square", 32, 24,
              persona="Restless kid who runs errands and gossip between everyone. Curious to a fault.",
              speed=2.2,
              schedule=sched((0, "sleep", "home_wren"), (7, "wander", "square"),
                             (12, "eat", "tavern"), (13, "wander", "stable"),
                             (16, "wander", "smithy"), (19, "wander", "square"),
                             (21, "sleep", "home_wren"))),
        Agent("elda", "Elda Marsh", "Herbalist", "home_dora", "well", 30, 30,
              persona="Old herbalist and healer. Speaks in riddles, trades remedies, remembers the dead.",
              schedule=sched((0, "sleep", "home_dora"), (7, "chores", "well"),
                             (10, "wander", "field"), (13, "eat", "tavern"),
                             (15, "chores", "square"), (20, "socialize", "tavern"),
                             (22, "sleep", "home_dora"))),
    ]
    # seed a few relationships
    cast_by = {a.id: a for a in cast}
    cast_by["bram"].adjust_affinity("toft", 0.3)
    cast_by["toft"].adjust_affinity("bram", 0.2)
    cast_by["isla"].adjust_affinity("dora", 0.4)
    cast_by["dora"].adjust_affinity("isla", 0.4)
    cast_by["wren"].adjust_affinity("elda", 0.3)
    return cast
