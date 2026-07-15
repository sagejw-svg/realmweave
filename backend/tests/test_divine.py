"""Unit tests for Phase 5 divine influence.

Run from the backend/ directory:  py tests\test_divine.py
Core acceptance: the same suggestion is accepted by an ambitious agent and
refused by a content one, each reacting in character; and god-authored
background/personality seeds identity without dictating behavior.
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
from realmweave.divine.influence import Outcome, infer_thrust


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


SHOP_SUGGESTION = "Sell the shop and seek something greater."
BOLD_THRUST = {"ambition": 1.0, "greed": 0.5}


class TestSuggestion(unittest.TestCase):
    def test_ambitious_accepts_content_refuses_same_suggestion(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]     # ambitious, greedy
        bram = sim.agents["bram"]     # content, social, unambitious
        r_toft = sim.divine.suggest("toft", SHOP_SUGGESTION, thrust=BOLD_THRUST, goal_kind="seek_adventure")
        r_bram = sim.divine.suggest("bram", SHOP_SUGGESTION, thrust=BOLD_THRUST, goal_kind="seek_adventure")
        self.assertEqual(r_toft["outcome"], Outcome.ACCEPT.value)
        self.assertEqual(r_bram["outcome"], Outcome.REFUSE.value)
        # each reacts in character (a non-empty line)
        self.assertTrue(r_toft["reaction"])
        self.assertTrue(r_bram["reaction"])

    def test_accept_applies_a_new_goal_refuse_does_not(self):
        sim = fresh_sim()
        bram_goal_before = sim.agents["bram"].goal
        sim.divine.suggest("toft", SHOP_SUGGESTION, thrust=BOLD_THRUST, goal_kind="seek_adventure")
        sim.divine.suggest("bram", SHOP_SUGGESTION, thrust=BOLD_THRUST, goal_kind="seek_adventure")
        self.assertIsNotNone(sim.agents["toft"].goal)
        self.assertEqual(sim.agents["toft"].goal.kind, "seek_adventure")
        self.assertEqual(sim.agents["bram"].goal, bram_goal_before)   # refusal changed nothing

    def test_disposition_and_favor_shift(self):
        sim = fresh_sim()
        favor_before = sim.divine.favor
        sim.divine.suggest("toft", SHOP_SUGGESTION, thrust=BOLD_THRUST)
        self.assertGreater(sim.agents["toft"].god_disposition, 0.0)   # heeded -> warmer
        self.assertLess(sim.divine.favor, favor_before)              # cost paid
        sim.divine.suggest("bram", SHOP_SUGGESTION, thrust=BOLD_THRUST)
        self.assertLess(sim.agents["bram"].god_disposition, 0.0)     # refused -> cooler

    def test_infer_thrust_reads_keywords(self):
        t = infer_thrust("go seek adventure on the road")
        self.assertIn("curiosity", t)


class TestAuthoring(unittest.TestCase):
    def test_authoring_seeds_identity_without_dictating(self):
        sim = fresh_sim()
        # re-author a formerly content farmer as bold, with a bandit past
        res = sim.divine.author("dora", name="Sam Smith",
                                background="Once rode with a bandit clan; now seeks a clean start.",
                                personality={"ambition": 0.9, "caution": 0.2})
        dora = sim.agents["dora"]
        self.assertEqual(dora.name, "Sam Smith")
        self.assertEqual(dora.personality["ambition"], 0.9)
        # background is seeded into memory, not a scripted action
        self.assertTrue(any("bandit clan" in e.text for e in dora.memory.entries))
        # authoring set no goal: behavior is not dictated
        self.assertIsNone(dora.goal)
        self.assertTrue(res["changed"])

    def test_authored_personality_influences_later_goals(self):
        sim = fresh_sim()
        sim.divine.author("dora", personality={"ambition": 0.95, "greed": 0.8, "caution": 0.1})
        # now the same agent proposes a bolder aim than her content seed would
        goal = sim.mind.propose_goal(sim.agents["dora"])
        self.assertIsNotNone(goal)
        self.assertIn(goal.kind, ("build_livelihood", "seek_adventure"))


class TestDivinePersistence(unittest.TestCase):
    def test_disposition_and_favor_survive_save_load(self):
        sim = fresh_sim()
        sim.divine.suggest("toft", SHOP_SUGGESTION, thrust=BOLD_THRUST)
        disp = sim.agents["toft"].god_disposition
        favor = sim.divine.favor
        path = os.path.join(tempfile.gettempdir(), "rw_divine.json")
        sim.save(path)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertAlmostEqual(sim2.agents["toft"].god_disposition, disp)
        self.assertAlmostEqual(sim2.divine.favor, favor)


if __name__ == "__main__":
    unittest.main(verbosity=2)
