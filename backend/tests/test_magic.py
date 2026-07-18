"""Unit tests for magic (character-systems phase 4).

Run from the backend/ directory:  py tests\test_magic.py

Covers: focus capacity scaling; casting economy (focus spent, insufficient focus
fails, regen and ward decay over ticks); the four spells (mend heals a wound, bolt
wounds a target, ward raises defense in combat, frighten drops a pursuit); and
focus/ward survive save/load while pre-v15 saves lazy-fill.
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
from realmweave.rules.magic import max_focus, SPELLS, WARD_TICKS
from realmweave.rules.harm import Severity
from realmweave.rules.combat import ExchangeResult


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestFocus(unittest.TestCase):
    def test_max_focus_scales_with_attributes(self):
        sim = fresh_sim()
        a = sim.agents["elda"]
        base = max_focus(a.sheet)
        a.sheet.attributes["Intellect"] = 100
        a.sheet.attributes["Presence"] = 100
        self.assertGreater(max_focus(a.sheet), base)

    def test_insufficient_focus_fails(self):
        sim = fresh_sim()
        a = sim.agents["elda"]
        a.ensure_focus()
        a.focus = 0.0
        res = sim.cast(a, "mend")
        self.assertFalse(res["ok"])

    def test_cast_spends_focus(self):
        sim = fresh_sim()
        a = sim.agents["elda"]
        a.focus = 12.0
        sim.cast(a, "ward")
        self.assertAlmostEqual(a.focus, 12.0 - SPELLS["ward"].cost, places=3)

    def test_focus_regens_and_ward_decays(self):
        sim = fresh_sim()
        a = sim.agents["elda"]
        a.activity = "sleep"
        a.focus = 1.0
        a.warded = 3
        for _ in range(5):
            sim._tick_magic(a)
        self.assertGreater(a.focus, 1.0)
        self.assertLess(a.warded, 3)


class TestSpells(unittest.TestCase):
    def test_mend_heals_a_wound(self):
        sim = fresh_sim()
        healer, patient = sim.agents["elda"], sim.agents["toft"]
        healer.sheet.skills["Faith"] = 99
        patient.add_wound(Severity.GRAVE)
        before = patient.wounds[0].severity
        for _ in range(40):
            healer.focus = 20.0
            res = sim.cast(healer, "mend", target=patient)
            if res["effect"] in ("healed", "healed_fully"):
                break
        # either the grave wound was stepped down or cleared entirely
        healed = (not patient.wounds) or patient.wounds[0].severity < before
        self.assertTrue(healed)

    def test_bolt_wounds_a_target(self):
        sim = fresh_sim()
        mage, foe = sim.agents["elda"], sim.agents["toft"]
        mage.sheet.skills["Arcana"] = 99
        struck = False
        for _ in range(40):
            mage.focus = 20.0
            if sim.cast(mage, "bolt", target=foe)["effect"] == "struck":
                struck = True
                break
        self.assertTrue(struck)
        self.assertGreaterEqual(len(foe.wounds), 1)

    def test_ward_raises_defense_in_combat(self):
        def hits_with_ward(warded):
            sim = fresh_sim()
            att, dfn = sim.agents["toft"], sim.agents["dora"]
            att.sheet.skills["Blades"] = 55
            dfn.sheet.skills = {"Athletics": 55}
            if warded:
                dfn.warded = 9999      # hold the ward across the sample
            hits = 0
            for _ in range(300):
                if sim.resolve_combat(att, dfn).result == ExchangeResult.HIT:
                    hits += 1
                dfn.wounds.clear()
            return hits
        self.assertLess(hits_with_ward(True), hits_with_ward(False))

    def test_frighten_drops_a_pursuit(self):
        sim = fresh_sim()
        caster, foe = sim.agents["elda"], sim.agents["toft"]
        caster.sheet.skills["Faith"] = 99
        setattr(foe, "_pursuing", "someone")
        for _ in range(20):
            caster.focus = 20.0
            if sim.cast(caster, "frighten", target=foe)["effect"] == "routed":
                break
        self.assertEqual(getattr(foe, "_pursuing", ""), "")


class TestPersistence(unittest.TestCase):
    def test_focus_and_ward_survive_save_load(self):
        sim = fresh_sim()
        sim.agents["elda"].focus = 7.0
        sim.agents["elda"].warded = 3
        path = os.path.join(tempfile.gettempdir(), "rw_magic.json")
        sim.save(path)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertAlmostEqual(sim2.agents["elda"].focus, 7.0, places=3)
        self.assertEqual(sim2.agents["elda"].warded, 3)

    def test_pre_v15_save_lazy_fills(self):
        sim = fresh_sim()
        path = os.path.join(tempfile.gettempdir(), "rw_magic_v14.json")
        sim.save(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for ad in data["agents"].values():
            ad.pop("focus", None); ad.pop("warded", None)
        data["version"] = 14
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        a = sim2.agents["elda"]
        self.assertEqual(a.warded, 0)
        self.assertLess(a.focus, 0)              # uninitialized sentinel
        self.assertGreater(a.ensure_focus(), 0)  # lazy-fills to capacity
