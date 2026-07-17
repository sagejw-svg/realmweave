"""Recipes and raw materials: the inputs a refined good is made from.

Slice B turns crafting into a supply chain. Some professions *gather* raw
materials (a farmer working a field brings in grain, a miner brings in ore);
others *refine* raw materials into finished goods (a smith turns iron and coal
into armor). A refined good cannot be made without its inputs, so production now
depends on supply.

Design is deliberately coarse so the emergent behaviour - who supplies whom,
where a shortage bites, when the NPC supplier gets called on - stays legible.
Grain, iron, and coal are gathered locally (field and mine), so a buyer prefers
a neighbour; anything with no local gatherer comes from the supplier at a
premium. That contrast is the whole point.
"""
from __future__ import annotations

# Raw materials and their base coin value (what a local seller charges).
# The mined metals below are ordered roughly by scarcity/worth; iron and coal
# feed the forge, the rest are stores of value (jewelcraft/coinage come later).
RAW_MATERIALS = {
    "grain": 5,
    "herb": 6,
    "coal": 4,
    "iron": 12,
    "copper": 10,
    "tin": 14,
    "silver": 30,
    "gold": 60,
    "gemstone": 90,
}

# A refined skill -> the inputs one craft consumes: list of (material, qty).
RECIPES = {
    "Smithing": [("iron", 1), ("coal", 1)],   # armor forged from iron over coal
    "Cooking": [("grain", 1)],                # a meal from grain
    "Herbalism": [("herb", 1)],               # a remedy from herb
    # Farming and Mining are primary (gatherers, see GATHER / ORE_TABLE); they
    # need no input.
}

# A location kind -> the raw material gathered by primary work there. A single
# deterministic yield; the mine is the exception (see ORE_TABLE).
GATHER = {
    "field": "grain",
}

# The mine's weighted ore table: a work tick yields one material, drawn by these
# relative weights. Common ores (iron, coal) keep the forge supplied locally;
# precious metals and gems are rare strikes that reward a patient, skilled miner.
# Weights are relative, not percentages, so new ores can be added without
# renormalizing.
ORE_TABLE = [
    ("iron", 40),
    ("coal", 30),
    ("copper", 12),
    ("tin", 8),
    ("silver", 5),
    ("gold", 3),
    ("gemstone", 2),
]


def roll_ore(rng) -> str:
    """Draw one material from the weighted ORE_TABLE using `rng` (an stdlib
    random.Random or compatible). Deterministic for a given seed + call order,
    so stub runs and tests stay reproducible."""
    total = sum(w for _, w in ORE_TABLE)
    pick = rng.randint(1, total)
    upto = 0
    for material, weight in ORE_TABLE:
        upto += weight
        if pick <= upto:
            return material
    return ORE_TABLE[-1][0]   # unreachable, but a safe fallback


# The NPC supplier's markup over base value when no local seller has the good.
# Being a premium keeps a locally-supplied chain cheaper, while guaranteeing that
# production never fully stalls for an agent who can pay.
SUPPLIER_MARKUP = 1.5


def premium_price(material: str) -> int:
    """What the NPC supplier charges for one unit (base value * markup)."""
    base = RAW_MATERIALS.get(material, 10)
    return max(1, int(base * SUPPLIER_MARKUP + 0.999))   # round up
