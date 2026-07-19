"""Tests for the dungeons: data, lore, and snapshot exposure (Phase 1).

Run from the backend/ directory:  py tests\test_dungeons.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.dungeons import DUNGEONS
from realmweave.world import World
from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig


def fresh_sim():
    cfg = load_config(); cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestDungeons(unittest.TestCase):
    def test_four_dungeons_including_kobold_and_welldeep(self):
        ids = {d.id for d in DUNGEONS}
        self.assertGreaterEqual(len(DUNGEONS), 4)
        self.assertIn("kobold_warren", ids)
        self.assertIn("welldeep", ids)

    def test_every_dungeon_has_lore(self):
        for d in DUNGEONS:
            self.assertTrue(d.name and d.entrance and d.mystery, d.id)
            self.assertGreaterEqual(d.danger, 1)
            self.assertLessEqual(d.danger, 5)
            self.assertTrue(d.levels, d.id)
            for lv in d.levels:
                self.assertLessEqual({"name", "denizens", "hazard"}, set(lv))

    def test_welldeep_descends_from_the_old_well(self):
        w = next(d for d in DUNGEONS if d.id == "welldeep")
        self.assertEqual((w.x, w.y), (32, 30))          # the Old Well's position
        self.assertIn("Well", w.entrance)
        self.assertEqual(w.levels[0]["name"], "The Stag's Cellar")   # rats first

    def test_world_and_snapshot_expose_dungeons(self):
        self.assertIn("dungeons", World().to_dict())
        d = fresh_sim().snapshot()["world"]["dungeons"]
        self.assertEqual(len(d), len(DUNGEONS))
        self.assertTrue(any(x["id"] == "kobold_warren" for x in d))
        self.assertTrue(all({"name", "danger", "levels", "mystery"} <= set(x) for x in d))


if __name__ == "__main__":
    unittest.main(verbosity=2)
