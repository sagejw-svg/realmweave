"""Goods: the things agents make, own, stock, and sell.

An Item is a concrete instance of a good with a quality (1-100, set by the skill
check that produced it). Its worth scales with quality, so a master smith's armor
is genuinely more valuable than a novice's. Base values are deliberately coarse;
the economy is about emergent behaviour, not spreadsheet balance.
"""
from __future__ import annotations
from dataclasses import dataclass

# base coin value per category (a quality-50 item is worth exactly this)
BASE_VALUES = {
    "armor": 40,
    "produce": 8,
    "remedy": 25,
    "tool": 18,
    "meal": 6,
    "good": 12,
}

# maps a crafting skill to the good it yields: (item name, category)
SKILL_OUTPUT = {
    "Smithing": ("a piece of armor", "armor"),
    "Farming": ("a bushel of produce", "produce"),
    "Herbalism": ("a healing remedy", "remedy"),
    "Cooking": ("a hot meal", "meal"),
}


@dataclass
class Item:
    name: str
    category: str
    quality: int
    base_value: int

    def value(self) -> int:
        """Worth in coin, scaled by quality (q50 = base, q100 = 1.5x, q10 = 0.6x)."""
        return max(1, int(self.base_value * (0.5 + self.quality / 100.0)))

    def to_dict(self) -> dict:
        return {"name": self.name, "category": self.category,
                "quality": self.quality, "base_value": self.base_value}

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        return cls(name=d["name"], category=d["category"],
                   quality=int(d["quality"]), base_value=int(d["base_value"]))


def make_item(skill: str, quality: int) -> Item:
    name, category = SKILL_OUTPUT.get(skill, ("a good", "good"))
    return Item(name=name, category=category, quality=quality,
                base_value=BASE_VALUES.get(category, 12))
