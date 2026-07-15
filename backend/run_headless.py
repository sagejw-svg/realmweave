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
    ap.add_argument("--load", type=str, default="", help="load a saved world before running")
    ap.add_argument("--save", type=str, default="", help="save the world to this path when done")
    ap.add_argument("--say", type=str, default="", help="a traveler says this to the nearest NPC at tick 20")
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
    crafts = []
    steps = []
    sim.subscribe(lambda e: dialogues.append(e) if e["kind"] == "dialogue" else None)
    sim.subscribe(lambda e: crafts.append(e) if e["kind"] == "craft" else None)
    sim.subscribe(lambda e: steps.append(e) if e["kind"] == "goal_step" else None)
    sim.subscribe(lambda e: print(f"  ** DEATH ** {e['name']} — {e['cause']} ({e['stamp']})")
                  if e["kind"] == "death" else None)
    sim.subscribe(lambda e: print(f"  >> GOAL   {e['agent_name']} resolves to {e['description']} "
                                  f"({e['steps']} steps)") if e["kind"] == "goal_new" else None)
    sim.subscribe(lambda e: print(f"  ++ DONE   {e['agent_name']} accomplished: {e['description']}")
                  if e["kind"] == "goal_complete" else None)
    sim.subscribe(lambda e: print(f"  $$ SHOP   {e['agent_name']} opened {e['shop']} "
                                  f"(stock: {e['stock']})") if e["kind"] == "shop_founded" else None)
    trades = []
    sim.subscribe(lambda e: trades.append(e) if e["kind"] == "trade" else None)
    sim.subscribe(lambda e: print(f"  ?? QUEST  posted: {e['title']} {e['domains']}")
                  if e["kind"] == "quest_posted" else None)
    sim.subscribe(lambda e: print(f"  >! QUEST  {e['agent_name']} took on '{e['title']}'")
                  if e["kind"] == "quest_accepted" else None)
    sim.subscribe(lambda e: print(f"  *! QUEST  {e['taker_name']} completed '{e['title']}' "
                                  f"(+{e['reward_coin']} coin, +{e['reward_skill']})")
                  if e["kind"] == "quest_completed" else None)

    if args.load:
        if sim.load(args.load):
            print(f"Loaded world from {args.load} -> resuming at {sim.clock.stamp()}\n")
        else:
            print(f"No valid save at {args.load}; starting fresh.\n")

    last_digest_hour = -999
    for i in range(args.ticks):
        if args.kill and i == 40:
            sim.kill(args.kill, cause="a sudden fever")
        if args.say and i == 20:
            reply = sim.player_speak("Traveler", 32.0, 24.0, args.say)
            if reply:
                print(f"\n  >> You say to {reply['agent_name']}: \"{args.say}\"")
                print(f"  << {reply['agent_name']} replies: \"{reply['text']}\"\n")
            else:
                print("\n  >> You speak, but no villager is close enough to hear.\n")
        sim.tick()
        cur_h = sim.clock.day_index * 24 + sim.clock.hour
        if cur_h - last_digest_hour >= args.digest_hours:
            last_digest_hour = cur_h
            print(f"\n--- {sim.clock.stamp()} | weather: {sim.world.weather} ---")
            for a in sim.agents.values():
                status = "DEAD" if not a.alive else a.activity
                where = sim.world.loc(a.current_location).name
                extra = f'  "{a.say}"' if (a.say and a.say_ttl > 0) else ""
                aim = f"  <aim: {a.goal.current_step.name}>" if (a.alive and a.goal and a.goal.current_step) else ""
                print(f"  {a.name:<14} {status:<10} @ {where}{extra}{aim}")
            for s in steps[-5:]:
                print(f"    * {s['agent_name']} step: {s['step']}")
            steps.clear()
            while dialogues:
                d = dialogues.pop(0)
                print(f"    · {d['speaker_name']} -> {d['listener_name']}: \"{d['text']}\"  "
                      f"[{d['tier']}/{d['backend']}]")
            for c in crafts[-4:]:
                print(f"    ~ {c['agent_name']} ({c['skill']} {c['skill_value']}) crafted "
                      f"{c['item']} q{c['quality']} [{c['outcome']}]")
            crafts.clear()
            for t in trades[-5:]:
                print(f"    $ {t['buyer_name']} bought {t['item']} q{t['quality']} from "
                      f"{t['seller_name']} for {t['price']} coin")
            trades.clear()

    print(f"\nSimulated {args.ticks} ticks -> {sim.clock.stamp()}.")
    if args.save:
        sim.save(args.save)
        print(f"Saved world to {args.save}.")
    # tiny memory peek
    sample = next(iter(sim.agents.values()))
    print(f"\n{sample.name}'s top memories right now:")
    for m in sample.memory.retrieve("today", sim.clock.minutes, k=4):
        print(f"  [{m.importance:.0f}] {m.text}")


if __name__ == "__main__":
    main()
