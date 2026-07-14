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

    def _on_event(self, evt: dict) -> None:
        # only push interesting events to clients (skip per-tick noise)
        if evt["kind"] in ("dialogue", "death", "reflection"):
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
                                 "x": 32.0, "y": 24.0, "say": "", "role": "Player"}
            await ws.send(json.dumps({"type": "joined", "id": pid}))
        elif mtype == "player_move":
            p = self.players.get(msg.get("id"))
            if p:
                p["x"], p["y"] = float(msg.get("x", p["x"])), float(msg.get("y", p["y"]))
        elif mtype == "player_say":
            p = self.players.get(msg.get("id"))
            if p:
                p["say"] = str(msg.get("text", ""))[:200]
        elif mtype == "admin_kill":
            self.sim.kill(msg.get("id", ""), cause=msg.get("cause", "an unseen hand"))

    async def sim_loop(self) -> None:
        dt = 1.0 / max(1, self.scfg["ticks_per_second"])
        while True:
            self.sim.tick()
            await asyncio.sleep(dt)

    async def event_loop(self) -> None:
        while True:
            evt = await self._event_queue.get()
            await self._broadcast({"type": "event", "event": evt})

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
        async with websockets.serve(self.handler, host, port):
            await asyncio.gather(self.sim_loop(), self.broadcast_loop(), self.event_loop())


def main() -> None:
    cfg = load_config()
    asyncio.run(RealmweaveServer(cfg).run())


if __name__ == "__main__":
    main()
