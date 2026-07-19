"""Livestock: lightweight ambient animals that graze near their home ground by
day and gather at a pen at night. They are not agents - no needs, memory, or
goals - just a bit of moving life for the pastures and farmyards. Animal
randomness uses a dedicated RNG so it never perturbs agent determinism.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Optional

SPEED = 0.6        # slow amble, well under a villager's 1.6
GRAZE_R = 5.0      # how far an animal drifts from its home ground while grazing
PEN_R = 1.6        # tight cluster when penned at night


@dataclass
class Animal:
    id: str
    kind: str          # sheep, cow, pig, chicken, horse
    x: float
    y: float
    home: str          # location id it grazes around by day
    pen: str           # location id it gathers at by night
    state: str = "graze"
    tx: Optional[float] = None
    ty: Optional[float] = None

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind,
                "x": round(self.x, 2), "y": round(self.y, 2), "state": self.state}


def default_animals() -> List["Animal"]:
    """A modest herd: sheep and a cow on the south pasture, horses by the
    stable, a pig at the west farm, hens at the north farm."""
    a: List[Animal] = []
    for i in range(4):
        a.append(Animal(f"sheep{i}", "sheep", 22, 54, "south_pasture", "south_pasture"))
    a.append(Animal("cow0", "cow", 24, 52, "south_pasture", "south_pasture"))
    # the stable paddock: a small herd of horses and a couple of goats
    for i in range(4):
        a.append(Animal(f"horse{i}", "horse", 46, 20, "stable", "stable"))
    for i in range(2):
        a.append(Animal(f"goat{i}", "goat", 48, 22, "stable", "stable"))
    a.append(Animal("pig0", "pig", 6, 20, "west_farm", "west_farm"))
    for i in range(3):
        a.append(Animal(f"hen{i}", "chicken", 52, 4, "north_farm", "north_farm"))
    return a


def update(animals: List["Animal"], world, clock, rng) -> None:
    """Advance every animal one tick: penned toward the pen at night, otherwise
    grazing toward a slowly-reselected point near home."""
    night = clock.is_night
    for an in animals:
        if an.home in world.locations:
            hx, hy = world.pos(an.home)
        else:
            hx, hy = an.x, an.y
        if night:
            an.state = "penned"
            if an.pen in world.locations:
                px, py = world.pos(an.pen)
            else:
                px, py = hx, hy
            ang = rng.random() * math.tau
            an.tx = px + math.cos(ang) * PEN_R
            an.ty = py + math.sin(ang) * PEN_R
        else:
            an.state = "graze"
            need_target = (an.tx is None
                           or math.hypot(an.x - an.tx, an.y - an.ty) < 0.6
                           or rng.random() < 0.04)
            if need_target:
                ang = rng.random() * math.tau
                r = rng.random() * GRAZE_R
                an.tx = hx + math.cos(ang) * r
                an.ty = hy + math.sin(ang) * r
        dx, dy = an.tx - an.x, an.ty - an.y
        d = math.hypot(dx, dy)
        if d > SPEED:
            an.x += SPEED * dx / d
            an.y += SPEED * dy / d
        else:
            an.x, an.y = an.tx, an.ty
