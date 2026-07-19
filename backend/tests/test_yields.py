"""Tests for animal yields: hens lay eggs, the cow milks, a hand collects them.

Run from the backend/ directory:  py tests\test_yields.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig, YIELD_INTERVAL


def fresh_sim():
    cfg = load_config(); cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestYields(unittest.TestCase):
    def test_producers_are_derived_from_the_animals(self):
        sim = fresh_sim()
        self.assertEqual(sim._yield_kind.get("north_farm"), "egg")   # hens
        self.assertEqual(sim._yield_kind.get("south_pasture"), "milk")  # the cow
        self.assertGreaterEqual(sim._yield_count["north_farm"], 3)    # three hens

    def test_yields_accumulate_on_the_timer(self):
        sim = fresh_sim()
        for _ in range(YIELD_INTERVAL):
            sim.tick()
        produced = sum(sim._pending.values()) + sim.larder["egg"] + sim.larder["milk"]
        self.assertGreater(produced, 0, "hens/cow should have produced by one interval")

    def test_a_hand_collects_eggs_into_the_larder(self):
        sim = fresh_sim()
        sim._pending["north_farm"] = 3
        h = sim.agents["hollis"]; h.current_location = "north_farm"
        sim._collect_yield(h)
        self.assertEqual(sim.larder["egg"], 3)
        self.assertEqual(sim._pending["north_farm"], 0)

    def test_the_shepherd_collects_milk(self):
        sim = fresh_sim()
        sim._pending["south_pasture"] = 2
        n = sim.agents["shep"]; n.current_location = "south_pasture"
        sim._collect_yield(n)
        self.assertEqual(sim.larder["milk"], 2)

    def test_non_field_workers_do_not_collect(self):
        sim = fresh_sim()
        sim._pending["north_farm"] = 3
        g = sim.agents["gart"]; g.current_location = "north_farm"   # a miner
        sim._collect_yield(g)
        self.assertEqual(sim.larder["egg"], 0)
        self.assertEqual(sim._pending["north_farm"], 3)

    def test_snapshot_exposes_the_larder(self):
        sim = fresh_sim()
        self.assertIn("larder", sim.snapshot())


if __name__ == "__main__":
    unittest.main(verbosity=2)
