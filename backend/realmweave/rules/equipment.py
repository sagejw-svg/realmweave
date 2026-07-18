"""Equipment: worn gear as check modifiers, not stat soak.

Gear layers onto the existing economy Item (economy/goods.py). A weapon adds an
offense modifier scaled by its quality and declares which skill it keys (a blade
keys Blades, a bow keys Archery). Armor does not soak hit points: on a hit it has
a quality-scaled chance to reduce the wound by one severity step (grave -> hurt
-> graze -> nothing), at the cost of a small evasion penalty so heavy protection
trades nimbleness for safety. A trinket slot is reserved for later focuses and
holy symbols.

Everything here is a pure function over an Item; the sim applies the results in
resolve_combat. Item quality is the existing 1-100, so a masterwork blade or fine
mail is genuinely better than a novice's, tying gear back to the crafting economy.
"""
from __future__ import annotations

SLOTS = ("weapon", "armor", "trinket")

# Which equipment slot an item fills, by its goods category.
_CATEGORY_SLOT = {"weapon": "weapon", "armor": "armor"}


def slot_for(item) -> str:
    """The slot an item occupies. Anything that is not a weapon or armor is a
    trinket (a catch-all for charms, focuses, holy symbols)."""
    return _CATEGORY_SLOT.get(item.category, "trinket")


def weapon_skill(item) -> str:
    """The offense skill a weapon keys. A bow keys Archery; anything else Blades."""
    return "Archery" if "bow" in item.name.lower() else "Blades"


def weapon_offense_mod(item) -> int:
    """A weapon's offense bonus, scaled by quality (q1 -> +1, q100 -> +20)."""
    return max(1, round(item.quality / 5))


def armor_mitigation_chance(item) -> float:
    """Chance that armor reduces an incoming wound by one severity step, scaled by
    quality (q1 -> ~0.11, q100 -> 0.70)."""
    return 0.1 + 0.6 * (item.quality / 100.0)


def armor_evasion_penalty(item) -> int:
    """Defense (evasion) cost of wearing armor. Flat and small: armor makes you a
    touch easier to hit, in exchange for turning aside the worst of a blow."""
    return 4
