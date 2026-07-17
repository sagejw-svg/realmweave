"""Abstract combat: one opposed exchange resolves to a narrative outcome.

Combat in Realmweave is not hit-point attrition. An exchange is a single opposed
check (rules/checks.opposed) between an attacker's offense and a defender's best
defense. The winner and the degree of success map to an outcome:

  - HIT       the attacker lands a blow; the defender takes a wound whose
              severity comes from the attacker's degree (partial graze, solid
              hurt, critical grave), via rules/harm.severity_from_outcome.
  - REPELLED  the defender turns the attack aside.
  - EXPOSED   the attacker fumbles and loses their footing (a hook for a riposte).
  - STANDOFF  neither gains; positions shift and the encounter may continue.

This module is pure and deterministic given the RNG. The sim decides who fights,
applies the wound, and chooses whether the encounter continues, so the branching
"who wins the war" logic stays out of here. Most encounters are one to a few
exchanges before someone yields, flees, or is subdued.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .checks import opposed, Outcome
from .harm import Severity, severity_from_outcome

# Skills an attacker may lead with, and the defenses a target may answer with.
# The sim picks the actor's best of each set.
OFFENSE_SKILLS = ("Blades", "Archery", "Intimidation")
DEFENSE_SKILLS = ("Athletics", "Blades", "Tactics")


class ExchangeResult(str, Enum):
    HIT = "hit"
    REPELLED = "repelled"
    EXPOSED = "exposed"
    STANDOFF = "standoff"


@dataclass
class Exchange:
    result: ExchangeResult
    severity: int = 0           # wound severity inflicted on the loser (0 = none)
    attacker_roll: int = 0
    defender_roll: int = 0


def resolve_exchange(attacker_off: int, defender_def: int, rng,
                     adv_att: int = 0, adv_def: int = 0) -> Exchange:
    """Resolve one exchange. Returns an Exchange; a HIT carries the wound severity
    (1..3) the defender should take."""
    winner, ra, rb = opposed(attacker_off, defender_def, rng, adv_att, adv_def)
    if ra.outcome == Outcome.FUMBLE:
        return Exchange(ExchangeResult.EXPOSED, 0, ra.roll, rb.roll)
    if winner == "a" and ra.success:
        sev = severity_from_outcome(ra.outcome) or Severity.GRAZE
        return Exchange(ExchangeResult.HIT, int(sev), ra.roll, rb.roll)
    if winner == "b" and rb.success:
        return Exchange(ExchangeResult.REPELLED, 0, ra.roll, rb.roll)
    return Exchange(ExchangeResult.STANDOFF, 0, ra.roll, rb.roll)
