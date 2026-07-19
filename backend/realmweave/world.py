"""World state: the village map, its locations, and shared world facts.

The village is a small top-down 2D map. Locations have a grid position and a
radius; agents navigate between them. Keep the geometry simple: the Godot
client mirrors these coordinates to place sprites.
"""
from __future__ import annotations
import math
import heapq
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
        # --- farmland ringing the village (Phase: lands around town) ---
        Location("west_farm", "Brookside Farm", 6, 20, "farm", capacity=6),
        Location("west_field", "West Wheatfield", 8, 30, "field", capacity=12),
        Location("north_orchard", "Sunapple Orchard", 16, 6, "orchard", capacity=10),
        Location("north_farm", "Harrow Steading", 52, 4, "farm", capacity=6),
        Location("east_field", "East Barleyfield", 66, 24, "field", capacity=12),
        Location("mill", "Old Mill", 66, 36, "mill", capacity=4),
        Location("south_pasture", "South Pasture", 22, 54, "pasture", capacity=16),
        Location("south_field", "Southmeadow", 44, 54, "field", capacity=12),
        # homes for the farmhands who work the outer land
        Location("home_shep", "Shepherd's Rest", 14, 48, "home", capacity=2),
        Location("home_hollis", "Hollis Cottage", 12, 12, "home", capacity=2),
        # the village grain store: farmhands haul harvest here, the cook draws from it
        Location("granary", "The Granary", 28, 18, "granary", capacity=6),
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


# Villagers route along roads instead of cutting straight across the map. The
# network links each location to its nearest neighbours so shortest paths stay
# close to straight-line distance: roads that read as a village, without forcing
# long detours that would leave everyone commuting instead of living.
ROAD_KNN = 5


def _knn_edges(locations: "Dict[str, Location]", k: int) -> List[Tuple[str, str]]:
    """Undirected edges joining each location to its k nearest neighbours."""
    ids = list(locations)
    edges = set()
    for a in ids:
        ax, ay = locations[a].x, locations[a].y
        nearest = sorted(ids, key=lambda b: math.hypot(locations[b].x - ax,
                                                        locations[b].y - ay))
        for b in nearest[1:k + 1]:
            edges.add(tuple(sorted((a, b))))
    return sorted(edges)


def default_paths() -> Dict[str, List[str]]:
    """Road adjacency for the default village (a nearest-neighbour network)."""
    locs = default_village()
    adj: Dict[str, List[str]] = {lid: [] for lid in locs}
    for a, b in _knn_edges(locs, ROAD_KNN):
        adj[a].append(b)
        adj[b].append(a)
    return adj


@dataclass
class World:
    name: str = "Oakhollow"
    locations: Dict[str, Location] = field(default_factory=default_village)
    props: List[dict] = field(default_factory=default_props)   # decorative scenery
    paths: Dict[str, List[str]] = field(default_factory=default_paths)  # road adjacency
    # free-form world facts other systems can read/write (weather, rumors, etc.)
    weather: str = "clear"
    rumors: List[str] = field(default_factory=list)

    def loc(self, loc_id: str) -> Location:
        return self.locations[loc_id]

    def pos(self, loc_id: str) -> Tuple[float, float]:
        l = self.locations[loc_id]
        return (l.x, l.y)

    def route(self, start: str, goal: str) -> List[str]:
        """Shortest path of location ids along the roads, inclusive of both
        ends (Dijkstra weighted by straight-line distance). Falls back to a
        direct [start, goal] hop if either node is off the network."""
        if start == goal:
            return [start]
        if start not in self.paths or goal not in self.paths:
            return [start, goal]
        dist = {start: 0.0}
        prev: Dict[str, str] = {}
        pq: List[Tuple[float, str]] = [(0.0, start)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == goal:
                break
            if d > dist.get(u, float("inf")):
                continue
            ux, uy = self.pos(u)
            for v in self.paths.get(u, []):
                vx, vy = self.pos(v)
                nd = d + math.hypot(vx - ux, vy - uy)
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        if goal not in prev:
            return [start, goal]
        path = [goal]
        while path[-1] != start:
            path.append(prev[path[-1]])
        path.reverse()
        return path

    def add_rumor(self, text: str) -> None:
        self.rumors.append(text)
        self.rumors = self.rumors[-50:]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "weather": self.weather,
            "locations": [l.to_dict() for l in self.locations.values()],
            "props": self.props,
            "roads": [[self.locations[a].x, self.locations[a].y,
                       self.locations[b].x, self.locations[b].y]
                      for a in self.paths for b in self.paths[a]
                      if a < b and a in self.locations and b in self.locations],
            "rumors": self.rumors[-10:],
        }
