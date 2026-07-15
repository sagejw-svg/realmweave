"""Unit tests for Phase 4 quests: interest, taking/ignoring, rewards, players.

Run from the backend/ directory:  py tests\test_quests.py
Core acceptance: an adventurous agent takes a combat quest; a content agent
declines it; a player can accept and complete a cross-domain quest for a reward.
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
from realmweave.quests.quest import QUEST_TEMPLATES


def fresh_sim():
    cfg = load_config()
    cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestInterest(unittest.TestCase):
    def test_adventurous_takes_content_ignores_combat_quest(self):
        sim = fresh_sim()
        # a fresh combat quest
        q = sim.quests.post_template(QUEST_TEMPLATES[0])   # Clear the North Road (Combat/Exploration)
        isla = sim.agents["isla"]   # ambitious, curious, bold
        dora = sim.agents["dora"]   # content, cautious, rooted
        self.assertGreaterEqual(sim.quests.interest(isla, q), 0.6)
        self.assertLess(sim.quests.interest(dora, q), 0.6)

    def test_try_offer_assigns_only_when_interested(self):
        sim = fresh_sim()
        # clear seeded quests, add only a combat quest
        sim.quests.quests.clear()
        sim.quests.post_template(QUEST_TEMPLATES[0])
        dora = sim.agents["dora"]
        self.assertIsNone(sim.quests.try_offer(dora), "content agent should ignore it")
        isla = sim.agents["isla"]
        goal = sim.quests.try_offer(isla)
        self.assertIsNotNone(goal, "adventurous agent should take it")
        self.assertEqual(goal.kind, "quest")
        self.assertTrue(goal.quest_id)


class TestRewards(unittest.TestCase):
    def test_completing_a_quest_grants_coin_and_skill(self):
        sim = fresh_sim()
        toft = sim.agents["toft"]
        q = sim.quests.post_template(QUEST_TEMPLATES[0])
        before_coin = toft.coin
        before_skill = toft.sheet.skill(q.reward_skill)
        sim.quests.complete(toft, q.id)
        self.assertEqual(toft.coin, before_coin + q.reward_coin)
        self.assertEqual(toft.sheet.skill(q.reward_skill), before_skill + q.reward_amount)
        self.assertEqual(sim.quests.get(q.id).status, "completed")


class TestEmergentQuests(unittest.TestCase):
    def test_agents_take_and_complete_quests_over_time(self):
        sim = fresh_sim()
        accepted, completed = [], []
        sim.subscribe(lambda e: accepted.append(e) if e["kind"] == "quest_accepted" else None)
        sim.subscribe(lambda e: completed.append(e) if e["kind"] == "quest_completed" else None)
        for _ in range(1200):
            sim.tick()
        self.assertGreaterEqual(len(accepted), 1, "some agent should take a quest")
        self.assertGreaterEqual(len(completed), 1, "some agent should finish one")


class TestPlayerQuest(unittest.TestCase):
    def test_player_accepts_and_completes_for_reward(self):
        cfg = load_config()
        cfg["force_stub"] = True
        cfg["server"]["save_path"] = os.path.join(tempfile.gettempdir(), "rw_test_never_saved.json")

        class FakeWS:
            def __init__(self):
                self.sent = []

            async def send(self, data):
                self.sent.append(json.loads(data))

        async def scenario():
            srv = RealmweaveServer(cfg)
            ws = FakeWS()
            await srv._handle_client_message(ws, json.dumps({"type": "player_join", "name": "Hero"}))
            pid = [m for m in ws.sent if m["type"] == "joined"][0]["id"]
            # take the seeded North Road quest (q1)
            q = srv.sim.quests.get("q1")
            await srv._handle_client_message(ws, json.dumps(
                {"type": "player_accept_quest", "id": pid, "quest_id": q.id}))
            self.assertTrue(any(m.get("event") == "accepted" for m in ws.sent))
            start_coin = srv.players[pid]["coin"]
            # walk to each objective in small steps (server authority forbids teleporting)
            for obj in q.objectives:
                loc = srv.sim.world.locations[obj.location]
                for _ in range(300):
                    p = srv.players[pid]
                    dx, dy = loc.x - p["x"], loc.y - p["y"]
                    if abs(dx) + abs(dy) < 1.0:
                        break
                    mx = max(-3.0, min(3.0, dx))
                    my = max(-2.0, min(2.0, dy))
                    await srv._handle_client_message(ws, json.dumps(
                        {"type": "player_move", "id": pid, "x": p["x"] + mx, "y": p["y"] + my}))
                # 'wait' objectives accumulate while standing at the spot
                reps = obj.target if obj.kind == "wait" else 1
                for _ in range(reps):
                    p = srv.players[pid]
                    await srv._handle_client_message(ws, json.dumps(
                        {"type": "player_move", "id": pid, "x": p["x"], "y": p["y"]}))
            done = [m for m in ws.sent if m.get("event") == "completed"]
            self.assertTrue(done, "player should complete the quest")
            self.assertEqual(srv.players[pid]["coin"], start_coin + q.reward_coin)
            self.assertEqual(srv.sim.quests.get(q.id).status, "completed")

        asyncio.run(scenario())


class TestQuestPersistence(unittest.TestCase):
    def test_quest_board_survives_save_load(self):
        sim = fresh_sim()
        q = sim.quests.post_template(QUEST_TEMPLATES[1])
        q.status = "active"
        q.taker_id = "toft"
        path = os.path.join(tempfile.gettempdir(), "rw_quests.json")
        sim.save(path)
        sim2 = fresh_sim()
        self.assertTrue(sim2.load(path))
        self.assertIn(q.id, sim2.quests.quests)
        self.assertEqual(sim2.quests.get(q.id).status, "active")
        self.assertEqual(sim2.quests.get(q.id).taker_id, "toft")


if __name__ == "__main__":
    unittest.main(verbosity=2)
