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


class RealmweaveServer:
    def __init__(self, config: dict):
        self.cfg = config
        self.scfg = config["server"]
        router = LLMRouter(config, ollama=OllamaClient(config["ollama_host"]))
        self.sim = Simulation(router, SimConfig(**config["sim"]))
        self.clients: Set = set()
        self.players: Dict[str, dict] = {}
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
                           "crime", "bounty", "arrest", "escape"):
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
            self.clients.discard(ws)

    async def _handle_client_message(self, ws, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        mtype = msg.get("type")
        if mtype == "player_join":
            pid = f"player:{msg.get('name','wanderer')}"
            self.players[pid] = {"id": pid, "name": msg.get("name", "Wanderer"),
                                 "x": 32.0, "y": 24.0, "say": "", "role": "Player",
                                 "coin": 150, "quest": None}
            await ws.send(json.dumps({"type": "joined", "id": pid}))
        elif mtype == "player_move":
            p = self.players.get(msg.get("id"))
            if p:
                p["x"], p["y"] = float(msg.get("x", p["x"])), float(msg.get("y", p["y"]))
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
            snap = self.sim.snapshot()
            snap["type"] = "snapshot"
            snap["players"] = list(self.players.values())
            await self._broadcast(snap)
            await asyncio.sleep(dt)

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
