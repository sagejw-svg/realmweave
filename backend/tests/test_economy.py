"""Unit tests for Phase 3 economy: goods, pricing, shops, and trade.

Run from the backend/ directory:  py tests\test_economy.py
Core acceptance: an ambitious agent founds a shop unprompted and completes at
least one sale, and shops/coin survive save/load.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig
from realmweave.economy.goods import Item, make_item


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestGoods(unittest.TestCase):
    def test_value_scales_with_quality(self):
        low = Item("armor", "armor", 10, 40)
        mid = Item("armor", "armor", 50, 40)
        high = Item("armor", "armor", 100, 40)
        self.assertLess(low.value(), mid.value())
        self.assertLess(mid.value(), high.value())
        self.assertEqual(mid.value(), 40)          # q50 == base value

    def test_make_item_from_skill(self):
        it = make_item("Smithing", 70)
        self.assertEqual(it.category, "armor")
        self.assertGreater(it.value(), 0)


class TestShopAndTrade(unittest.TestCase):
    def test_found_shop_moves_inventory_to_stock(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]
        toft.inventory = [make_item("Smithing", 60), make_item("Smithing", 80)]
        shop = sim.economy.found_shop(toft)
        self.assertIsNotNone(shop)
        self.assertEqual(len(shop.stock), 2)
        self.assertEqual(toft.inventory, [])
        # the shop is now a real, visitable location in the world
        self.assertIn(shop.location_id, sim.world.locations)

    def test_price_includes_margin(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]
        toft.inventory = [make_item("Smithing", 50)]
        shop = sim.economy.found_shop(toft)
        item = shop.stock[0]
        # no buyer -> no haggle; price is value plus the owner's margin
        self.assertGreater(sim.economy.price_of(shop, item), item.value())

    def test_buy_transfers_coin_and_item(self):
        sim = fresh_sim()
        toft, isla = sim.agents["toft"], sim.agents["isla"]
        toft.inventory = [make_item("Smithing", 50)]
        shop = sim.economy.found_shop(toft)
        item = shop.stock[0]
        toft.coin, isla.coin = 0, 500
        price = sim.economy.buy(isla, shop, item)
        self.assertIsNotNone(price)
        self.assertEqual(toft.coin, price)         # seller got paid
        self.assertEqual(isla.coin, 500 - price)   # buyer paid
        self.assertNotIn(item, shop.stock)         # stock decremented
        self.assertIn(item, isla.inventory)        # buyer holds the good


class TestEmergentLivelihood(unittest.TestCase):
    def test_agent_founds_shop_and_sells_unprompted(self):
        sim = fresh_sim()
        founded, trades = [], []
        sim.subscribe(lambda e: founded.append(e) if e["kind"] == "shop_founded" else None)
        sim.subscribe(lambda e: trades.append(e) if e["kind"] == "trade" else None)
        for _ in range(900):
            sim.tick()
        self.assertGreaterEqual(len(founded), 1, "an agent should open a shop unprompted")
        self.assertGreaterEqual(len(trades), 1, "at least one sale should complete")


class TestEconomyPersistence(unittest.TestCase):
    def test_shops_and_coin_survive_save_load(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]
        toft.inventory = [make_item("Smithing", 70)]
        sim.economy.found_shop(toft)
        toft.coin = 123
        path = os.path.join(tempfile.gettempdir(), "rw_economy.json")
        sim.save(path)

        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertIn("toft", sim2.economy.shops)
        self.assertEqual(len(sim2.economy.shops["toft"].stock), 1)
        self.assertEqual(sim2.agents["toft"].coin, 123)
        self.assertIn("shop_toft", sim2.world.locations)   # shop location restored


if __name__ == "__main__":
    unittest.main(verbosity=2)
