"""Identity, reputation, and crime records.

Reputation is tracked per faction (village, guard, and later bandits, temple).
Crimes are recorded only when witnessed; each record remembers who saw it, which
is what lets an alias hold until someone who saw your face recognizes you.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

FACTIONS = ["village", "guard", "bandits", "temple"]

# crime kind -> severity (1..3)
SEVERITY = {"theft": 1, "assault": 2, "murder": 3}


@dataclass
class CrimeRecord:
    perp_id: str
    kind: str
    severity: int
    victim_id: str
    witnesses: List[str]
    location: str
    at: int                 # world minutes
    resolved: bool = False

    def to_dict(self) -> dict:
        return {"perp_id": self.perp_id, "kind": self.kind, "severity": self.severity,
                "victim_id": self.victim_id, "witnesses": list(self.witnesses),
                "location": self.location, "at": self.at, "resolved": self.resolved}

    @classmethod
    def from_dict(cls, d: dict) -> "CrimeRecord":
        return cls(perp_id=d["perp_id"], kind=d["kind"], severity=int(d["severity"]),
                   victim_id=d.get("victim_id", ""), witnesses=list(d.get("witnesses", [])),
                   location=d.get("location", ""), at=int(d.get("at", 0)),
                   resolved=bool(d.get("resolved", False)))
