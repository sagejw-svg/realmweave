"""Tests for crops: fields and farms ripen over time and are harvested to grain.

Run from the backend/ directory:  py tests\test_crops.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig, HARVEST_THRESHOLD


def fresh_sim():
    cfg = load_config(); cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestCrops(unittest.TestCase):
    def test_every_field_and_farm_has_a_crop_and_starts_ripe(self):
        sim = fresh_sim()
        for lid, l in sim.world.locations.items():
            if l.kind in ("field", "farm"):
                self.assertIn(lid, sim._crops)
                self.assertGreaterEqual(sim._crops[lid], HARVEST_THRESHOLD)

    def test_crops_ripen_over_time(self):
        sim = fresh_sim()
        sim._crops["field"] = 0.0
        sim.tick()
        self.assertGreater(sim._crops["field"], 0.0)

    def test_harvest_yields_grain_and_resets_the_field(self):
        sim = fresh_sim()
        dora = sim.agents["dora"]
        dora.activity, dora.current_location = "work", "field"
        sim._crops["field"] = 1.0
        for _ in range(400):
            sim._maybe_craft(dora)
            if dora.materials.get("grain", 0) > 0:
                break
        self.assertGreater(dora.materials.get("grain", 0), 0)
        self.assertEqual(sim._crops["field"], 0.0)   # reaped; it will regrow

    def test_farms_also_grow_grain(self):
        sim = fresh_sim()
        hollis = sim.agents["hollis"]
        hollis.activity, hollis.current_location = "work", "west_farm"
        sim._crops["west_farm"] = 1.0
        for _ in range(400):
            sim._maybe_craft(hollis)
            if hollis.materials.get("grain", 0) > 0:
                break
        self.assertGreater(hollis.materials.get("grain", 0), 0)

    def test_snapshot_exposes_crops(self):
        sim = fresh_sim()
        crops = sim.snapshot()["crops"]
        self.assertIn("field", crops)
        self.assertTrue(all(0.0 <= r <= 1.0 for r in crops.values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
