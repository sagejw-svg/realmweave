"""Unit tests for Phase 6 perception.

Run from the backend/ directory:  py tests\test_perception.py
Core acceptance: an event witnessed by one agent is known only to those who
could perceive it; unwitnessed agents stay unaware until the news reaches them
by rumor through conversation.
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
from realmweave.perception import senses as perception


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestSenses(unittest.TestCase):
    def test_sight_falls_off_with_distance_and_night(self):
        sim = fresh_sim()
        a = sim.agents["bram"]
        a.x, a.y = 0.0, 0.0
        self.assertTrue(perception.can_see(a, 5, 0, is_night=False))
        self.assertFalse(perception.can_see(a, 40, 0, is_night=False))
        self.assertGreater(perception.sight_range(a, False), perception.sight_range(a, True))

    def test_loud_events_carry_by_hearing(self):
        sim = fresh_sim()
        a = sim.agents["bram"]
        a.x, a.y = 0.0, 0.0
        # just out of sight at night, but within earshot for a loud event
        pt = (perception.NIGHT_SIGHT + 2.0, 0.0)
        self.assertFalse(perception.can_see(a, pt[0], pt[1], is_night=True))
        self.assertTrue(perception.can_perceive(a, pt[0], pt[1], is_night=True, loud=True))


class TestWitnessedDeath(unittest.TestCase):
    def test_only_witnesses_learn_of_a_death(self):
        sim = fresh_sim()
        for a in sim.agents.values():          # move everyone far away
            a.x, a.y = 500.0, 500.0
        victim = sim.agents["bram"]; victim.x, victim.y = 0.0, 0.0
        near = sim.agents["toft"]; near.x, near.y = 1.0, 1.0     # a witness
        far = sim.agents["dora"]; far.x, far.y = 500.0, 500.0    # unaware

        sim.kill("bram", cause="a sudden fever")
        self.assertIn("death:bram", near.known_facts)
        self.assertNotIn("death:bram", far.known_facts)
        self.assertTrue(any("bram" in e.text.lower() or "died" in e.text.lower()
                            for e in near.memory.entries))
        self.assertFalse(any("died" in e.text.lower() for e in far.memory.entries))


class TestRumorSpread(unittest.TestCase):
    def test_spread_transfers_a_fact_by_word_of_mouth(self):
        sim = fresh_sim()
        a, b = sim.agents["wren"], sim.agents["pip"] if "pip" in sim.agents else sim.agents["wander"]
        a.known_facts.add("death:elda")
        sim._spread_rumor(a, b)
        self.assertIn("death:elda", b.known_facts)
        self.assertTrue(any("died" in e.text.lower() for e in b.memory.entries))

    def test_news_spreads_beyond_the_witnesses_over_time(self):
        sim = fresh_sim()
        for a in sim.agents.values():
            a.x, a.y = 500.0, 500.0
        victim = sim.agents["bram"]; victim.x, victim.y = 0.0, 0.0
        near = sim.agents["toft"]; near.x, near.y = 1.0, 1.0
        sim.kill("bram", cause="a fall")
        knew_at_death = sum(1 for a in sim.agents.values() if "death:bram" in a.known_facts)
        for _ in range(800):
            sim.tick()
        knew_after = sum(1 for a in sim.agents.values() if "death:bram" in a.known_facts)
        self.assertEqual(knew_at_death, 1)          # only the one witness at first
        self.assertGreater(knew_after, 1)           # word got around


class TestPerceptionPersistence(unittest.TestCase):
    def test_known_facts_survive_save_load(self):
        sim = fresh_sim()
        sim.agents["toft"].known_facts.update({"death:elda", "death:wren"})
        path = os.path.join(tempfile.gettempdir(), "rw_perception.json")
        sim.save(path)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertEqual(sim2.agents["toft"].known_facts, {"death:elda", "death:wren"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
