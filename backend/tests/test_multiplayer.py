"""Unit tests for Phase 10 multiplayer: roster, interest management, authority.

Run from the backend/ directory:  py tests\test_multiplayer.py
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


class TestRoster(unittest.TestCase):
    def test_join_assigns_unique_ids_and_leaves_cleanly(self):
        async def scenario():
            srv = make_server()
            joins = []
            srv.sim.subscribe(lambda e: joins.append(e) if e["kind"] in ("player_join", "player_leave") else None)
            ws1, ws2 = FakeWS(), FakeWS()
            await srv._handle_client_message(ws1, json.dumps({"type": "player_join", "name": "Ada"}))
            await srv._handle_client_message(ws2, json.dumps({"type": "player_join", "name": "Ada"}))
            ids = [m["id"] for w in (ws1, ws2) for m in w.sent if m["type"] == "joined"]
            self.assertEqual(len(set(ids)), 2, "same name -> distinct player ids")
            self.assertEqual(len(srv.players), 2)
            # leaving removes the player and emits a leave
            srv._drop_client(ws1)
            self.assertEqual(len(srv.players), 1)
            self.assertTrue(any(e["kind"] == "player_leave" for e in joins))
        asyncio.run(scenario())

    def test_server_full_is_rejected(self):
        async def scenario():
            srv = make_server(); srv.max_players = 2
            for i in range(2):
                await srv._handle_client_message(FakeWS(), json.dumps({"type": "player_join", "name": f"P{i}"}))
            ws = FakeWS()
            await srv._handle_client_message(ws, json.dumps({"type": "player_join", "name": "late"}))
            self.assertTrue(any(m["type"] == "join_denied" for m in ws.sent))
            self.assertEqual(len(srv.players), 2)
        asyncio.run(scenario())


class TestAuthority(unittest.TestCase):
    def test_move_is_own_only_and_anti_teleport(self):
        async def scenario():
            srv = make_server()
            ws1, ws2 = FakeWS(), FakeWS()
            await srv._handle_client_message(ws1, json.dumps({"type": "player_join", "name": "Ada"}))
            pid = [m for m in ws1.sent if m["type"] == "joined"][0]["id"]
            start = (srv.players[pid]["x"], srv.players[pid]["y"])
            # a teleport is rejected (kept at start)
            await srv._handle_client_message(ws1, json.dumps({"type": "player_move", "id": pid, "x": 300, "y": 300}))
            self.assertEqual((srv.players[pid]["x"], srv.players[pid]["y"]), start)
            # a small step is accepted
            await srv._handle_client_message(ws1, json.dumps({"type": "player_move", "id": pid, "x": start[0] + 2, "y": start[1]}))
            self.assertAlmostEqual(srv.players[pid]["x"], start[0] + 2)
            # another connection cannot move someone else's character
            await srv._handle_client_message(ws2, json.dumps({"type": "player_move", "id": pid, "x": start[0] + 5, "y": start[1]}))
            self.assertAlmostEqual(srv.players[pid]["x"], start[0] + 2)
        asyncio.run(scenario())


class TestInterestManagement(unittest.TestCase):
    def test_client_gets_only_nearby_agents_plus_observed(self):
        async def scenario():
            srv = make_server()
            srv.interest_radius = 8.0
            ws = FakeWS()
            await srv._handle_client_message(ws, json.dumps({"type": "player_join", "name": "Ada"}))
            pid = [m for m in ws.sent if m["type"] == "joined"][0]["id"]
            srv.players[pid]["x"], srv.players[pid]["y"] = 20.0, 20.0
            # place one agent near, the rest far
            for a in srv.sim.agents.values():
                a.x, a.y = 900.0, 900.0
            srv.sim.agents["toft"].x, srv.sim.agents["toft"].y = 22.0, 20.0
            base = srv.sim.snapshot(); base["type"] = "snapshot"; base["players"] = list(srv.players.values())
            view = srv._client_snapshot(ws, base)
            ids = {a["id"] for a in view["agents"]}
            self.assertIn("toft", ids)
            self.assertLess(len(ids), len(base["agents"]), "far agents filtered out")
            # an observed far agent is still included
            srv._observing[ws] = "dora"
            view2 = srv._client_snapshot(ws, base)
            self.assertIn("dora", {a["id"] for a in view2["agents"]})

        asyncio.run(scenario())

    def test_spectator_gets_full_world(self):
        srv = make_server()
        ws = FakeWS()   # never joined -> spectator (e.g. a dashboard)
        base = srv.sim.snapshot(); base["type"] = "snapshot"; base["players"] = []
        view = srv._client_snapshot(ws, base)
        self.assertEqual(len(view["agents"]), len(base["agents"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
