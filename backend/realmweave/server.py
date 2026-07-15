"""Async WebSocket server that runs the sim and streams it to clients.

Protocol (JSON, newline-free frames):

  server -> client
    {"type":"hello", "world":{...}, "config":{...}}        once on connect
    {"type":"snapshot", "clock":{...}, "agents":[...], "tick":N}
    {"type":"event", "event":{...}}                        dialogue/death/etc.

  client -> server
    {"type":"player_join", "name":"..."}
    {"type":"player_move", "id":"...", "x":.., "y":..}
    {"type":"player_say", "id":"...", "text":"..."}
    {"type":"admin_kill", "id":"agent_id", "cause":"..."}   (dev only)

The sim advances on a fixed real-time cadence (ticks_per_second) and snapshots
are broadcast at broadcast_hz. This same server is the seam for multiplayer:
multiple client connections already share one authoritative world; players are
added to a roster the sim can render alongside NPCs.
"""
from __future__ import annotations
import asyncio
import json
import os
from typing import Dict, Set

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None

from .config import load_config
from .llm.router import LLMRouter
from .llm.ollama_client import OllamaClient
from .sim import Simulation, SimConfig


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class RealmweaveServer:
    def __init__(self, config: dict):
        self.cfg = config
        self.scfg = config["server"]
        router = LLMRouter(config, ollama=OllamaClient(config["ollama_host"]))
        self.sim = Simulation(router, SimConfig(**config["sim"]))
        self.clients: Set = set()
        self.players: Dict[str, dict] = {}
        self._observing: Dict[object, str] = {}    # ws -> agent id being watched
        self._ws_player: Dict[object, str] = {}    # ws -> player id (their character)
        self._player_counter = 0
        self.interest_radius = float(self.scfg.get("interest_radius", 24.0))
        self.max_players = int(self.scfg.get("max_players", 16))
        self._event_queue: "asyncio.Queue[dict]" = asyncio.Queue()
        self.sim.subscribe(self._on_event)

        # resolve save path relative to the backend/ dir and resume if present
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.save_path = os.path.join(base, self.scfg.get("save_path", "data/world_save.json"))
        self.autosave_seconds = int(self.scfg.get("autosave_seconds", 60))
        if self.sim.load(self.save_path):
            print(f"Resumed world from {self.save_path} at {self.sim.clock.stamp()}")
        else:
            print("Starting a fresh world (no save found).")

    def _on_event(self, evt: dict) -> None:
        # only push interesting events to clients (skip per-tick noise)
        if evt["kind"] in ("dialogue", "death", "reflection", "shop_founded",
                           "trade", "quest_posted", "quest_accepted", "quest_completed",
                           "divine_suggestion", "divine_authored", "rumor",
                           "crime", "bounty", "arrest", "escape",
                           "player_join", "player_leave"):
            try:
                self._event_queue.put_nowait(evt)
            except asyncio.QueueFull:
                pass

    async def _broadcast(self, message: dict) -> None:
        if not self.clients:
            return
        data = json.dumps(message)
        await asyncio.gather(*[self._safe_send(c, data) for c in list(self.clients)],
                             return_exceptions=True)

    async def _safe_send(self, ws, data: str) -> None:
        try:
            await ws.send(data)
        except Exception:
            self.clients.discard(ws)

    async def handler(self, ws) -> None:
        self.clients.add(ws)
        await ws.send(json.dumps({
            "type": "hello",
            "world": self.sim.world.to_dict(),
            "config": {"minutes_per_tick": self.sim.cfg.minutes_per_tick},
        }))
        try:
            async for raw in ws:
                await self._handle_client_message(ws, raw)
        except Exception:
            pass
        finally:
            self._drop_client(ws)

    def _drop_client(self, ws) -> None:
        self.clients.discard(ws)
        self._observing.pop(ws, None)
        pid = self._ws_player.pop(ws, None)
        if pid and pid in self.players:
            name = self.players[pid]["name"]
            del self.players[pid]
            self.sim.emit("player_leave", player=pid, name=name)

    async def _handle_client_message(self, ws, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        mtype = msg.get("type")
        if mtype == "player_join":
            if len([p for p in self.players]) >= self.max_players:
                await ws.send(json.dumps({"type": "join_denied", "reason": "server full"}))
                return
            self._player_counter += 1
            name = str(msg.get("name", "Wanderer"))[:24] or "Wanderer"
            pid = f"player:{self._player_counter}:{name}"
            self.players[pid] = {"id": pid, "name": name, "x": 32.0, "y": 24.0, "say": "",
                                 "role": "Player", "coin": 150, "quest": None}
            self._ws_player[ws] = pid
            self.sim.emit("player_join", player=pid, name=name)
            await ws.send(json.dumps({"type": "joined", "id": pid}))
        elif mtype == "player_move":
            p = self.players.get(msg.get("id"))
            # authority: a client may only move its own character, and only a
            # sane distance per update (no teleporting), clamped to the world
            if p and self._ws_player.get(ws) == p["id"]:
                nx = _clamp(float(msg.get("x", p["x"])), 0.0, 64.0)
                ny = _clamp(float(msg.get("y", p["y"])), 0.0, 52.0)
                if abs(nx - p["x"]) + abs(ny - p["y"]) <= 6.0:   # max step per update
                    p["x"], p["y"] = nx, ny
                await self._progress_player_quest(ws, p)
        elif mtype == "player_accept_quest":
            p = self.players.get(msg.get("id"))
            await self._accept_player_quest(ws, p, msg.get("quest_id", ""))
        elif mtype == "player_say":
            p = self.players.get(msg.get("id"))
            if p:
                text = str(msg.get("text", ""))[:200]
                # "/suggest <text>" whispers a divine suggestion to the nearest NPC
                if text.lower().startswith("/suggest "):
                    await self._divine_suggest_nearest(ws, p, text[9:].strip())
                    return
                p["say"] = text
                reply = self.sim.player_speak(p["name"], p["x"], p["y"], p["say"])
                if reply:
                    await ws.send(json.dumps({"type": "npc_reply", **reply}))
                else:
                    await ws.send(json.dumps({"type": "npc_reply", "agent_name": "",
                                              "text": "(No one is close enough to hear you.)"}))
        elif mtype == "divine_suggest":
            res = self.sim.divine.suggest(msg.get("agent_id", ""), str(msg.get("text", "")),
                                          goal_kind=msg.get("goal_kind", ""))
            await ws.send(json.dumps({"type": "divine_result", **(res or {"error": "no such agent"})}))
        elif mtype == "divine_author":
            res = self.sim.divine.author(msg.get("agent_id", ""), name=msg.get("name", ""),
                                         background=msg.get("background", ""),
                                         personality=msg.get("personality") or None)
            await ws.send(json.dumps({"type": "divine_authored", **(res or {"error": "no such agent"})}))
        elif mtype == "admin_kill":
            self.sim.kill(msg.get("id", ""), cause=msg.get("cause", "an unseen hand"))
        elif mtype == "commit_crime":
            res = self.sim.justice.commit_crime(msg.get("perp", ""), msg.get("kind", "theft"),
                                                victim_id=msg.get("victim", ""))
            await ws.send(json.dumps({"type": "crime_result", **res}))
        elif mtype == "observe":
            aid = msg.get("agent_id", "")
            self._observing[ws] = aid
            await ws.send(json.dumps({"type": "observing", "agent_id": aid}))
        elif mtype == "stop_observe":
            self._observing.pop(ws, None)
        elif mtype == "inner_thought":
            t = self.sim.inner_thought(msg.get("agent_id", ""))
            await ws.send(json.dumps({"type": "thought", "agent_id": msg.get("agent_id", ""),
                                      "text": t or "..."}))
        elif mtype == "possess":
            aid = msg.get("agent_id", "")
            a = self.sim.agents.get(aid)
            cost = 2.0
            if a is None or not a.alive:
                await ws.send(json.dumps({"type": "possess_result", "ok": False, "reason": "no such soul"}))
            elif self.sim.divine.favor < cost:
                await ws.send(json.dumps({"type": "possess_result", "ok": False, "reason": "not enough favor"}))
            else:
                self.sim.divine.favor -= cost
                a._possessed = True
                self.sim.emit("possess", agent=aid, agent_name=a.name)
                await ws.send(json.dumps({"type": "possess_result", "ok": True, "agent_id": aid,
                                          "favor": round(self.sim.divine.favor, 1)}))
        elif mtype == "possess_act":
            a = self.sim.agents.get(msg.get("agent_id", ""))
            if a is not None and getattr(a, "_possessed", False):
                from .cognition.planner import build_plan, goal_description
                from .cognition.goals import Goal
                gk = msg.get("goal_kind", "explore")
                a.goal = Goal(kind=gk, description=goal_description(gk), priority=1.0,
                              steps=build_plan(gk, a), created_at=self.sim.clock.minutes)
                await ws.send(json.dumps({"type": "possess_result", "ok": True, "acted": gk}))
        elif mtype == "release":
            a = self.sim.agents.get(msg.get("agent_id", ""))
            if a is not None:
                a._possessed = False
                await ws.send(json.dumps({"type": "possess_result", "ok": True, "released": True}))

    # ---- divine influence ---------------------------------------------
    async def _divine_suggest_nearest(self, ws, player, text: str) -> None:
        import math
        target, best = None, 8.0
        for a in self.sim.living():
            d = math.hypot(a.x - player["x"], a.y - player["y"])
            if d <= best:
                best, target = d, a
        if target is None:
            await ws.send(json.dumps({"type": "divine_result",
                                      "reaction": "(No one is near enough to hear the divine whisper.)"}))
            return
        low = text.lower()
        goal_kind = "seek_adventure" if any(w in low for w in
                    ("bigger", "greater", "adventure", "explore", "more", "beyond")) else ""
        res = self.sim.divine.suggest(target.id, text, goal_kind=goal_kind)
        await ws.send(json.dumps({"type": "divine_result", **(res or {})}))

    # ---- player quests -------------------------------------------------
    async def _accept_player_quest(self, ws, player, quest_id: str) -> None:
        if not player:
            return
        q = self.sim.quests.get(quest_id)
        if q is None or q.status != "open":
            await ws.send(json.dumps({"type": "quest_update", "event": "unavailable"}))
            return
        q.status = "active"
        q.taker_id = player["id"]
        player["quest"] = {"id": q.id, "title": q.title,
                           "objectives": [o.to_dict() for o in q.fresh_objectives()], "index": 0}
        self.sim.emit("quest_accepted", quest=q.id, title=q.title,
                      agent=player["id"], agent_name=player["name"])
        await ws.send(json.dumps({"type": "quest_update", "event": "accepted",
                                  "id": q.id, "title": q.title,
                                  "objective": player["quest"]["objectives"][0]["name"]}))

    async def _progress_player_quest(self, ws, player) -> None:
        pq = player.get("quest")
        if not pq:
            return
        objs = pq["objectives"]
        i = pq["index"]
        if i >= len(objs):
            return
        obj = objs[i]
        loc = self.sim.world.locations.get(obj["location"])
        if loc is None:
            return
        near = abs(loc.x - player["x"]) <= 2.5 and abs(loc.y - player["y"]) <= 2.5
        if not near:
            return
        obj["progress"] = obj["target"] if obj["kind"] == "visit" else obj["progress"] + 1
        if obj["progress"] >= obj["target"]:
            pq["index"] += 1
            if pq["index"] >= len(objs):
                await self._complete_player_quest(ws, player)
            else:
                await ws.send(json.dumps({"type": "quest_update", "event": "objective",
                                          "objective": objs[pq["index"]]["name"]}))

    async def _complete_player_quest(self, ws, player) -> None:
        pq = player.get("quest")
        q = self.sim.quests.get(pq["id"]) if pq else None
        if q is None:
            return
        q.status = "completed"
        player["coin"] = player.get("coin", 0) + q.reward_coin
        player["quest"] = None
        self.sim.emit("quest_completed", quest=q.id, title=q.title, taker=player["id"],
                      taker_name=player["name"], reward_coin=q.reward_coin, reward_skill=q.reward_skill)
        await ws.send(json.dumps({"type": "quest_update", "event": "completed",
                                  "title": q.title, "reward_coin": q.reward_coin,
                                  "coin": player["coin"]}))

    async def sim_loop(self) -> None:
        dt = 1.0 / max(1, self.scfg["ticks_per_second"])
        while True:
            self.sim.tick()
            await asyncio.sleep(dt)

    async def event_loop(self) -> None:
        while True:
            evt = await self._event_queue.get()
            await self._broadcast({"type": "event", "event": evt})

    async def autosave_loop(self) -> None:
        while True:
            await asyncio.sleep(self.autosave_seconds)
            try:
                self.sim.save(self.save_path)
                print(f"[autosave] {self.sim.clock.stamp()} -> {self.save_path}")
            except Exception as e:
                print(f"[autosave] failed: {e}")

    async def broadcast_loop(self) -> None:
        dt = 1.0 / max(1, self.scfg["broadcast_hz"])
        while True:
            base = self.sim.snapshot()
            base["type"] = "snapshot"
            base["players"] = list(self.players.values())
            for ws in list(self.clients):
                await self._safe_send(ws, json.dumps(self._client_snapshot(ws, base)))
            # send each observer the subjective view of the agent they're watching
            for ws, aid in list(self._observing.items()):
                view = self.sim.subjective_view(aid)
                if view is not None:
                    await self._safe_send(ws, json.dumps(view))
            await asyncio.sleep(dt)

    def _client_snapshot(self, ws, base: dict) -> dict:
        """Interest management: a client controlling a character receives only the
        agents near it (plus any it is observing), which bounds bandwidth as the
        world and player count grow. Spectator clients (dashboards, no character)
        get the full world."""
        pid = self._ws_player.get(ws)
        if pid is None or pid not in self.players:
            return base
        p = self.players[pid]
        r = self.interest_radius
        watch = self._observing.get(ws, "")
        near = [a for a in base["agents"]
                if abs(a["x"] - p["x"]) <= r and abs(a["y"] - p["y"]) <= r]
        near_ids = {a["id"] for a in near}
        if watch and watch not in near_ids:
            extra = next((a for a in base["agents"] if a["id"] == watch), None)
            if extra:
                near.append(extra)
        view = dict(base)
        view["agents"] = near
        view["interest_radius"] = r
        return view

    async def run(self) -> None:
        if websockets is None:
            raise RuntimeError("The 'websockets' package is required: pip install websockets")
        host, port = self.scfg["host"], self.scfg["port"]
        print(f"Realmweave server listening on ws://{host}:{port}")
        try:
            async with websockets.serve(self.handler, host, port):
                await asyncio.gather(self.sim_loop(), self.broadcast_loop(),
                                     self.event_loop(), self.autosave_loop())
        finally:
            # persist the world on shutdown (Ctrl+C) so nothing is lost
            try:
                self.sim.save(self.save_path)
                print(f"\nSaved world to {self.save_path} on shutdown.")
            except Exception as e:
                print(f"Save on shutdown failed: {e}")


def main() -> None:
    cfg = load_config()
    asyncio.run(RealmweaveServer(cfg).run())


if __name__ == "__main__":
    main()
