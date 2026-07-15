"""Tests for the log-out safe bubble: offline characters are preserved and
protected, and resume where they left off.

Run from the backend/ directory:  py tests\test_offline.py
"""
import os
import sys
import json
import asyncio
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig
from realmweave.server import RealmweaveServer


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send(self, data):
        self.sent.append(json.loads(data))


def make_server():
    cfg = load_config(); cfg["force_stub"] = True
    cfg["server"]["save_path"] = os.path.join(tempfile.gettempdir(), "rw_test_never_saved.json")
    return RealmweaveServer(cfg)


class TestOfflineBubble(unittest.TestCase):
    def test_logout_preserves_and_protects_then_resumes(self):
        async def scenario():
            srv = make_server()
            ws = FakeWS()
            await srv._handle_client_message(ws, json.dumps({"type": "player_join", "name": "Ada"}))
            pid = [m for m in ws.sent if m["type"] == "joined"][0]["id"]
            # earn some coin and move a little
            srv.players[pid]["coin"] = 275
            srv.players[pid]["x"], srv.players[pid]["y"] = 40.0, 12.0

            # log out: character leaves the world into the safe bubble
            srv._drop_client(ws)
            self.assertNotIn(pid, srv.players)              # not in the world...
            self.assertIn("Ada", srv.sim.offline_players)   # ...but safely stored
            # while offline they are not a live entity, so nothing can touch them
            self.assertNotIn("Ada", [p["name"] for p in srv.players.values()])

            # log back in with the same name: state is restored
            ws2 = FakeWS()
            await srv._handle_client_message(ws2, json.dumps({"type": "player_join", "name": "Ada"}))
            joined = [m for m in ws2.sent if m["type"] == "joined"][0]
            self.assertTrue(joined["resumed"])
            self.assertEqual(joined["coin"], 275)
            new_pid = joined["id"]
            self.assertEqual(srv.players[new_pid]["coin"], 275)
            self.assertEqual((srv.players[new_pid]["x"], srv.players[new_pid]["y"]), (40.0, 12.0))
            self.assertNotIn("Ada", srv.sim.offline_players)  # taken out of the bubble
        asyncio.run(scenario())

    def test_offline_bubble_survives_save_load(self):
        cfg = load_config(); cfg["force_stub"] = True
        sim = Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))
        sim.offline_players["Ada"] = {"name": "Ada", "x": 10.0, "y": 20.0, "coin": 300, "quest": None}
        path = os.path.join(tempfile.gettempdir(), "rw_offline.json")
        sim.save(path)
        sim2 = Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))
        self.assertTrue(sim2.load(path))
        self.assertIn("Ada", sim2.offline_players)
        self.assertEqual(sim2.offline_players["Ada"]["coin"], 300)


if __name__ == "__main__":
    unittest.main(verbosity=2)
