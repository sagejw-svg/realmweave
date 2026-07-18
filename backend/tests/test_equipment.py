"""Unit tests for equipment/armor (character-systems phase 3).

Run from the backend/ directory:  py tests\test_equipment.py

Covers: slot/skill/mod helpers; Agent equip/unequip (inventory bookkeeping and
displacement); combat integration (a weapon raises hit rate, armor reduces grave
outcomes); the guard is seeded with gear; and equipment survives save/load while
pre-v14 saves keep seeded gear.
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
from realmweave.economy.goods import Item, BASE_VALUES
from realmweave.rules.combat import ExchangeResult
from realmweave.rules import equipment as eq


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


def weapon(q=80):
    return Item("a fine blade", "weapon", q, BASE_VALUES["weapon"])


def bow(q=50):
    return Item("a hunting bow", "weapon", q, BASE_VALUES["weapon"])


def mail(q=90):
    return Item("a coat of mail", "armor", q, BASE_VALUES["armor"])


class TestHelpers(unittest.TestCase):
    def test_slot_for(self):
        self.assertEqual(eq.slot_for(weapon()), "weapon")
        self.assertEqual(eq.slot_for(mail()), "armor")
        self.assertEqual(eq.slot_for(Item("a charm", "good", 30, 12)), "trinket")

    def test_weapon_skill_and_mod(self):
        self.assertEqual(eq.weapon_skill(bow()), "Archery")
        self.assertEqual(eq.weapon_skill(weapon()), "Blades")
        self.assertLess(eq.weapon_offense_mod(weapon(20)), eq.weapon_offense_mod(weapon(100)))

    def test_armor_scales_with_quality(self):
        self.assertLess(eq.armor_mitigation_chance(mail(10)), eq.armor_mitigation_chance(mail(100)))
        self.assertGreater(eq.armor_evasion_penalty(mail()), 0)


class TestEquipUnequip(unittest.TestCase):
    def test_equip_from_inventory_and_displace(self):
        sim = fresh_sim()
        a = sim.agents["toft"]
        w1, w2 = weapon(40), weapon(90)
        a.inventory.extend([w1, w2])
        self.assertIsNone(a.equip(w1))
        self.assertEqual(a.equipment["weapon"], w1)
        self.assertNotIn(w1, a.inventory)
        # equipping a second weapon displaces the first back to inventory
        displaced = a.equip(w2)
        self.assertEqual(displaced, w1)
        self.assertIn(w1, a.inventory)
        self.assertEqual(a.equipment["weapon"], w2)

    def test_unequip_returns_to_inventory(self):
        sim = fresh_sim()
        a = sim.agents["toft"]
        m = mail()
        a.equip(m)
        self.assertEqual(a.unequip("armor"), m)
        self.assertIn(m, a.inventory)
        self.assertNotIn("armor", a.equipment)


class TestGuardSeededGear(unittest.TestCase):
    def test_guard_has_blade_and_mail(self):
        sim = fresh_sim()
        guard = sim.agents["guard"]
        self.assertIn("weapon", guard.equipment)
        self.assertIn("armor", guard.equipment)


class TestCombatIntegration(unittest.TestCase):
    def _hits(self, with_weapon):
        """Count hits over a fixed number of exchanges at matched skill, seeded."""
        sim = fresh_sim()
        att, dfn = sim.agents["toft"], sim.agents["dora"]
        att.sheet.skills["Blades"] = 45
        dfn.sheet.skills = {"Athletics": 45}
        if with_weapon:
            att.equip(weapon(80))
        hits = 0
        for _ in range(300):
            if sim.resolve_combat(att, dfn).result == ExchangeResult.HIT:
                hits += 1
            dfn.wounds.clear()          # isolate each exchange from wound penalties
        return hits

    def test_weapon_raises_hit_rate(self):
        self.assertGreater(self._hits(with_weapon=True), self._hits(with_weapon=False))

    def _grave_count(self, with_armor):
        sim = fresh_sim()
        att, dfn = sim.agents["toft"], sim.agents["dora"]
        att.sheet.skills["Blades"] = 99
        dfn.sheet.skills = {}           # ~untrained defenses
        if with_armor:
            dfn.equip(mail(90))
        graves = 0
        for _ in range(400):
            sim.resolve_combat(att, dfn)
            graves += sum(1 for w in dfn.wounds if w.severity == 3)
            dfn.wounds.clear()
        return graves

    def test_armor_reduces_grave_wounds(self):
        self.assertLess(self._grave_count(with_armor=True), self._grave_count(with_armor=False))


class TestPersistence(unittest.TestCase):
    def test_equipment_survives_save_load(self):
        sim = fresh_sim()
        sim.agents["toft"].equip(weapon(70))
        path = os.path.join(tempfile.gettempdir(), "rw_equip.json")
        sim.save(path)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        w = sim2.agents["toft"].equipment.get("weapon")
        self.assertIsNotNone(w)
        self.assertEqual(w.quality, 70)
        # and the guard's seeded gear round-trips
        self.assertIn("armor", sim2.agents["guard"].equipment)

    def test_pre_v14_save_keeps_seeded_gear(self):
        sim = fresh_sim()
        path = os.path.join(tempfile.gettempdir(), "rw_equip_v13.json")
        sim.save(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for ad in data["agents"].values():
            ad.pop("equipment", None)
        data["version"] = 13
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        # no equipment in the save -> the guard keeps its authored blade and mail
        self.assertIn("weapon", sim2.agents["guard"].equipment)


if __name__ == "__main__":
    unittest.main(verbosity=2)
