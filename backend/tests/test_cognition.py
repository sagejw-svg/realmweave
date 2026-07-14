"""Unit tests for Phase 2 cognition: personality, goals, planning, autonomy.

Run from the backend/ directory:  py tests\test_cognition.py
Core acceptance: from one authored village, agents diverge and independently
form and pursue multi-step goals, with no scripting.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig
from realmweave.cognition.personality import seed_personality
from realmweave.cognition.mind import Mind
from realmweave.cognition.goals import Goal, Step


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestPersonality(unittest.TestCase):
    def test_seed_is_deterministic_and_distinct(self):
        self.assertEqual(seed_personality("toft"), seed_personality("toft"))
        self.assertNotEqual(seed_personality("toft"), seed_personality("bram"))

    def test_defaults_fill_missing_traits(self):
        p = seed_personality("nobody")
        self.assertEqual(set(p.keys()), {"ambition", "sociability", "caution",
                                         "greed", "loyalty", "curiosity", "industry"})
        self.assertAlmostEqual(p["ambition"], 0.5)


class TestGoalProposal(unittest.TestCase):
    def test_ambitious_agent_forms_a_multistep_goal(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]
        goal = sim.mind.propose_goal(toft)
        self.assertIsNotNone(goal)
        self.assertGreaterEqual(len(goal.steps), 1)
        # Toft is ambitious+greedy: should aim at a livelihood, and it is multi-step
        self.assertEqual(goal.kind, "build_livelihood")
        self.assertGreater(len(goal.steps), 1)

    def test_goals_differ_by_personality(self):
        sim = fresh_sim()
        kinds = {aid: sim.mind.propose_goal(a).kind for aid, a in sim.agents.items()
                 if sim.mind.propose_goal(a)}
        # the village should not converge on a single shared goal
        self.assertGreater(len(set(kinds.values())), 1)


class TestAutonomyLoop(unittest.TestCase):
    def test_agents_form_and_advance_goals_unscripted(self):
        sim = fresh_sim()
        new_goals, steps_done, completed = [], [], []
        sim.subscribe(lambda e: new_goals.append(e) if e["kind"] == "goal_new" else None)
        sim.subscribe(lambda e: steps_done.append(e) if e["kind"] == "goal_step" else None)
        sim.subscribe(lambda e: completed.append(e) if e["kind"] == "goal_complete" else None)

        for _ in range(400):
            sim.tick()

        self.assertGreaterEqual(len(new_goals), 3, "several agents should self-select goals")
        self.assertGreaterEqual(len(steps_done), 1, "agents should make real progress")
        # at least one agent pursued a genuinely multi-step goal
        multistep = [g for g in new_goals if g["steps"] > 1]
        self.assertTrue(multistep, "expected at least one multi-step goal")

    def test_utility_choice_prioritises_urgent_need_via_override(self):
        sim = fresh_sim()
        a = sim.agents["toft"]
        a.energy.value = 0.05      # desperate for sleep
        sim.mind.maybe_generate_goal(a)
        sim._decide(a)
        self.assertEqual(a.activity, "sleep")   # survival overrides goal/routine


class TestGoalSerialization(unittest.TestCase):
    def test_goal_round_trips(self):
        g = Goal(kind="build_livelihood", description="open a shop", priority=0.9,
                 steps=[Step("save", "work", "smithy", "work", 6),
                        Step("scout", "visit", "square", "visit", 1)], step_index=1)
        g2 = Goal.from_dict(g.to_dict())
        self.assertEqual(g2.kind, g.kind)
        self.assertEqual(g2.step_index, 1)
        self.assertEqual(len(g2.steps), 2)
        self.assertEqual(g2.steps[0].target, 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
