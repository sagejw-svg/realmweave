"""World state: the village map, its locations, and shared world facts.

The village is a small top-down 2D map. Locations have a grid position and a
radius; agents navigate between them. Keep the geometry simple: the Godot
client mirrors these coordinates to place sprites.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Location:
    id: str
    name: str
    x: float
    y: float
    kind: str  # tavern, home, stable, well, square, smithy, field, gate
    capacity: int = 8

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "x": self.x, "y": self.y, "kind": self.kind}


def default_village() -> Dict[str, Location]:
    """A hand-authored starter village: Oakhollow."""
    locs = [
        Location("square", "Village Square", 32, 24, "square", capacity=30),
        Location("tavern", "The Gilded Stag", 20, 18, "tavern", capacity=20),
        Location("tavern_kitchen", "Stag Kitchen", 16, 16, "tavern", capacity=4),
        Location("well", "Old Well", 32, 30, "well", capacity=6),
        Location("stable", "Stables", 46, 20, "stable", capacity=8),
        Location("smithy", "Ironbark Smithy", 44, 30, "smithy", capacity=4),
        Location("field", "North Fields", 30, 6, "field", capacity=12),
        Location("mine", "Ironbark Mine", 56, 32, "mine", capacity=6),
        Location("gate", "South Gate", 32, 44, "gate", capacity=10),
        Location("home_bram", "Bram's Room", 14, 22, "home", capacity=2),
        Location("home_isla", "Isla's Cottage", 50, 14, "home", capacity=3),
        Location("home_toft", "Toft's Shack", 48, 36, "home", capacity=2),
        Location("home_wren", "Wren's Loft", 24, 34, "home", capacity=2),
        Location("home_dora", "Dora's House", 38, 10, "home", capacity=3),
        Location("home_gart", "Gart's Hut", 58, 38, "home", capacity=2),
    ]
    return {l.id: l for l in locs}


def default_props() -> List[dict]:
    """Decorative, non-interactive scenery for the client to render (trees, a
    pond, rocks). Hand-placed around the edges so the village reads as a place,
    not a scatter of labels. Purely visual; the simulation ignores these."""
    trees = [(8, 8), (12, 40), (52, 8), (56, 40), (6, 26), (58, 24), (24, 4),
             (40, 46), (18, 44), (48, 4), (2, 16), (60, 34), (30, 48), (34, 2)]
    props = [{"kind": "tree", "x": x, "y": y} for (x, y) in trees]
    props += [{"kind": "rock", "x": 26, "y": 6}, {"kind": "rock", "x": 44, "y": 42}]
    props += [{"kind": "rock", "x": 58, "y": 30}, {"kind": "rock", "x": 54, "y": 34}]
    props += [{"kind": "pond", "x": 12, "y": 32}]
    return props


@dataclass
class World:
    name: str = "Oakhollow"
    locations: Dict[str, Location] = field(default_factory=default_village)
    props: List[dict] = field(default_factory=default_props)   # decorative scenery
    # free-form world facts other systems can read/write (weather, rumors, etc.)
    weather: str = "clear"
    rumors: List[str] = field(default_factory=list)

    def loc(self, loc_id: str) -> Location:
        return self.locations[loc_id]

    def pos(self, loc_id: str) -> Tuple[float, float]:
        l = self.locations[loc_id]
        return (l.x, l.y)

    def add_rumor(self, text: str) -> None:
        self.rumors.append(text)
        self.rumors = self.rumors[-50:]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "weather": self.weather,
            "locations": [l.to_dict() for l in self.locations.values()],
            "props": self.props,
            "rumors": self.rumors[-10:],
        }
