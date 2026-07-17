"""Unit tests for Slice A: the audited money path, ledger, and daily finance.

Run from the backend/ directory:  py tests\test_finance.py

Covers: every coin move goes through transfer() and lands in the ledger; the
daily cycle pays wages, collects rent, and guarantees a relief floor so no agent
is left destitute; the coffer never silently overdraws; and finance + ledger
survive save/load while pre-v10 saves migrate to safe defaults.
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
from realmweave.economy.goods import make_item
from realmweave.economy.finance import DAILY_WAGE, DAILY_RENT, RELIEF_FLOOR, STARTING_TREASURY


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


def force_next_day(sim):
    """Jump the clock to the next day boundary and run the daily finance cycle."""
    sim.clock.minutes = (sim.clock.day_index + 1) * 1440
    sim.finance.step()


def worker(sim):
    """An agent that has a workplace (so it earns a wage)."""
    for a in sim.living():
        if a.workplace:
            return a
    raise AssertionError("no agent has a workplace")


class TestTransfer(unittest.TestCase):
    def test_transfer_moves_coin_and_logs(self):
        sim = fresh_sim()
        a, b = sim.agents["toft"], sim.agents["isla"]
        a.coin, b.coin = 100, 0
        moved = sim.economy.transfer(a, b, 30, "test", note="hi")
        self.assertEqual(moved, 30)
        self.assertEqual(a.coin, 70)
        self.assertEqual(b.coin, 30)
        last = sim.economy.ledger.tail(1)[0]
        self.assertEqual(last["kind"], "test")
        self.assertEqual(last["src"], a.id)
        self.assertEqual(last["dst"], b.id)
        self.assertEqual(last["amount"], 30)

    def test_transfer_is_forgiving_by_default(self):
        sim = fresh_sim()
        a, b = sim.agents["toft"], sim.agents["isla"]
        a.coin, b.coin = 10, 0
        moved = sim.economy.transfer(a, b, 50, "test")   # allow_partial default
        self.assertEqual(moved, 10)                      # capped to what a holds
        self.assertEqual(a.coin, 0)
        self.assertEqual(b.coin, 10)

    def test_zero_or_negative_is_a_noop(self):
        sim = fresh_sim()
        a, b = sim.agents["toft"], sim.agents["isla"]
        before = len(sim.economy.ledger.entries)
        self.assertEqual(sim.economy.transfer(a, b, 0, "test"), 0)
        self.assertEqual(sim.economy.transfer(a, b, -5, "test"), 0)
        self.assertEqual(len(sim.economy.ledger.entries), before)


class TestExistingFlowsUseLedger(unittest.TestCase):
    def test_theft_conserves_coin_and_is_logged(self):
        sim = fresh_sim()
        perp, victim = sim.agents["toft"], sim.agents["isla"]
        perp.coin, victim.coin = 0, 100
        res = sim.justice.commit_crime(perp.id, "theft", victim.id)
        stolen = res["stolen"]
        self.assertGreater(stolen, 0)
        self.assertEqual(victim.coin, 100 - stolen)
        self.assertEqual(perp.coin, stolen)
        self.assertTrue(any(e["kind"] == "theft" for e in sim.economy.ledger.entries))

    def test_buy_records_a_trade_entry(self):
        sim = fresh_sim()
        toft, isla = sim.agents["toft"], sim.agents["isla"]
        toft.inventory = [make_item("Smithing", 50)]
        shop = sim.economy.found_shop(toft)
        item = shop.stock[0]
        toft.coin, isla.coin = 0, 500
        price = sim.economy.buy(isla, shop, item)
        self.assertEqual(toft.coin, price)
        self.assertEqual(isla.coin, 500 - price)
        self.assertTrue(any(e["kind"] == "trade" for e in sim.economy.ledger.entries))


class TestDailyFinance(unittest.TestCase):
    def test_wage_paid_to_workers(self):
        sim = fresh_sim()
        a = worker(sim)
        a.coin = 100                       # comfortably above the relief floor
        force_next_day(sim)
        self.assertEqual(a.coin, 100 + DAILY_WAGE)
        self.assertTrue(any(e["kind"] == "wage" and e["dst"] == a.id
                            for e in sim.economy.ledger.entries))

    def test_relief_floor_catches_the_destitute(self):
        sim = fresh_sim()
        a = sim.agents["isla"]
        a.coin = 0
        force_next_day(sim)
        self.assertGreaterEqual(a.coin, RELIEF_FLOOR)
        self.assertEqual(a.coin, RELIEF_FLOOR)   # topped exactly to the floor

    def test_rent_collected_from_shop_owner(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]
        toft.inventory = [make_item("Smithing", 60)]
        sim.economy.found_shop(toft)
        toft.coin = 200
        treasury_before = sim.finance.treasury
        force_next_day(sim)
        # owner pays rent (and earns a wage): net change is wage - rent
        self.assertEqual(toft.coin, 200 + DAILY_WAGE - DAILY_RENT)
        self.assertTrue(any(e["kind"] == "rent" and e["src"] == toft.id
                            for e in sim.economy.ledger.entries))
        self.assertGreaterEqual(sim.finance.treasury, treasury_before - 10_000)  # sane

    def test_coffer_never_silently_overdraws(self):
        sim = fresh_sim()
        sim.finance.treasury = 0            # empty coffer
        for a in sim.living():
            a.coin = 0                      # everyone destitute: max relief demand
        force_next_day(sim)
        self.assertGreaterEqual(sim.finance.treasury, 0)
        for a in sim.living():
            self.assertGreaterEqual(a.coin, RELIEF_FLOOR)
        # the shortfall was covered by a world subsidy, logged as such
        self.assertTrue(any(e["kind"] == "subsidy" for e in sim.economy.ledger.entries))

    def test_daily_cycle_runs_once_per_day(self):
        sim = fresh_sim()
        events = []
        sim.subscribe(lambda e: events.append(e) if e["kind"] == "economy_day" else None)
        force_next_day(sim)
        sim.finance.step()                  # same day again: must not re-run
        self.assertEqual(len(events), 1)


class TestFinancePersistence(unittest.TestCase):
    def test_finance_and_ledger_survive_save_load(self):
        sim = fresh_sim()
        force_next_day(sim)                 # populate ledger + move the coffer
        treasury = sim.finance.treasury
        last_day = sim.finance.last_day
        n_entries = len(sim.economy.ledger.entries)
        path = os.path.join(tempfile.gettempdir(), "rw_finance.json")
        sim.save(path)

        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertEqual(sim2.finance.treasury, treasury)
        self.assertEqual(sim2.finance.last_day, last_day)
        self.assertEqual(len(sim2.economy.ledger.entries), n_entries)

    def test_pre_v10_save_migrates_to_defaults(self):
        sim = fresh_sim()
        path = os.path.join(tempfile.gettempdir(), "rw_finance_v9.json")
        sim.save(path)
        # simulate an old save: strip the v10 keys and roll the version back
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.pop("finance", None)
        data.pop("ledger", None)
        data["version"] = 9
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertEqual(sim2.finance.treasury, STARTING_TREASURY)
        self.assertEqual(sim2.economy.ledger.entries, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
