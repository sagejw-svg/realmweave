"""Unit tests for the abstract combat resolver (character-systems phase 2).

Run from the backend/ directory:  py tests\test_combat.py

Covers: the pure exchange mapping (a strong attacker mostly hits, a weak one is
mostly repelled, hits carry a 1..3 severity, fumbles expose the attacker, results
are deterministic per seed); and sim.resolve_combat wiring (a hit wounds the
defender and emits a combat event, a lethal grave hit downs and kills, and open
wounds lower an attacker's offense).
"""
import os
import random
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig
from realmweave.rules.combat import (
    resolve_exchange, ExchangeResult, OFFENSE_SKILLS, DEFENSE_SKILLS,
)
from realmweave.rules.harm import Severity


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestExchangeResolver(unittest.TestCase):
    def test_strong_attacker_mostly_hits(self):
        rng = random.Random(1)
        c = Counter(resolve_exchange(95, 10, rng).result for _ in range(500))
        self.assertGreater(c[ExchangeResult.HIT], c[ExchangeResult.REPELLED])

    def test_weak_attacker_mostly_repelled(self):
        rng = random.Random(2)
        c = Counter(resolve_exchange(10, 95, rng).result for _ in range(500))
        self.assertGreater(c[ExchangeResult.REPELLED], c[ExchangeResult.HIT])

    def test_hits_carry_valid_severity(self):
        rng = random.Random(3)
        for _ in range(1000):
            ex = resolve_exchange(70, 40, rng)
            if ex.result == ExchangeResult.HIT:
                self.assertIn(ex.severity, (int(Severity.GRAZE), int(Severity.HURT), int(Severity.GRAVE)))
            else:
                self.assertEqual(ex.severity, 0)

    def test_fumble_exposes_attacker(self):
        # over many rolls a mid attacker will fumble (roll 96-100) at least once
        rng = random.Random(4)
        results = [resolve_exchange(60, 60, rng).result for _ in range(1000)]
        self.assertIn(ExchangeResult.EXPOSED, results)

    def test_deterministic_per_seed(self):
        a = [resolve_exchange(55, 45, random.Random(9)).result for _ in range(3)]
        b = [resolve_exchange(55, 45, random.Random(9)).result for _ in range(3)]
        self.assertEqual(a, b)


class TestSimResolveCombat(unittest.TestCase):
    def _skew(self, attacker, defender):
        """Make the attacker overwhelmingly likely to land blows."""
        attacker.sheet.skills["Blades"] = 99
        defender.sheet.skills = {}          # untrained defenses (~10)

    def test_hit_wounds_defender_and_emits(self):
        sim = fresh_sim()
        att, dfn = sim.agents["toft"], sim.agents["dora"]
        self._skew(att, dfn)
        events = []
        sim.subscribe(lambda e: events.append(e) if e["kind"] == "combat" else None)
        landed = False
        for _ in range(50):
            ex = sim.resolve_combat(att, dfn)
            if ex.result == ExchangeResult.HIT:
                landed = True
                break
        self.assertTrue(landed)
        self.assertGreaterEqual(len(dfn.wounds), 1)
        self.assertTrue(events and events[-1]["result"] == "hit")

    def test_lethal_grave_hit_kills(self):
        sim = fresh_sim()
        att, dfn = sim.agents["toft"], sim.agents["dora"]
        self._skew(att, dfn)
        deaths = []
        sim.subscribe(lambda e: deaths.append(e) if e["kind"] == "death" else None)
        killed = False
        for _ in range(200):
            if not dfn.alive:
                killed = True
                break
            sim.resolve_combat(att, dfn, lethal=True)
        self.assertTrue(killed)
        self.assertFalse(dfn.alive)
        self.assertTrue(deaths and "slain" in deaths[0]["cause"])

    def test_wounds_lower_offense(self):
        sim = fresh_sim()
        att = sim.agents["toft"]
        base = sim._best_skill(att, OFFENSE_SKILLS)
        att.add_wound(Severity.GRAVE)
        self.assertEqual(att.wound_penalty(), 28)
        effective_off = sim._best_skill(att, OFFENSE_SKILLS) - att.wound_penalty()
        self.assertEqual(effective_off, base - 28)


if __name__ == "__main__":
    unittest.main(verbosity=2)
