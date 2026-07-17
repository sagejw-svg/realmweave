"""Unit tests for Slice B: recipes, gathering, and the supply chain.

Run from the backend/ directory:  py tests\test_supply.py

Covers: primary work gathers raw materials; refining consumes recipe inputs;
inputs are sourced locally when a neighbour has surplus and from the NPC supplier
at a premium otherwise; a broke refiner stalls without crashing; and material
stock survives save/load while pre-v11 saves migrate to empty.
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
from realmweave.economy.recipes import RAW_MATERIALS, premium_price


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


def work_at(a, loc_id):
    a.activity = "work"
    a.current_location = loc_id


class TestGathering(unittest.TestCase):
    def test_field_work_gathers_grain(self):
        sim = fresh_sim()
        dora = sim.agents["dora"]
        work_at(dora, "field")
        for _ in range(400):
            sim._maybe_craft(dora)
        self.assertGreater(dora.materials.get("grain", 0), 0)


class TestSupplyAcquire(unittest.TestCase):
    def test_prefers_local_seller_at_base_price(self):
        sim = fresh_sim()
        buyer, seller = sim.agents["toft"], sim.agents["dora"]
        seller.materials["grain"] = 3
        buyer.coin, seller.coin = 100, 0
        base = RAW_MATERIALS["grain"]
        got = sim.economy.supply.acquire(buyer, "grain", 2)
        self.assertEqual(got, 2)
        self.assertEqual(buyer.materials["grain"], 2)
        self.assertEqual(seller.materials["grain"], 1)      # sold two of three
        self.assertEqual(buyer.coin, 100 - 2 * base)        # paid base, not premium
        self.assertEqual(seller.coin, 2 * base)             # neighbour got paid
        self.assertTrue(any(e["kind"] == "supply" and "local" in e["note"]
                            for e in sim.economy.ledger.entries))

    def test_falls_back_to_premium_supplier(self):
        sim = fresh_sim()
        buyer = sim.agents["toft"]
        buyer.coin = 100
        # no one holds iron, so the supplier is the only source
        got = sim.economy.supply.acquire(buyer, "iron", 1)
        self.assertEqual(got, 1)
        self.assertEqual(buyer.materials["iron"], 1)
        self.assertEqual(buyer.coin, 100 - premium_price("iron"))
        self.assertGreater(premium_price("iron"), RAW_MATERIALS["iron"])   # it IS a premium
        self.assertTrue(any(e["kind"] == "supply" and e["dst"] == "world"
                            for e in sim.economy.ledger.entries))

    def test_broke_agent_secures_nothing(self):
        sim = fresh_sim()
        buyer = sim.agents["toft"]
        buyer.coin = 0
        got = sim.economy.supply.acquire(buyer, "iron", 1)
        self.assertEqual(got, 0)
        self.assertEqual(buyer.materials.get("iron", 0), 0)


class TestRefining(unittest.TestCase):
    def test_refiner_consumes_inputs_and_produces(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]
        toft.materials["iron"] = 5
        toft.coin = 100
        work_at(toft, "smithy")
        crafts = []
        sim.subscribe(lambda e: crafts.append(e) if e["kind"] == "craft" else None)
        for _ in range(400):
            sim._maybe_craft(toft)
        self.assertGreaterEqual(len(crafts), 1)
        self.assertLess(toft.materials["iron"], 5)          # iron was consumed
        # armor landed somewhere (shop if founded, else inventory)
        made = len(toft.inventory) + sum(len(s.stock) for s in sim.economy.shops.values())
        self.assertGreaterEqual(made, 1)

    def test_broke_refiner_stalls_without_crashing(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]
        toft.coin = 0
        toft.materials.clear()
        work_at(toft, "smithy")
        crafts, shortages = [], []
        sim.subscribe(lambda e: crafts.append(e) if e["kind"] == "craft" else None)
        sim.subscribe(lambda e: shortages.append(e) if e["kind"] == "shortage" else None)
        for _ in range(200):
            sim._maybe_craft(toft)                          # must not raise
        self.assertEqual(len(crafts), 0)
        self.assertEqual(toft.materials.get("iron", 0), 0)
        self.assertGreaterEqual(len(shortages), 1)          # it reported the shortage


class TestMaterialsPersistence(unittest.TestCase):
    def test_materials_survive_save_load(self):
        sim = fresh_sim()
        sim.agents["toft"].materials = {"iron": 3, "grain": 1}
        path = os.path.join(tempfile.gettempdir(), "rw_supply.json")
        sim.save(path)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertEqual(sim2.agents["toft"].materials, {"iron": 3, "grain": 1})

    def test_pre_v11_save_migrates_to_empty(self):
        sim = fresh_sim()
        path = os.path.join(tempfile.gettempdir(), "rw_supply_v10.json")
        sim.save(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for ad in data["agents"].values():
            ad.pop("materials", None)
        data["version"] = 10
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertEqual(sim2.agents["toft"].materials, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
