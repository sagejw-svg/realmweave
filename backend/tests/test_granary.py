"""Tests for the village granary: farmhands store grain, the cook draws from it.

Run from the backend/ directory:  py tests\test_granary.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig


def fresh_sim():
    cfg = load_config(); cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestGranary(unittest.TestCase):
    def test_granary_exists_and_starts_empty(self):
        sim = fresh_sim()
        self.assertIn("granary", sim.world.locations)
        self.assertEqual(sim.granary, 0)
        self.assertIn("granary", sim.snapshot())

    def test_farmhand_stores_grain_at_the_granary(self):
        sim = fresh_sim()
        h = sim.agents["hollis"]
        h.current_location, h.materials["grain"] = "granary", 5
        sim._store_grain(h)
        self.assertEqual(h.materials["grain"], 0)
        self.assertEqual(sim.granary, 5)

    def test_grain_is_also_dropped_at_the_tavern(self):
        sim = fresh_sim()
        d = sim.agents["dora"]
        d.current_location, d.materials["grain"] = "tavern", 3
        sim._store_grain(d)
        self.assertEqual(sim.granary, 3)

    def test_non_field_workers_do_not_deposit(self):
        sim = fresh_sim()
        g = sim.agents["gart"]                       # a miner, not a field worker
        g.current_location, g.materials["grain"] = "granary", 4
        sim._store_grain(g)
        self.assertEqual(sim.granary, 0)
        self.assertEqual(g.materials["grain"], 4)

    def test_cook_draws_from_the_granary_even_when_broke(self):
        sim = fresh_sim()
        sim.granary = 6
        bram = sim.agents["bram"]                     # Tavernkeeper -> Cooking
        bram.activity, bram.current_location = "work", "tavern"
        bram.coin, bram.materials = 0, {}             # no coin: granary is the only source
        crafts = []
        sim.subscribe(lambda e: crafts.append(e) if e["kind"] == "craft" else None)
        for _ in range(400):
            sim._maybe_craft(bram)
        self.assertGreaterEqual(len(crafts), 1, "the cook should cook from the granary")
        self.assertLess(sim.granary, 6, "the cook should have drawn grain from the store")


if __name__ == "__main__":
    unittest.main(verbosity=2)
