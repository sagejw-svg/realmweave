"""Unit tests for the harm/wound foundation (character-systems phase 1).

Run from the backend/ directory:  py tests\test_harm.py

Covers: check-degree -> wound severity mapping; wound penalties and the bounded
total; agent add_wound/wound_penalty; natural mending closes wounds (graze fast,
grave slow) with a rest bonus; open wounds bleed health so a grave wound can kill
via the existing mortality path; and wounds survive save/load while pre-v13 saves
migrate to unwounded.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig
from realmweave.rules.checks import Outcome
from realmweave.rules.harm import (
    Wound, Severity, severity_from_outcome, total_penalty, worst_severity,
)


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


def well_fed(a):
    """Put an agent in no danger of starvation so mortality isolates wounds."""
    for n in (a.energy, a.hunger, a.thirst, a.social):
        n.value = 1.0


class TestSeverityMapping(unittest.TestCase):
    def test_outcome_to_severity(self):
        self.assertEqual(severity_from_outcome(Outcome.CRIT_SUCCESS), Severity.GRAVE)
        self.assertEqual(severity_from_outcome(Outcome.SUCCESS), Severity.HURT)
        self.assertEqual(severity_from_outcome(Outcome.PARTIAL), Severity.GRAZE)
        self.assertIsNone(severity_from_outcome(Outcome.FAILURE))
        self.assertIsNone(severity_from_outcome(Outcome.FUMBLE))


class TestPenalties(unittest.TestCase):
    def test_penalty_increases_with_severity(self):
        g = Wound(Severity.GRAZE); h = Wound(Severity.HURT); v = Wound(Severity.GRAVE)
        self.assertLess(g.penalty(), h.penalty())
        self.assertLess(h.penalty(), v.penalty())

    def test_total_penalty_is_bounded(self):
        many = [Wound(Severity.GRAVE) for _ in range(10)]
        self.assertEqual(total_penalty(many), 60)   # MAX_PENALTY cap
        self.assertEqual(total_penalty([]), 0)
        self.assertEqual(worst_severity(many), 3)
        self.assertEqual(worst_severity([]), 0)


class TestAgentWounds(unittest.TestCase):
    def test_add_wound_and_penalty(self):
        sim = fresh_sim()
        a = sim.agents["toft"]
        self.assertEqual(a.wound_penalty(), 0)
        a.add_wound(Severity.HURT, source="Blades (test)")
        self.assertEqual(len(a.wounds), 1)
        self.assertEqual(a.wound_penalty(), Wound(Severity.HURT).penalty())


class TestHealing(unittest.TestCase):
    def test_wounds_close_over_time_graze_before_grave(self):
        sim = fresh_sim()
        g = sim.agents["toft"]; v = sim.agents["dora"]
        well_fed(g); well_fed(v)
        g.add_wound(Severity.GRAZE); v.add_wound(Severity.GRAVE)
        graze_ticks = None
        for t in range(1, 400):
            sim._tick_wounds(g); sim._tick_wounds(v)
            if graze_ticks is None and not g.wounds:
                graze_ticks = t
            if not v.wounds:
                self.assertIsNotNone(graze_ticks)
                self.assertLess(graze_ticks, t)   # graze healed well before grave
                break
        else:
            self.fail("grave wound never closed")

    def test_rest_speeds_healing(self):
        sim = fresh_sim()
        rester = sim.agents["toft"]; worker = sim.agents["dora"]
        well_fed(rester); well_fed(worker)
        rester.activity = "sleep"; worker.activity = "work"
        rester.add_wound(Severity.HURT); worker.add_wound(Severity.HURT)
        rest_done = work_done = None
        for t in range(1, 400):
            if rester.wounds: sim._tick_wounds(rester)
            elif rest_done is None: rest_done = t
            if worker.wounds: sim._tick_wounds(worker)
            elif work_done is None: work_done = t
            if rest_done and work_done:
                break
        self.assertLess(rest_done, work_done)


class TestMortalityIntegration(unittest.TestCase):
    def test_graze_does_not_bleed_health(self):
        sim = fresh_sim()
        a = sim.agents["toft"]; well_fed(a)
        a.health = 0.5
        a.add_wound(Severity.GRAZE)
        sim._mortality(a)
        self.assertGreaterEqual(a.health, 0.5)   # a graze costs no health

    def test_grave_wound_can_kill_via_mortality(self):
        sim = fresh_sim()
        a = sim.agents["toft"]; well_fed(a)
        a.health = 0.1                      # already frail
        a.add_wound(Severity.GRAVE)
        deaths = []
        sim.subscribe(lambda e: deaths.append(e) if e["kind"] == "death" else None)
        for _ in range(60):
            well_fed(a)                     # keep needs full so only the wound bites
            sim._tick_wounds(a)
            sim._mortality(a)
            if not a.alive:
                break
        self.assertFalse(a.alive)
        self.assertTrue(deaths and "wound" in deaths[0]["cause"])


class TestPersistence(unittest.TestCase):
    def test_wounds_survive_save_load(self):
        sim = fresh_sim()
        sim.agents["toft"].add_wound(Severity.GRAVE, source="Blades (bandit)")
        sim.agents["toft"].wounds[0].mend = 0.4
        path = os.path.join(tempfile.gettempdir(), "rw_harm.json")
        sim.save(path)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        w = sim2.agents["toft"].wounds
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0].severity, int(Severity.GRAVE))
        self.assertAlmostEqual(w[0].mend, 0.4, places=3)
        self.assertEqual(w[0].source, "Blades (bandit)")

    def test_pre_v13_save_migrates_to_unwounded(self):
        sim = fresh_sim()
        sim.agents["toft"].add_wound(Severity.HURT)
        path = os.path.join(tempfile.gettempdir(), "rw_harm_v12.json")
        sim.save(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for ad in data["agents"].values():
            ad.pop("wounds", None)
        data["version"] = 12
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertEqual(sim2.agents["toft"].wounds, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
