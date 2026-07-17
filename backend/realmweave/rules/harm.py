"""Harm and wounds: the shared currency for combat, accidents, and hazards.

A Wound is a lasting hurt with a severity. Wounds do two things: they penalize
physical action (a situational check modifier) and they weigh on health, so an
untreated grave wound can tip an agent toward the existing mortality path
(sim._mortality) rather than a separate death system. Wounds mend over time,
faster with rest or care.

Severity is set by the DEGREE of the resolving check, never a damage roll, so
everything stays on the one d100 spine (rules/checks.py) and reproducible with a
seed. This module is pure data + pure functions; the sim wires it into health,
healing, and death.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

from .checks import Outcome


class Severity(IntEnum):
    GRAZE = 1
    HURT = 2
    GRAVE = 3


# Per-wound physical-check penalty (subtracted from effective skill).
_PENALTY = {Severity.GRAZE: 4, Severity.HURT: 12, Severity.GRAVE: 28}

# Natural mend progress added per tick (0..1 accumulates; at >=1 the wound closes).
_MEND_PER_TICK = {Severity.GRAZE: 0.08, Severity.HURT: 0.03, Severity.GRAVE: 0.01}

# Health bled per tick by an open wound. A grave wound bleeds faster than natural
# regen (0.03 in sim), so left untreated it is genuinely dangerous; a hurt wound
# is survivable but slows recovery; a graze costs nothing but a check penalty.
_HEALTH_BLEED = {Severity.GRAZE: 0.0, Severity.HURT: 0.008, Severity.GRAVE: 0.035}

# Cap so a pile of wounds cannot drive an effective skill absurdly negative.
MAX_PENALTY = 60


@dataclass
class Wound:
    severity: int          # a Severity value (1..3)
    source: str = ""       # short note, e.g. "Blades (bandit)"
    mend: float = 0.0      # healing progress 0..1; at >=1 the wound closes

    def penalty(self) -> int:
        return _PENALTY.get(Severity(self.severity), 0)

    def health_bleed(self) -> float:
        return _HEALTH_BLEED.get(Severity(self.severity), 0.0)

    def tick_mend(self, care: float = 0.0) -> None:
        """Advance healing by one tick. `care` is extra progress from rest or
        treatment (a healer's Medicine, a Mend spell)."""
        self.mend += _MEND_PER_TICK.get(Severity(self.severity), 0.0) + care

    def treat(self, amount: float) -> None:
        """Apply a burst of healing progress (e.g. a successful Medicine check)."""
        self.mend += max(0.0, amount)

    def closed(self) -> bool:
        return self.mend >= 1.0

    def to_dict(self) -> dict:
        return {"severity": int(self.severity), "source": self.source,
                "mend": round(self.mend, 4)}

    @classmethod
    def from_dict(cls, d: dict) -> "Wound":
        return cls(severity=int(d["severity"]), source=d.get("source", ""),
                   mend=float(d.get("mend", 0.0)))


def severity_from_outcome(outcome: Outcome) -> Optional[Severity]:
    """Map an attacker's winning check outcome to the wound it inflicts. A clean
    strike grazes, a solid hit hurts, a critical leaves a grave wound. Anything
    that is not a hit inflicts nothing (returns None)."""
    if outcome == Outcome.CRIT_SUCCESS:
        return Severity.GRAVE
    if outcome == Outcome.SUCCESS:
        return Severity.HURT
    if outcome == Outcome.PARTIAL:
        return Severity.GRAZE
    return None


def total_penalty(wounds) -> int:
    """Combined physical-check penalty from all open wounds, bounded by
    MAX_PENALTY so a badly hurt agent is hampered but never impossibly so."""
    return min(MAX_PENALTY, sum(w.penalty() for w in wounds))


def worst_severity(wounds) -> int:
    """The highest severity among open wounds, or 0 if unwounded."""
    return max((w.severity for w in wounds), default=0)
