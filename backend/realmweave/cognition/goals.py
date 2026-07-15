"""Goals and their step-by-step plans.

A Goal is a self-set aim (open a shop, seek adventure, master a craft) with an
ordered list of Steps that decompose it into concrete, executable behaviour. A
Step completes when the agent has spent enough time doing the right activity in
the right place; when all steps complete, so does the goal. Everything here is
plain data that serializes cleanly for save/load.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Step:
    name: str            # human-readable ("save up coin")
    activity: str        # maps to a sim activity: work/socialize/visit/wander/chores
    location: str        # concrete location id the step happens at
    kind: str = "work"   # work | socialize | visit | wait  (how progress is measured)
    target: int = 3      # ticks of effort (or 1 for a visit) needed to complete
    progress: int = 0

    @property
    def done(self) -> bool:
        return self.progress >= self.target

    def to_dict(self) -> dict:
        return {"name": self.name, "activity": self.activity, "location": self.location,
                "kind": self.kind, "target": self.target, "progress": self.progress}

    @classmethod
    def from_dict(cls, d: dict) -> "Step":
        return cls(name=d["name"], activity=d["activity"], location=d["location"],
                   kind=d.get("kind", "work"), target=int(d.get("target", 3)),
                   progress=int(d.get("progress", 0)))


@dataclass
class Goal:
    kind: str
    description: str
    priority: float                 # 0..1, drives how strongly it competes with needs
    steps: List[Step] = field(default_factory=list)
    step_index: int = 0
    status: str = "active"          # active | complete | abandoned
    created_at: int = 0
    quest_id: str = ""              # set when this goal is a quest the agent took on

    @property
    def current_step(self) -> Optional[Step]:
        if self.status == "active" and 0 <= self.step_index < len(self.steps):
            return self.steps[self.step_index]
        return None

    def advance(self) -> bool:
        """Move to the next step. Returns True if the whole goal is now complete."""
        self.step_index += 1
        if self.step_index >= len(self.steps):
            self.status = "complete"
            return True
        return False

    def to_dict(self) -> dict:
        return {"kind": self.kind, "description": self.description, "priority": self.priority,
                "step_index": self.step_index, "status": self.status,
                "created_at": self.created_at, "quest_id": self.quest_id,
                "steps": [s.to_dict() for s in self.steps]}

    @classmethod
    def from_dict(cls, d: dict) -> "Goal":
        return cls(kind=d["kind"], description=d["description"], priority=float(d["priority"]),
                   steps=[Step.from_dict(s) for s in d.get("steps", [])],
                   step_index=int(d.get("step_index", 0)), status=d.get("status", "active"),
                   created_at=int(d.get("created_at", 0)), quest_id=d.get("quest_id", ""))
