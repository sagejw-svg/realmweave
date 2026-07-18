"""Magic: two traditions, one small, legible catalog.

Realmweave's magic is uncommon, costly, and mostly practical, in keeping with the
low-industrial tone. Two traditions cast from a personal `focus` pool (a
mana-like reservoir scaled by the caster's mind and presence, refilled by rest):

  - Arcana  (keyed to the Arcana skill): the scholar's craft, offense and wards.
  - Faith   (keyed to the Faith skill): the devout's grace, mending and routing.

Casting is a skill check (rules/checks): the degree of success sets the effect's
strength, and a fumble backfires. Effects resolve in code, deterministic with a
seed; the LLM only narrates. This module is the pure catalog and the focus
maths; the sim (sim.cast) applies the effects to agents and the world.

Design note: the proposal floated Faith drawing on the global divine `favor`
pool, but that pool is the player-god's suggestion budget, not a caster's
resource. Using a per-agent focus pool for both traditions keeps the two systems
from stepping on each other; the god's favor stays about influence, not spells.
"""
from __future__ import annotations
from dataclasses import dataclass

# Ward: a defensive buff that raises the target's defense for a short while.
WARD_TICKS = 6
WARD_DEFENSE_BONUS = 15
# A fumbled cast costs extra focus (the spell recoils on the caster).
BACKFIRE_FOCUS_LOSS = 2.0


def max_focus(sheet) -> float:
    """A caster's focus capacity, scaled by Intellect and Presence. A default
    sheet (attributes 50) yields 13; a gifted mind/presence more."""
    if sheet is None:
        return 8.0
    return 8.0 + (sheet.attribute("Intellect") + sheet.attribute("Presence")) // 20


@dataclass(frozen=True)
class Spell:
    name: str
    skill: str        # governing skill: "Arcana" or "Faith"
    cost: float       # focus spent to attempt the cast
    kind: str         # heal / attack / defend / rout


# The catalog: small enough that a person and an LLM can both reason about it.
SPELLS = {
    "mend":     Spell("mend",     "Faith",  4.0, "heal"),
    "bolt":     Spell("bolt",     "Arcana", 6.0, "attack"),
    "ward":     Spell("ward",     "Arcana", 3.0, "defend"),
    "frighten": Spell("frighten", "Faith",  3.0, "rout"),
}


def get_spell(name: str):
    return SPELLS.get(name)
