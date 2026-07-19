"""Tests for ambient livestock (graze by day, pen at night).

Run from the backend/ directory:  py tests\test_livestock.py
"""
import os
import sys
import math
import random
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave import livestock
from realmweave.world import World
from realmweave.time_system import WorldClock
from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig


class TestLivestock(unittest.TestCase):
    def test_default_herd_present(self):
        animals = livestock.default_animals()
        kinds = {a.kind for a in animals}
        self.assertLessEqual({"sheep", "cow", "horse", "pig", "chicken", "goat"}, kinds)
        self.assertGreaterEqual(len(animals), 8)
        w = World()
        for a in animals:
            self.assertIn(a.home, w.locations)
            self.assertIn(a.pen, w.locations)

    def test_stable_paddock_has_horses_and_goats(self):
        stable = [a for a in livestock.default_animals() if a.home == "stable"]
        horses = sum(1 for a in stable if a.kind == "horse")
        goats = sum(1 for a in stable if a.kind == "goat")
        self.assertGreaterEqual(horses, 4)
        self.assertGreaterEqual(goats, 2)

    def test_animals_move_and_stay_near_home_by_day(self):
        w = World(); animals = livestock.default_animals(); rng = random.Random(1)
        noon = WorldClock(minutes=12 * 60)
        self.assertFalse(noon.is_night)
        before = [(a.x, a.y) for a in animals]
        for _ in range(200):
            livestock.update(animals, w, noon, rng)
        moved = any(b != (a.x, a.y) for b, a in zip(before, animals))
        self.assertTrue(moved, "no animal moved while grazing")
        for a in animals:
            hx, hy = w.pos(a.home)
            self.assertLessEqual(math.hypot(a.x - hx, a.y - hy),
                                 livestock.GRAZE_R + livestock.SPEED + 1e-6)
            self.assertEqual(a.state, "graze")

    def test_animals_pen_at_night(self):
        w = World(); animals = livestock.default_animals(); rng = random.Random(2)
        # scatter them first (a day of grazing), then run a night
        noon = WorldClock(minutes=12 * 60)
        for _ in range(120):
            livestock.update(animals, w, noon, rng)
        night = WorldClock(minutes=23 * 60)
        self.assertTrue(night.is_night)
        for _ in range(300):
            livestock.update(animals, w, night, rng)
        for a in animals:
            px, py = w.pos(a.pen)
            self.assertEqual(a.state, "penned")
            self.assertLessEqual(math.hypot(a.x - px, a.y - py),
                                 livestock.PEN_R + livestock.SPEED + 1e-6)

    def test_snapshot_exposes_animals(self):
        cfg = load_config(); cfg["force_stub"] = True
        sim = Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))
        for _ in range(10):
            sim.tick()
        animals = sim.snapshot()["animals"]
        self.assertTrue(animals)
        for a in animals:
            self.assertLessEqual({"id", "kind", "x", "y", "state"}, set(a))


if __name__ == "__main__":
    unittest.main(verbosity=2)
