"""Unit tests for Phase 8 'through their eyes' subjective view.

Run from the backend/ directory:  py tests\test_observe.py
Core acceptance: you can build one agent's subjective world - seeing only what
they could perceive and their inner life - and observe it over the server.
"""
import os
import sys
import json
import asyncio
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig
from realmweave.server import RealmweaveServer


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestSubjectiveView(unittest.TestCase):
    def test_sees_only_the_perceivable(self):
        sim = fresh_sim()
        for a in sim.agents.values():
            a.x, a.y = 800.0, 800.0
        me = sim.agents["toft"]; me.x, me.y = 20.0, 20.0
        near = sim.agents["wren"]; near.x, near.y = 22.0, 20.0
        far = sim.agents["dora"]; far.x, far.y = 800.0, 800.0
        view = sim.subjective_view("toft")
        seen_ids = [s["id"] for s in view["seen"]]
        self.assertIn("wren", seen_ids)
        self.assertNotIn("dora", seen_ids)
        self.assertNotIn("toft", seen_ids)     # never see yourself in the crowd

    def test_mood_and_self_notes_reflect_state(self):
        sim = fresh_sim()
        me = sim.agents["bram"]
        me.social.value = 0.1
        self.assertEqual(sim.subjective_view("bram")["mood"], "lonely")
        me.social.value = 0.6
        me.wanted, me.bounty = 1, 40
        view = sim.subjective_view("bram")
        self.assertEqual(view["mood"], "hunted and wary")
        self.assertTrue(any("wanted" in n.lower() for n in view["self_notes"]))

    def test_view_has_inner_life(self):
        sim = fresh_sim()
        for _ in range(20):
            sim.tick()
        view = sim.subjective_view("toft")
        self.assertIn("goal", view)
        self.assertIn("memories", view)
        self.assertIn("needs", view)

    def test_inner_thought_returns_a_line(self):
        sim = fresh_sim()
        for _ in range(10):
            sim.tick()
        t = sim.inner_thought("toft")
        self.assertIsInstance(t, str)
        self.assertTrue(t)


class TestObserveOverServer(unittest.TestCase):
    def test_observe_and_thought_commands(self):
        cfg = load_config(); cfg["force_stub"] = True

        class FakeWS:
            def __init__(self): self.sent = []
            async def send(self, data): self.sent.append(json.loads(data))

        async def scenario():
            srv = RealmweaveServer(cfg)
            ws = FakeWS()
            await srv._handle_client_message(ws, json.dumps({"type": "observe", "agent_id": "toft"}))
            self.assertEqual(srv._observing.get(ws), "toft")
            self.assertTrue(any(m["type"] == "observing" for m in ws.sent))
            # the broadcast loop would push this subjective view:
            view = srv.sim.subjective_view("toft")
            self.assertEqual(view["agent"]["id"], "toft")
            # on-demand inner thought
            await srv._handle_client_message(ws, json.dumps({"type": "inner_thought", "agent_id": "toft"}))
            self.assertTrue(any(m["type"] == "thought" and m["text"] for m in ws.sent))
            # possess costs favor and can nudge an aim from the inside
            favor_before = srv.sim.divine.favor
            await srv._handle_client_message(ws, json.dumps({"type": "possess", "agent_id": "toft"}))
            self.assertLess(srv.sim.divine.favor, favor_before)
            await srv._handle_client_message(ws, json.dumps({"type": "possess_act", "agent_id": "toft", "goal_kind": "seek_adventure"}))
            self.assertEqual(srv.sim.agents["toft"].goal.kind, "seek_adventure")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main(verbosity=2)
