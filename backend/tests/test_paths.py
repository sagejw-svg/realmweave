"""Tests for the road network and villagers walking along it.

Run from the backend/ directory:  py tests\test_paths.py
"""
import os
import sys
import math
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.world import World
from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig


def _pt_seg_dist(px, py, ax, ay, bx, by):
    """Distance from point (px,py) to segment (ax,ay)-(bx,by)."""
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    cx, cy = ax + t * vx, ay + t * vy
    return math.hypot(px - cx, py - cy)


class TestRoadRouting(unittest.TestCase):
    def setUp(self):
        self.w = World()

    def test_paths_are_symmetric_and_cover_all_locations(self):
        for a, nbrs in self.w.paths.items():
            for b in nbrs:
                self.assertIn(a, self.w.paths[b], f"{a}->{b} not symmetric")
        for loc_id in self.w.locations:
            self.assertIn(loc_id, self.w.paths, f"{loc_id} is off the road network")
            self.assertTrue(self.w.paths[loc_id], f"{loc_id} has no roads")

    def test_route_is_a_valid_connected_path(self):
        self.assertEqual(self.w.route("square", "square"), ["square"])
        for start, goal in [("tavern", "well"), ("home_bram", "home_gart"),
                            ("tavern_kitchen", "mine"), ("field", "gate")]:
            r = self.w.route(start, goal)
            self.assertEqual(r[0], start)
            self.assertEqual(r[-1], goal)
            self.assertEqual(len(r), len(set(r)), "route revisits a node")
            for a, b in zip(r, r[1:]):
                self.assertIn(b, self.w.paths[a], f"{a}->{b} is not a road")

    def test_route_is_near_optimal(self):
        # a nearest-neighbour network keeps routed distance close to straight
        def straight(a, b):
            ax, ay = self.w.pos(a); bx, by = self.w.pos(b)
            return math.hypot(bx - ax, by - ay)

        def routed_len(a, b):
            r = self.w.route(a, b)
            return sum(straight(u, v) for u, v in zip(r, r[1:]))
        worst = max(routed_len(a, b) / straight(a, b)
                    for a in self.w.locations for b in self.w.locations
                    if a != b)
        self.assertLess(worst, 1.6, "some road detour is too long")

    def test_snapshot_exposes_roads(self):
        cfg = load_config(); cfg["force_stub"] = True
        sim = Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))
        roads = sim.snapshot()["world"]["roads"]
        self.assertTrue(roads)
        self.assertTrue(all(len(seg) == 4 for seg in roads))


class TestAgentWalksTheRoads(unittest.TestCase):
    def test_agent_stays_on_the_roads_and_arrives(self):
        cfg = load_config(); cfg["force_stub"] = True
        sim = Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))
        roads = sim.world.to_dict()["roads"]
        a = next(iter(sim.agents.values()))
        a.current_location = "home_bram"
        a.x, a.y = sim.world.pos("home_bram")
        a.target_location = "home_gart"     # far corner: a genuine multi-hop trip
        a.activity = "work"
        sim._routes.pop(a.id, None)

        self.assertGreater(len(sim.world.route("home_bram", "home_gart")), 2)
        arrived_at = None
        for step in range(400):
            px, py = a.x, a.y
            sim._move(a)
            self.assertLessEqual(math.hypot(a.x - px, a.y - py), a.speed + 1e-6,
                                 "agent teleported")
            # at every tick the agent sits on a road segment, not cutting across
            on_road = min(_pt_seg_dist(a.x, a.y, *seg) for seg in roads)
            self.assertLess(on_road, 0.5, "agent left the roads")
            if a.current_location == "home_gart":
                arrived_at = step
                break
        self.assertIsNotNone(arrived_at, "agent never reached its destination")


if __name__ == "__main__":
    unittest.main(verbosity=2)
