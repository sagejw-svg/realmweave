"""Recipes and raw materials: the inputs a refined good is made from.

Slice B turns crafting into a supply chain. Some professions *gather* raw
materials (a farmer working a field brings in grain); others *refine* raw
materials into finished goods (a smith turns iron into armor). A refined good
cannot be made without its inputs, so production now depends on supply.

Design is deliberately coarse (one input per good) so the emergent behaviour -
who supplies whom, where a shortage bites, when the NPC supplier gets called on -
stays legible. Iron and herb have no local gatherer in Oakhollow yet, so they
come from the supplier at a premium; grain is farmed locally, so a cook prefers
to buy it from a neighbour. That contrast is the whole point.
"""
from __future__ import annotations

# Raw materials and their base coin value (what a local seller charges).
RAW_MATERIALS = {
    "iron": 12,
    "grain": 5,
    "herb": 6,
}

# A refined skill -> the inputs one craft consumes: list of (material, qty).
RECIPES = {
    "Smithing": [("iron", 1)],     # armor from iron
    "Cooking": [("grain", 1)],     # a meal from grain
    "Herbalism": [("herb", 1)],    # a remedy from herb
    # Farming is primary (a gatherer, see GATHER); it needs no input.
}

# A location kind -> the raw material gathered by primary work there.
GATHER = {
    "field": "grain",
}

# The NPC supplier's markup over base value when no local seller has the good.
# Being a premium keeps a locally-supplied chain cheaper, while guaranteeing that
# production never fully stalls for an agent who can pay.
SUPPLIER_MARKUP = 1.5


def premium_price(material: str) -> int:
    """What the NPC supplier charges for one unit (base value * markup)."""
    base = RAW_MATERIALS.get(material, 10)
    return max(1, int(base * SUPPLIER_MARKUP + 0.999))   # round up
