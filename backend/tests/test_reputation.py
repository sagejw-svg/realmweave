"""Unit tests for Phase 7 reputation & justice.

Run from the backend/ directory:  py tests\test_reputation.py
Core acceptance: a witnessed crime makes the perp wanted and pursued; the same
crime unwitnessed goes undetected; an alias holds until a witness recognizes the
true face; and standing recovers over time.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


def scatter_far(sim, keep):
    """Move everyone except `keep` ids far away so they can't witness."""
    for a in sim.agents.values():
        if a.id not in keep:
            a.x, a.y = 900.0, 900.0


class TestWitnessing(unittest.TestCase):
    def test_witnessed_crime_makes_perp_wanted(self):
        sim = fresh_sim()
        scatter_far(sim, keep={"toft", "wren"})
        perp = sim.agents["toft"]; perp.x, perp.y = 30.0, 30.0
        witness = sim.agents["wren"]; witness.x, witness.y = 31.0, 30.0   # sharp-eyed, close
        res = sim.justice.commit_crime("toft", "theft", victim_id="bram")
        self.assertTrue(res["detected"])
        self.assertGreater(perp.wanted, 0)
        self.assertGreater(perp.bounty, 0)
        self.assertIn("wanted:toft", witness.known_facts)
        self.assertIn(witness.id, perp.recognized_by)
        self.assertLess(perp.reputation["village"], 0)
        # the guard is notified and joins the hunt
        self.assertIn("wanted:toft", sim.agents["guard"].known_facts)

    def test_unwitnessed_crime_goes_undetected(self):
        sim = fresh_sim()
        scatter_far(sim, keep={"toft"})
        perp = sim.agents["toft"]; perp.x, perp.y = 30.0, 30.0
        res = sim.justice.commit_crime("toft", "theft", victim_id="")
        self.assertFalse(res["detected"])
        self.assertEqual(perp.wanted, 0)


class TestAlias(unittest.TestCase):
    def test_alias_holds_until_recognized(self):
        sim = fresh_sim()
        perp = sim.agents["dora"]
        perp.name = "Dora Meel"; perp.alias = "Sam Smith"
        stranger = sim.agents["bram"]
        witness = sim.agents["wren"]
        # before any recognition, both see the alias
        self.assertEqual(sim.display_name(perp, stranger.id), "Sam Smith")
        # the witness recognizes the true face (as if they saw a crime)
        perp.recognized_by.add(witness.id)
        self.assertEqual(sim.display_name(perp, witness.id), "Dora Meel")
        self.assertEqual(sim.display_name(perp, stranger.id), "Sam Smith")


class TestPursuitAndRedemption(unittest.TestCase):
    def test_wanted_perp_is_pursued_and_caught(self):
        sim = fresh_sim()
        scatter_far(sim, keep={"toft", "wren", "guard"})
        perp = sim.agents["toft"]; perp.x, perp.y = 32.0, 24.0
        sim.agents["wren"].x, sim.agents["wren"].y = 33.0, 24.0
        sim.agents["guard"].x, sim.agents["guard"].y = 34.0, 24.0
        sim.justice.commit_crime("toft", "assault", victim_id="wren")
        arrests = []
        sim.subscribe(lambda e: arrests.append(e) if e["kind"] == "arrest" else None)
        for _ in range(500):
            sim.tick()
            if arrests:
                break
        self.assertTrue(arrests, "the guard should eventually catch the wanted perp")
        self.assertEqual(sim.agents["toft"].wanted, 0)

    def test_notoriety_recovers_over_time(self):
        sim = fresh_sim()
        sim.agents["toft"].notoriety = 5.0
        before = sim.agents["toft"].notoriety
        for _ in range(50):
            sim.justice._recover()
        self.assertLess(sim.agents["toft"].notoriety, before)


class TestJusticePersistence(unittest.TestCase):
    def test_wanted_and_crimes_survive_save_load(self):
        sim = fresh_sim()
        scatter_far(sim, keep={"toft", "wren"})
        sim.agents["toft"].x, sim.agents["toft"].y = 30.0, 30.0
        sim.agents["wren"].x, sim.agents["wren"].y = 31.0, 30.0
        sim.justice.commit_crime("toft", "theft", victim_id="bram")
        sim.agents["toft"].alias = "The Masked Thief"
        path = os.path.join(tempfile.gettempdir(), "rw_reputation.json")
        sim.save(path)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertGreater(sim2.agents["toft"].wanted, 0)
        self.assertEqual(sim2.agents["toft"].alias, "The Masked Thief")
        self.assertTrue(sim2.justice.crimes)
        self.assertIn("wren", sim2.agents["toft"].recognized_by)


if __name__ == "__main__":
    unittest.main(verbosity=2)
