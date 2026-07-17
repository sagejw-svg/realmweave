"""Unit tests for mining: the Mining skill, the mine gathering site, the weighted
ore table, and the miner seeded into Oakhollow.

Run from the backend/ directory:  py tests\test_mining.py

Covers: working the mine yields ore drawn from ORE_TABLE; every ore in the table
is reachable and iron/coal dominate; roll_ore is deterministic for a seed; the
Mining skill and Miner role seed exist; the miner is placed next to the mine; and
Smithing now consumes iron and coal, sourced locally from the miner when he has
surplus.
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
from realmweave.economy.recipes import ORE_TABLE, RAW_MATERIALS, RECIPES, roll_ore
from realmweave.rules.skills import SKILL_CATALOG, role_sheet


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


def work_at(a, loc_id):
    a.activity = "work"
    a.current_location = loc_id


class TestOreTable(unittest.TestCase):
    def test_every_ore_is_priced(self):
        for material, _ in ORE_TABLE:
            self.assertIn(material, RAW_MATERIALS, f"{material} missing a base value")

    def test_roll_ore_is_deterministic(self):
        seq_a = [roll_ore(r) for r in [random.Random(42)]] + \
                [roll_ore(random.Random(42)) for _ in range(5)]
        seq_b = [roll_ore(r) for r in [random.Random(42)]] + \
                [roll_ore(random.Random(42)) for _ in range(5)]
        self.assertEqual(seq_a, seq_b)

    def test_distribution_reaches_every_ore_and_favours_common(self):
        rng = random.Random(1)
        draws = Counter(roll_ore(rng) for _ in range(20000))
        for material, _ in ORE_TABLE:
            self.assertGreater(draws[material], 0, f"{material} never rolled")
        # iron and coal (the forge inputs) should be the two most common
        top_two = {m for m, _ in draws.most_common(2)}
        self.assertEqual(top_two, {"iron", "coal"})
        self.assertGreater(draws["iron"], draws["gold"])
        self.assertGreater(draws["coal"], draws["silver"])


class TestMiningSkill(unittest.TestCase):
    def test_mining_skill_registered(self):
        self.assertIn("Mining", SKILL_CATALOG)

    def test_miner_role_seed_trains_mining(self):
        sheet = role_sheet("Miner")
        self.assertGreaterEqual(sheet.skill("Mining"), 60)


class TestMineGathering(unittest.TestCase):
    def test_mine_work_yields_ore(self):
        sim = fresh_sim()
        gart = sim.agents["gart"]
        work_at(gart, "mine")
        gathered = []
        sim.subscribe(lambda e: gathered.append(e) if e["kind"] == "gather" else None)
        for _ in range(600):
            sim._maybe_craft(gart)
        total = sum(gart.materials.get(m, 0) for m, _ in ORE_TABLE)
        self.assertGreater(total, 0)
        self.assertTrue(gathered)

    def test_miner_lives_beside_the_mine(self):
        sim = fresh_sim()
        gart = sim.agents["gart"]
        self.assertEqual(gart.home, "home_gart")
        mine = sim.world.loc("mine")
        home = sim.world.loc("home_gart")
        dist = abs(mine.x - home.x) + abs(mine.y - home.y)
        self.assertLessEqual(dist, 12)   # home is adjacent, not across the map


class TestSmithingUsesCoal(unittest.TestCase):
    def test_smithing_recipe_needs_iron_and_coal(self):
        inputs = dict(RECIPES["Smithing"])
        self.assertEqual(inputs.get("iron"), 1)
        self.assertEqual(inputs.get("coal"), 1)

    def test_smith_buys_forge_inputs_locally_from_miner(self):
        sim = fresh_sim()
        toft, gart = sim.agents["toft"], sim.agents["gart"]
        gart.materials["iron"] = 5
        gart.materials["coal"] = 5
        toft.coin, gart.coin = 200, 0
        base_iron, base_coal = RAW_MATERIALS["iron"], RAW_MATERIALS["coal"]
        got_iron = sim.economy.supply.acquire(toft, "iron", 1)
        got_coal = sim.economy.supply.acquire(toft, "coal", 1)
        self.assertEqual((got_iron, got_coal), (1, 1))
        self.assertEqual(gart.coin, base_iron + base_coal)   # miner earned the sale
        self.assertTrue(any(e["kind"] == "supply" and "local" in e["note"]
                            for e in sim.economy.ledger.entries))


if __name__ == "__main__":
    unittest.main(verbosity=2)
