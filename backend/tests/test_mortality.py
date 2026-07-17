"""Tier 1 loop-closing tests: natural mortality, location-gated needs, and the
subsistence floor / stuck watchdog.

Run from the backend/ directory:  py tests\test_mortality.py

These cover the three highest-cost open loops the review found:
  * the world can now produce a death on its own (need-starvation -> health -> death),
  * eating/drinking/sleeping only pay off at the tavern/well/home (not anywhere),
  * no agent can be trapped in an unrecoverable death-spiral (a bare-hands floor).
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
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestLocationGatedNeeds(unittest.TestCase):
    def test_drink_only_pays_off_at_water(self):
        sim = fresh_sim()
        a = sim.agents["toft"]
        a.activity = "drink"
        # at the well: thirst rises
        a.current_location = "well"
        a.thirst.value = 0.3
        sim._activity_effects(a)
        self.assertGreater(a.thirst.value, 0.3)
        # in a bedroom: the same activity does nothing (you must go to water)
        a.current_location = "home_toft"
        a.thirst.value = 0.3
        sim._activity_effects(a)
        self.assertEqual(a.thirst.value, 0.3)

    def test_eat_only_pays_off_at_tavern(self):
        sim = fresh_sim()
        a = sim.agents["isla"]
        a.activity = "eat"
        a.current_location = "tavern"
        a.hunger.value = 0.3
        sim._activity_effects(a)
        self.assertGreater(a.hunger.value, 0.3)
        a.current_location = "smithy"
        a.hunger.value = 0.3
        sim._activity_effects(a)
        self.assertEqual(a.hunger.value, 0.3)

    def test_sleep_only_pays_off_at_home(self):
        sim = fresh_sim()
        a = sim.agents["isla"]
        a.activity = "sleep"
        a.current_location = "home_isla"
        a.energy.value = 0.3
        sim._activity_effects(a)
        self.assertGreater(a.energy.value, 0.3)
        a.current_location = "field"
        a.energy.value = 0.3
        sim._activity_effects(a)
        self.assertEqual(a.energy.value, 0.3)

    def test_guard_sleeps_at_his_post(self):
        # the guard's "home" is the gate; sleeping there must still restore energy
        sim = fresh_sim()
        g = sim.agents["guard"]
        self.assertEqual(g.home, "gate")
        g.activity = "sleep"
        g.current_location = "gate"
        g.energy.value = 0.3
        sim._activity_effects(g)
        self.assertGreater(g.energy.value, 0.3)


class TestMortality(unittest.TestCase):
    def test_starvation_drains_health_then_kills(self):
        sim = fresh_sim()
        a = sim.agents["dora"]
        deaths = []
        sim.subscribe(lambda e: deaths.append(e) if e["kind"] == "death" else None)
        a.energy.value = 0.0
        a.thirst.value = 0.0
        a.hunger.value = 0.0
        a.health = 1.0
        # each call bleeds health; with three needs starving it drops fast
        for _ in range(200):
            sim._mortality(a)
            if not a.alive:
                break
        self.assertFalse(a.alive)
        self.assertEqual(a.health, 0.0)
        self.assertEqual(len(deaths), 1)
        self.assertIn(deaths[0]["cause"], ("exhaustion", "thirst", "hunger"))

    def test_wellfed_agent_regenerates_health(self):
        sim = fresh_sim()
        a = sim.agents["dora"]
        a.energy.value = a.thirst.value = a.hunger.value = 0.8
        a.health = 0.5
        sim._mortality(a)
        self.assertGreater(a.health, 0.5)
        self.assertTrue(a.alive)

    def test_illness_roll_can_kill_when_enabled(self):
        sim = fresh_sim()
        sim.cfg.illness_chance = 1.0     # certainty for the test
        a = sim.agents["wren"]
        a.energy.value = a.thirst.value = a.hunger.value = 0.9   # not starving
        sim._mortality(a)
        self.assertFalse(a.alive)

    def test_healthy_village_has_no_spontaneous_deaths(self):
        # with illness off (default) a seeded run must never kill anyone: agents
        # reach food/water/home and location-gating does not starve them.
        sim = fresh_sim()
        deaths = []
        sim.subscribe(lambda e: deaths.append(e) if e["kind"] == "death" else None)
        for _ in range(300):
            sim.tick()
        self.assertEqual(deaths, [])
        self.assertTrue(all(a.alive for a in sim.agents.values()))


class TestSubsistenceFloor(unittest.TestCase):
    def test_stuck_agent_is_flagged_and_forages_to_survive(self):
        sim = fresh_sim()
        a = sim.agents["bram"]
        stuck = []
        sim.subscribe(lambda e: stuck.append(e) if e["kind"] == "stuck" else None)
        a.energy.value = 0.8
        a.hunger.value = 0.8
        a.thirst.value = 0.0            # a need pinned critically low
        a.health = 1.0
        for _ in range(40):
            sim._survival_watchdog(a)
            sim._mortality(a)
        # the floor fires exactly once and keeps the agent alive despite the need
        self.assertEqual(len(stuck), 1)
        self.assertTrue(a.alive)
        self.assertGreater(a.thirst.value, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
