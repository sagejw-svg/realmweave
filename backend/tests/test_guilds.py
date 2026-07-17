"""Unit tests for Slice C: guilds and factions.

Run from the backend/ directory:  py tests\test_guilds.py

Covers: the guard is seeded into the lawful faction; joining sets rank and renown;
ranks rise with tenure; dues flow to the coffer through the ledger; merchant-guild
members get a cheaper supplier premium; fighters'-guild members are deputized into
pursuits; a join_guild goal enrolls the agent; and guild state survives save/load
while pre-v12 saves migrate to the seeded default.
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
from realmweave.cognition.goals import Goal
from realmweave.economy.recipes import premium_price, RAW_MATERIALS
from realmweave.factions.guilds import best_guild_for, MERCHANT_DISCOUNT


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


def set_day(sim, day):
    sim.clock.minutes = day * 1440


def next_day(sim):
    set_day(sim, sim.clock.day_index + 1)
    sim.guilds.step()


class TestSeedAndMembership(unittest.TestCase):
    def test_guard_is_seeded_into_fighters(self):
        sim = fresh_sim()
        self.assertEqual(sim.guilds.guild_of("guard"), "fighters")
        self.assertTrue(sim.guilds.is_member(sim.agents["guard"], "fighters"))
        self.assertEqual(sim.guilds.rank_of("guard"), 1)
        self.assertEqual(sim.guilds.title_of("guard"), "Recruit")

    def test_join_sets_rank_and_renown(self):
        sim = fresh_sim()
        dora = sim.agents["dora"]
        self.assertTrue(sim.guilds.join(dora, "merchants"))
        self.assertEqual(sim.guilds.guild_of("dora"), "merchants")
        self.assertEqual(sim.guilds.title_of("dora"), "Peddler")
        self.assertGreater(dora.reputation.get("merchants", 0.0), 0.0)

    def test_rank_rises_with_tenure(self):
        sim = fresh_sim()
        sim.guilds.join(sim.agents["toft"], "fighters")   # joined on day 0
        self.assertEqual(sim.guilds.rank_of("toft"), 1)
        set_day(sim, 3)
        self.assertEqual(sim.guilds.rank_of("toft"), 2)
        set_day(sim, 9)
        self.assertEqual(sim.guilds.rank_of("toft"), 4)
        set_day(sim, 100)
        self.assertEqual(sim.guilds.rank_of("toft"), 4)   # capped at MAX_RANK


class TestDues(unittest.TestCase):
    def test_dues_flow_to_coffer_and_ledger(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]
        toft.coin = 100
        sim.guilds.join(toft, "merchants")
        next_day(sim)
        self.assertGreaterEqual(sim.guilds.coffers["merchants"], 3)
        self.assertLessEqual(toft.coin, 97)
        self.assertTrue(any(e["kind"] == "dues" and e["src"] == "toft"
                            for e in sim.economy.ledger.entries))


class TestBenefits(unittest.TestCase):
    def test_merchant_member_gets_supplier_discount(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]
        toft.coin = 100
        sim.guilds.join(toft, "merchants")
        got = sim.economy.supply.acquire(toft, "iron", 1)
        self.assertEqual(got, 1)
        discounted = int(premium_price("iron") * MERCHANT_DISCOUNT)
        self.assertEqual(toft.coin, 100 - discounted)

    def test_non_member_pays_full_premium(self):
        sim = fresh_sim()
        isla = sim.agents["isla"]
        isla.coin = 100
        got = sim.economy.supply.acquire(isla, "iron", 1)   # no local iron in a fresh world
        self.assertEqual(got, 1)
        self.assertEqual(isla.coin, 100 - premium_price("iron"))

    def test_fighters_member_is_deputized_for_pursuit(self):
        sim = fresh_sim()
        perp = sim.agents["toft"]
        perp.wanted = 1
        bram = sim.agents["bram"]
        bram.personality["loyalty"] = 0.0          # would not chase on his own
        bram.known_facts.add("wanted:toft")
        self.assertNotIn(bram, sim.justice.pursuers_of(perp))
        sim.guilds.join(bram, "fighters")
        self.assertIn(bram, sim.justice.pursuers_of(perp))


class TestJoinGuildGoal(unittest.TestCase):
    def test_completing_join_goal_enrolls_agent(self):
        sim = fresh_sim()
        dora = sim.agents["dora"]
        goal = Goal(kind="join_guild", description="join a guild", priority=0.9, steps=[])
        sim._on_goal_complete(dora, goal)
        self.assertEqual(sim.guilds.guild_of("dora"), best_guild_for(dora))

    def test_shopkeeper_proposes_join_guild(self):
        sim = fresh_sim()
        dora = sim.agents["dora"]
        sim.economy.found_shop(dora)               # now an established owner
        dora.personality["sociability"] = 1.0
        dora.personality["ambition"] = 1.0
        goal = sim.mind.propose_goal(dora)
        self.assertIsNotNone(goal)
        self.assertEqual(goal.kind, "join_guild")


class TestGuildPersistence(unittest.TestCase):
    def test_guilds_survive_save_load(self):
        sim = fresh_sim()
        sim.guilds.join(sim.agents["toft"], "mages")
        sim.guilds.coffers["mages"] = 7
        path = os.path.join(tempfile.gettempdir(), "rw_guilds.json")
        sim.save(path)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertEqual(sim2.guilds.guild_of("toft"), "mages")
        self.assertEqual(sim2.guilds.guild_of("guard"), "fighters")
        self.assertEqual(sim2.guilds.coffers["mages"], 7)

    def test_pre_v12_save_keeps_seeded_default(self):
        sim = fresh_sim()
        path = os.path.join(tempfile.gettempdir(), "rw_guilds_v11.json")
        sim.save(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.pop("guilds", None)
        data["version"] = 11
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertEqual(sim2.guilds.guild_of("guard"), "fighters")
        self.assertEqual(sim2.guilds.guild_of("toft"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
