"""Tier 1: the player can act on the economy, not just watch it.

Run from the backend/ directory:  py tests\test_player_trade.py

Covers player_buy (purchase from a nearby shop, authoritative coin/stock moves)
and player_give (a gift the receiving NPC remembers, with an affinity bump - the
single best emergent-story beat).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig
from realmweave.economy.goods import make_item


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


def toft_shop(sim):
    toft = sim.agents["toft"]
    toft.inventory = [make_item("Smithing", 40), make_item("Smithing", 80)]
    return sim.economy.found_shop(toft), toft


class TestPlayerBuy(unittest.TestCase):
    def test_buy_moves_coin_and_stock_authoritatively(self):
        sim = fresh_sim()
        shop, toft = toft_shop(sim)
        toft.coin = 0
        stock_before = len(shop.stock)
        res = sim.player_buy("Trav", shop.x, shop.y, coin=1000)
        self.assertTrue(res["ok"])
        self.assertGreater(res["price"], 0)
        self.assertEqual(len(shop.stock), stock_before - 1)   # one item left the shelf
        self.assertEqual(toft.coin, res["price"])             # the owner was paid

    def test_cannot_afford_is_rejected(self):
        sim = fresh_sim()
        shop, _ = toft_shop(sim)
        res = sim.player_buy("Trav", shop.x, shop.y, coin=0)
        self.assertFalse(res["ok"])
        self.assertEqual(len(shop.stock), 2)                  # nothing moved

    def test_no_shop_within_reach(self):
        sim = fresh_sim()
        toft_shop(sim)
        res = sim.player_buy("Trav", 0.0, 0.0, coin=1000)     # far from any shop
        self.assertFalse(res["ok"])

    def test_item_index_selects_a_specific_good(self):
        sim = fresh_sim()
        shop, _ = toft_shop(sim)
        want = shop.stock[1]
        res = sim.player_buy("Trav", shop.x, shop.y, coin=100000, item_index=1)
        self.assertTrue(res["ok"])
        self.assertNotIn(want, shop.stock)


class TestPlayerGive(unittest.TestCase):
    def test_gift_coin_is_remembered_and_lifts_affinity(self):
        sim = fresh_sim()
        a = sim.agents["elda"]
        coin_before = a.coin
        res = sim.player_give("Trav", a.x, a.y, amount=50)
        self.assertTrue(res["ok"])
        self.assertEqual(a.coin, coin_before + 50)
        self.assertGreater(a.affinity("player:Trav"), 0.0)
        self.assertTrue(any("gave me" in e.text for e in a.memory.entries))

    def test_gift_with_no_recipient_nearby(self):
        sim = fresh_sim()
        res = sim.player_give("Trav", -50.0, -50.0, amount=10)
        self.assertFalse(res["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
