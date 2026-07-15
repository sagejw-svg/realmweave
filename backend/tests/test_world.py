"""Tests for Phase 9 world-feel data (decorative props + render-facing fields).

Run from the backend/ directory:  py tests\test_world.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.world import World
from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig


class TestWorldProps(unittest.TestCase):
    def test_world_has_decorative_props(self):
        w = World()
        self.assertTrue(w.props)
        kinds = {p["kind"] for p in w.props}
        self.assertIn("tree", kinds)
        d = w.to_dict()
        self.assertIn("props", d)
        self.assertTrue(all("x" in p and "y" in p and "kind" in p for p in d["props"]))

    def test_snapshot_exposes_props_and_time_of_day(self):
        cfg = load_config(); cfg["force_stub"] = True
        sim = Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))
        snap = sim.snapshot()
        self.assertIn("props", snap["world"])
        self.assertIn("part_of_day", snap["clock"])
        self.assertIn(snap["clock"]["part_of_day"],
                      ("night", "morning", "afternoon", "evening"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
