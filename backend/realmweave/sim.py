"""The Realmweave simulation: the beating heart that advances the world.

Each `tick()`:
  1. Advance the world clock.
  2. Decay every living agent's needs.
  3. For each agent, decide an activity (urgent need > schedule) and a target
     location, then steer toward it.
  4. Apply activity effects (sleeping restores energy, eating restores hunger,
     etc.) and record observations to memory.
  5. Resolve co-located social encounters, occasionally invoking the LLM router
     to generate dialogue. Routine chatter uses the cheap `reflex` tier; charged
     encounters escalate to `dialogue`; deaths escalate to `narrative`.
  6. Emit structured events to any subscribers (server, logger).

The sim is deterministic given a seed + stubbed LLM, which makes it testable.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
import random

from .time_system import WorldClock
from .world import World
from .agents import Agent, default_agents
from .memory import MemoryStream
from .llm.router import LLMRouter, LLMRequest, Tier

EventSink = Callable[[dict], None]

ARRIVE_RADIUS = 1.5


@dataclass
class SimConfig:
    minutes_per_tick: int = 10
    seed: int = 7
    social_chance: float = 0.5        # base chance two co-located agents talk
    reflection_interval: int = 720    # world minutes between agent reflections


class Simulation:
    def __init__(self, router: LLMRouter, config: Optional[SimConfig] = None):
        self.cfg = config or SimConfig()
        self.rng = random.Random(self.cfg.seed)
        self.clock = WorldClock()
        self.world = World()
        self.router = router
        self.agents: Dict[str, Agent] = {}
        self.event_sinks: List[EventSink] = []
        self.tick_count = 0
        self._last_reflect: Dict[str, int] = {}

        embedder = router.embedder()
        for a in default_agents():
            a.memory = MemoryStream(owner=a.id, embedder=embedder)
            a.current_location = a.home
            self.agents[a.id] = a
            self._last_reflect[a.id] = 0

    # ---- events --------------------------------------------------------
    def subscribe(self, sink: EventSink) -> None:
        self.event_sinks.append(sink)

    def emit(self, kind: str, **data) -> None:
        evt = {"kind": kind, "t": self.clock.minutes, "stamp": self.clock.stamp(), **data}
        for s in self.event_sinks:
            try:
                s(evt)
            except Exception:
                pass

    # ---- helpers -------------------------------------------------------
    def living(self) -> List[Agent]:
        return [a for a in self.agents.values() if a.alive]

    def at_location(self, loc_id: str) -> List[Agent]:
        return [a for a in self.living() if a.current_location == loc_id]

    def _activity_effects(self, a: Agent) -> None:
        act = a.activity
        if act == "sleep":
            a.energy.satisfy(0.06)
        elif act == "eat":
            a.hunger.satisfy(0.20)
            a.thirst.satisfy(0.05)
        elif act == "drink":
            a.thirst.satisfy(0.30)
        elif act in ("work", "chores", "patrol"):
            a.energy.value = max(0.0, a.energy.value - 0.005)
            a.social.value = max(0.0, a.social.value - 0.003)
        elif act == "socialize":
            a.social.satisfy(0.05)

    def _observe(self, a: Agent, text: str, importance: float, kind: str = "observation") -> None:
        if a.memory is not None:
            a.memory.add(text, importance, self.clock.minutes, kind)

    # ---- decision + movement ------------------------------------------
    def _decide(self, a: Agent) -> None:
        urgent = a.urgent_need()
        if urgent is not None:
            a.activity, a.target_location = urgent
        else:
            block = a.scheduled_block(self.clock.hour)
            a.activity, a.target_location = block.activity, block.location

    def _move(self, a: Agent) -> None:
        if a.activity == "wander" and a.current_location == a.target_location:
            # pick a nearby location to drift toward
            choices = [l for l in self.world.locations if l != a.current_location]
            a.target_location = self.rng.choice(choices)
        tx, ty = self.world.pos(a.target_location)
        arrived = a.step_toward(tx, ty)
        if arrived and a.current_location != a.target_location:
            a.current_location = a.target_location
            self._observe(a, f"Arrived at {self.world.loc(a.target_location).name} to {a.activity}.", 1.0)

    # ---- social encounters --------------------------------------------
    def _maybe_socialize(self, loc_id: str) -> None:
        present = self.at_location(loc_id)
        if len(present) < 2:
            return
        # only some locations invite talk; homes/fields are quieter
        kind = self.world.loc(loc_id).kind
        base = self.cfg.social_chance
        if kind in ("home", "field"):
            base *= 0.3
        if kind in ("tavern", "square"):
            base *= 1.3
        if self.rng.random() > base:
            return

        a, b = self.rng.sample(present, 2)
        affinity = a.affinity(b.id)
        # importance rises with strong (positive or negative) feeling
        importance = 3.0 + abs(affinity) * 4.0
        tier = Tier.REFLEX if importance <= self.router.reflex_max else Tier.DIALOGUE
        context = self._dialogue_context(a, b, loc_id)
        req = LLMRequest(
            prompt=context, system=self._persona_system(a),
            importance=importance, tier=tier, other=b.name, num_predict=60,
        )
        resp = self.router.generate(req)
        line = resp.text.split("\n")[0][:180]
        a.speak(line)
        # relationships drift toward each other slightly through contact
        drift = 0.03 if affinity >= 0 else 0.01
        a.adjust_affinity(b.id, drift)
        b.adjust_affinity(a.id, drift)
        a.social.satisfy(0.04)
        b.social.satisfy(0.04)
        self._observe(a, f"Talked with {b.name} at {self.world.loc(loc_id).name}: \"{line}\"", importance, "dialogue")
        self._observe(b, f"{a.name} said to me: \"{line}\"", importance, "dialogue")
        self.emit("dialogue", speaker=a.id, speaker_name=a.name, listener=b.id,
                  listener_name=b.name, location=loc_id, text=line,
                  tier=resp.tier.value, model=resp.model, backend=resp.backend)

    def _persona_system(self, a: Agent) -> str:
        return (f"You are {a.name}, {a.role} of the village of Oakhollow. {a.persona} "
                f"Speak in one short, natural line of dialogue, in character. No narration.")

    def _dialogue_context(self, a: Agent, b: Agent, loc_id: str) -> str:
        mems = a.memory.retrieve(f"{b.name} {a.activity}", self.clock.minutes, k=3) if a.memory else []
        mem_txt = " ".join(f"[{m.text}]" for m in mems)
        aff = a.affinity(b.id)
        mood = "warmly" if aff > 0.2 else ("coldly" if aff < -0.2 else "neutrally")
        return (f"It is {self.clock.part_of_day} at {self.world.loc(loc_id).name}. "
                f"You are {a.activity}. You see {b.name} ({b.role}) and feel {mood} toward them. "
                f"Recent memories: {mem_txt or 'none'}. Say one line to {b.name}.")

    # ---- mortality -----------------------------------------------------
    def kill(self, agent_id: str, cause: str = "unknown") -> None:
        a = self.agents.get(agent_id)
        if not a or not a.alive:
            return
        a.alive = False
        a.activity = "dead"
        a.speak("")
        self.world.add_rumor(f"{a.name} died ({cause}).")
        self.emit("death", agent=a.id, name=a.name, cause=cause, location=a.current_location)
        # every living agent remembers the loss; grief scales with affinity
        for other in self.living():
            aff = other.affinity(a.id)
            importance = 6.0 + max(0.0, aff) * 4.0
            self._observe(other, f"{a.name} died ({cause}). I feel the loss.", importance, "event")
            if aff > 0.2:
                req = LLMRequest(prompt=f"grief: {a.name} has died. React.",
                                 system=self._persona_system(other),
                                 importance=8.5, tier=Tier.NARRATIVE, other=a.name, num_predict=60)
                resp = self.router.generate(req)
                other.speak(resp.text.split("\n")[0][:180], ttl=12)

    # ---- reflection ----------------------------------------------------
    def _maybe_reflect(self, a: Agent) -> None:
        if self.clock.minutes - self._last_reflect.get(a.id, 0) < self.cfg.reflection_interval:
            return
        self._last_reflect[a.id] = self.clock.minutes
        if not a.memory or len(a.memory.entries) < 3:
            return
        recent = a.memory.recent(6)
        summary = "; ".join(m.text for m in recent)
        req = LLMRequest(prompt=f"Reflect briefly on your day: {summary}",
                         system=self._persona_system(a), importance=4.0,
                         tier=Tier.DIALOGUE, num_predict=50)
        resp = self.router.generate(req)
        self._observe(a, f"Reflection: {resp.text.splitlines()[0][:180]}", 5.0, "reflection")

    # ---- main loop -----------------------------------------------------
    def tick(self) -> None:
        self.clock.advance(self.cfg.minutes_per_tick)
        self.tick_count += 1

        for a in self.living():
            a.tick_needs()
            if a.say_ttl > 0:
                a.say_ttl -= 1
            self._decide(a)
            self._move(a)
            self._activity_effects(a)
            self._maybe_reflect(a)

        for loc_id in list(self.world.locations.keys()):
            self._maybe_socialize(loc_id)

        self.emit("tick", tick=self.tick_count)

    # ---- serialization -------------------------------------------------
    def snapshot(self) -> dict:
        return {
            "clock": self.clock.to_dict(),
            "world": self.world.to_dict(),
            "agents": [a.to_dict() for a in self.agents.values()],
            "tick": self.tick_count,
        }
