"""Tests for dungeon delving (Phase 2): combat-driven expeditions.

Run from the backend/ directory:  py tests\test_delving.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig
from realmweave.dungeons import DUNGEONS


def fresh_sim():
    cfg = load_config(); cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


def dungeon(did):
    return next(d for d in DUNGEONS if d.id == did)


class TestDelving(unittest.TestCase):
    def test_a_delve_returns_a_valid_result(self):
        sim = fresh_sim()
        d = dungeon("weeping_caverns")
        res = sim.resolve_delve(sim.agents["guard"], d)
        self.assertIn(res["outcome"], ("triumph", "withdrew", "slain"))
        self.assertGreaterEqual(res["depth"], 0)
        self.assertLessEqual(res["depth"], len(d.levels))

    def test_a_mighty_hero_triumphs_and_learns_the_mystery(self):
        sim = fresh_sim()
        hero = sim.agents["guard"]
        for sk in ("Blades", "Athletics", "Tactics", "Intimidation"):
            hero.sheet.skills[sk] = 100
        res = sim.resolve_delve(hero, dungeon("weeping_caverns"))
        self.assertEqual(res["outcome"], "triumph")
        self.assertIn("weeping_caverns", sim.cleared_dungeons)
        self.assertIn("mystery:weeping_caverns", hero.known_facts)

    def test_a_feeble_delver_does_not_clear_a_grave(self):
        sim = fresh_sim()
        hero = sim.agents["guard"]
        for sk in ("Blades", "Athletics", "Tactics", "Intimidation"):
            hero.sheet.skills[sk] = 10          # hopeless
        hero.equipment.clear()
        res = sim.resolve_delve(hero, dungeon("hollow_barrow"))  # danger 4
        self.assertNotEqual(res["outcome"], "triumph")
        self.assertLess(res["depth"], len(dungeon("hollow_barrow").levels))

    def test_no_expeditions_when_disabled(self):
        sim = fresh_sim()                         # delve_chance defaults to 0
        seen = []
        sim.subscribe(lambda e: seen.append(e) if e["kind"] == "expedition" else None)
        for _ in range(300):
            sim.tick()
        self.assertEqual(len(seen), 0)
        self.assertFalse(sim.cleared_dungeons)

    def test_expeditions_fire_when_enabled(self):
        sim = fresh_sim()
        sim.cfg.delve_chance = 1.0
        seen = []
        sim.subscribe(lambda e: seen.append(e) if e["kind"] == "expedition" else None)
        for _ in range(20):
            sim.tick()
        self.assertGreaterEqual(len(seen), 1)

    def test_snapshot_exposes_cleared_dungeons(self):
        self.assertIn("cleared_dungeons", fresh_sim().snapshot())


if __name__ == "__main__":
    unittest.main(verbosity=2)
