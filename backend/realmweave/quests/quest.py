"""Quests: opportunities in the world, spanning one or more domains.

A Quest is a titled objective with steps, a reward, and a status. Crucially, a
quest is an *opportunity*, not an order: agents evaluate it against their own
personality and may ignore it (see board.interest). Players can take and complete
quests for coin and skill. Objectives reuse the cognition Step so the existing
goal loop can execute a quest with no special-casing.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

from ..cognition.goals import Step


@dataclass
class Quest:
    id: str
    title: str
    description: str
    domains: List[str]                 # e.g. ["Combat", "Exploration"]
    giver_id: str                      # agent id who posted it, or "" for the world
    objectives: List[Step]
    reward_coin: int
    reward_skill: str
    reward_amount: int
    status: str = "open"               # open | active | completed | expired
    taker_id: str = ""                 # agent id or "player:Name"
    created_at: int = 0

    def fresh_objectives(self) -> List[Step]:
        """A clean copy of the objectives (progress reset) for a taker to work."""
        return [Step(name=o.name, activity=o.activity, location=o.location,
                     kind=o.kind, target=o.target, progress=0) for o in self.objectives]

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "description": self.description,
                "domains": list(self.domains), "giver_id": self.giver_id,
                "objectives": [o.to_dict() for o in self.objectives],
                "reward_coin": self.reward_coin, "reward_skill": self.reward_skill,
                "reward_amount": self.reward_amount, "status": self.status,
                "taker_id": self.taker_id, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict) -> "Quest":
        return cls(id=d["id"], title=d["title"], description=d["description"],
                   domains=list(d.get("domains", [])), giver_id=d.get("giver_id", ""),
                   objectives=[Step.from_dict(o) for o in d.get("objectives", [])],
                   reward_coin=int(d["reward_coin"]), reward_skill=d["reward_skill"],
                   reward_amount=int(d["reward_amount"]), status=d.get("status", "open"),
                   taker_id=d.get("taker_id", ""), created_at=int(d.get("created_at", 0)))


# Authored quest templates. Each is a pool the board draws from to seed and to
# generate emergent quests. Steps reference existing world location ids.
# tuple form: (name, activity, location, kind, target)
QUEST_TEMPLATES = [
    {
        "key": "north_road", "title": "Clear the North Road",
        "description": "Travelers say bandits haunt the road north. Someone bold should drive them off.",
        "domains": ["Combat", "Exploration"],
        "steps": [("scout from the gate", "visit", "gate", "visit", 1),
                  ("range into the north fields", "visit", "field", "visit", 1),
                  ("hold the line a while", "wait", "field", "wait", 3)],
        "coin": 70, "skill": "Blades", "amount": 3,
    },
    {
        "key": "caravan", "title": "Escort the Caravan",
        "description": "A trade caravan needs guards from the gate through the square and back.",
        "domains": ["Trade", "Combat", "Exploration"],
        "steps": [("meet the caravan at the gate", "visit", "gate", "visit", 1),
                  ("guard it through the square", "wait", "square", "wait", 2),
                  ("see it safely out the gate", "visit", "gate", "visit", 1)],
        "coin": 90, "skill": "Tactics", "amount": 3,
    },
    {
        "key": "herbs", "title": "Gather Healing Herbs",
        "description": "The herbalist needs fresh herbs from the fields and water from the well.",
        "domains": ["Survival", "Craft"],
        "steps": [("forage in the fields", "visit", "field", "visit", 1),
                  ("draw water at the well", "wait", "well", "wait", 2)],
        "coin": 40, "skill": "Herbalism", "amount": 3,
    },
    {
        "key": "supply_stag", "title": "Supply the Gilded Stag",
        "description": "Bram needs wares brought from the smithy to the tavern.",
        "domains": ["Trade"],
        "steps": [("collect goods at the smithy", "visit", "smithy", "visit", 1),
                  ("deliver them to the tavern", "visit", "tavern", "visit", 1)],
        "coin": 45, "skill": "Bargaining", "amount": 3,
    },
    {
        "key": "quarrel", "title": "Mend a Quarrel",
        "description": "Two villagers are at odds. Smooth it over at the tavern.",
        "domains": ["Social"],
        "steps": [("go to the tavern", "visit", "tavern", "visit", 1),
                  ("talk it through", "socialize", "tavern", "socialize", 3)],
        "coin": 35, "skill": "Persuasion", "amount": 3,
    },
]
