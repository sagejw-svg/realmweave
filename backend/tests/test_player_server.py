"""Server-authority tests for the player economy verbs.

Run from the backend/ directory:  py tests\test_player_server.py

The sim-level buy/give are covered in test_player_trade; here we exercise the
server wrappers that make them authoritative: the server owns the player's coin
and only debits it on a confirmed sale, and refuses a gift larger than the
player actually holds.
"""
import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.server import RealmweaveServer
from realmweave.economy.goods import make_item


class FakeWS:
    """Minimal stand-in for a websocket: records everything sent to it."""
    def __init__(self):
        self.sent = []

    async def send(self, data):
        self.sent.append(data)


def fresh_server():
    cfg = load_config()
    cfg["force_stub"] = True
    # point the save at a nonexistent temp path so no world is auto-loaded
    cfg["server"]["save_path"] = os.path.join(tempfile.gettempdir(), "rw_no_such_save.json")
    return RealmweaveServer(cfg)


def register_player(server, ws, coin, x, y):
    pid = "player:1:Trav"
    server.players[pid] = {"id": pid, "name": "Trav", "x": x, "y": y,
                           "say": "", "role": "Player", "coin": coin, "quest": None}
    server._ws_player[ws] = pid
    return pid


class TestPlayerBuyAuthority(unittest.TestCase):
    def test_buy_debits_only_the_players_own_coin(self):
        server = fresh_server()
        toft = server.sim.agents["toft"]
        toft.inventory = [make_item("Smithing", 40)]
        shop = server.sim.economy.found_shop(toft)
        toft.coin = 0
        ws = FakeWS()
        register_player(server, ws, coin=1000, x=shop.x, y=shop.y)

        asyncio.run(server._handle_client_message(
            ws, '{"type":"player_buy","id":"player:1:Trav"}'))

        self.assertTrue(any("buy_result" in m and '"ok": true' in m for m in ws.sent))
        self.assertLess(server.players["player:1:Trav"]["coin"], 1000)  # player paid
        self.assertGreater(toft.coin, 0)                                # owner was paid
        self.assertEqual(len(shop.stock), 0)                            # item left the shelf


class TestPlayerGiveAuthority(unittest.TestCase):
    def test_gift_larger_than_balance_is_refused(self):
        server = fresh_server()
        elda = server.sim.agents["elda"]
        coin_before = elda.coin
        ws = FakeWS()
        register_player(server, ws, coin=10, x=elda.x, y=elda.y)

        asyncio.run(server._handle_client_message(
            ws, '{"type":"player_give","id":"player:1:Trav","amount":9999}'))

        self.assertTrue(any("not enough coin" in m for m in ws.sent))
        self.assertEqual(elda.coin, coin_before)     # nothing was given

    def test_valid_gift_moves_coin_and_is_remembered(self):
        server = fresh_server()
        elda = server.sim.agents["elda"]
        coin_before = elda.coin
        ws = FakeWS()
        register_player(server, ws, coin=100, x=elda.x, y=elda.y)

        asyncio.run(server._handle_client_message(
            ws, '{"type":"player_give","id":"player:1:Trav","amount":40}'))

        self.assertEqual(elda.coin, coin_before + 40)
        self.assertEqual(server.players["player:1:Trav"]["coin"], 60)
        self.assertGreater(elda.affinity("player:Trav"), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
