#!/usr/bin/env python3
"""Run Realmweave headless: no graphics, just the living world in your terminal.

    python run_headless.py --ticks 200 --stub

Prints an hourly digest of what each NPC is doing plus any dialogue and deaths.
Use --stub to force the GPU-free deterministic LLM (great for a first run or CI).
This is the fastest way to feel the world breathe before wiring up Godot.
"""
from __future__ import annotations
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.llm.ollama_client import OllamaClient
from realmweave.sim import Simulation, SimConfig


def main() -> None:
    ap = argparse.ArgumentParser(description="Realmweave headless world runner")
    ap.add_argument("--ticks", type=int, default=144, help="number of sim ticks to run")
    ap.add_argument("--stub", action="store_true", help="force the GPU-free stub LLM")
    ap.add_argument("--digest-hours", type=int, default=2, help="hours between world digests")
    ap.add_argument("--kill", type=str, default="", help="agent id to kill at tick 40 (drama test)")
    args = ap.parse_args()

    cfg = load_config()
    if args.stub:
        cfg["force_stub"] = True

    router = LLMRouter(cfg, ollama=OllamaClient(cfg["ollama_host"]))
    sim = Simulation(router, SimConfig(**cfg["sim"]))

    backend = "stub (GPU-free)" if cfg.get("force_stub") or not router._ollama_available() else "Ollama"
    print(f"== Realmweave :: {sim.world.name} ==  LLM backend: {backend}")
    print(f"Cast: {', '.join(a.name + ' (' + a.role + ')' for a in sim.agents.values())}\n")

    dialogues = []
    sim.subscribe(lambda e: dialogues.append(e) if e["kind"] == "dialogue" else None)
    sim.subscribe(lambda e: print(f"  ** DEATH ** {e['name']} — {e['cause']} ({e['stamp']})")
                  if e["kind"] == "death" else None)

    last_digest_hour = -999
    for i in range(args.ticks):
        if args.kill and i == 40:
            sim.kill(args.kill, cause="a sudden fever")
        sim.tick()
        cur_h = sim.clock.day_index * 24 + sim.clock.hour
        if cur_h - last_digest_hour >= args.digest_hours:
            last_digest_hour = cur_h
            print(f"\n--- {sim.clock.stamp()} | weather: {sim.world.weather} ---")
            for a in sim.agents.values():
                status = "DEAD" if not a.alive else a.activity
                where = sim.world.loc(a.current_location).name
                extra = f'  "{a.say}"' if (a.say and a.say_ttl > 0) else ""
                print(f"  {a.name:<14} {status:<10} @ {where}{extra}")
            while dialogues:
                d = dialogues.pop(0)
                print(f"    · {d['speaker_name']} -> {d['listener_name']}: \"{d['text']}\"  "
                      f"[{d['tier']}/{d['backend']}]")

    print(f"\nSimulated {args.ticks} ticks -> {sim.clock.stamp()}.")
    # tiny memory peek
    sample = next(iter(sim.agents.values()))
    print(f"\n{sample.name}'s top memories right now:")
    for m in sample.memory.retrieve("today", sim.clock.minutes, k=4):
        print(f"  [{m.importance:.0f}] {m.text}")


if __name__ == "__main__":
    main()
