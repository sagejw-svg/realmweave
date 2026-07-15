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
import math
import random

from .time_system import WorldClock
from .world import World
from .agents import Agent, default_agents
from .memory import MemoryStream
from .rules.skills import role_sheet
from .cognition.mind import Mind
from .cognition.personality import seed_personality
from .economy.market import Economy
from .economy.goods import make_item
from .quests.board import QuestBoard
from .divine.influence import DivineInfluence
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

        self.mind = Mind(self)
        self.economy = Economy(self)
        self.quests = QuestBoard(self)
        self.divine = DivineInfluence(self)

        embedder = router.embedder()
        for a in default_agents():
            a.memory = MemoryStream(owner=a.id, embedder=embedder)
            a.sheet = role_sheet(a.role)
            a.personality = seed_personality(a.id)
            a.coin = 150                     # starting money to trade with
            a.inventory = []
            a.current_location = a.home
            self.agents[a.id] = a
            self._last_reflect[a.id] = 0

        self.quests.seed()               # the world begins with opportunity

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
        # survival needs still hard-override everything
        urgent = a.urgent_need()
        if urgent is not None:
            a.activity, a.target_location = urgent
            return
        # otherwise the Mind scores needs, the active goal step, and routine,
        # and picks the highest-utility action (personality bends the weights)
        a.activity, a.target_location = self.mind.choose(a)

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
        skills = ""
        if a.sheet is not None:
            skills = f" You are a {a.sheet.summary()}."
        return (f"You are {a.name}, {a.role} of the village of Oakhollow. {a.persona}{skills} "
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

    # ---- crafting (skills drive outcomes) -----------------------------
    def _maybe_craft(self, a: Agent) -> None:
        """When an agent works at a production site, a skill check sets the
        quality of what they make. This is the first place mechanics (the 1-100
        skills) visibly drive world outcomes."""
        if a.activity != "work" or a.sheet is None:
            return
        kind = self.world.loc(a.current_location).kind
        if kind == "smithy":
            skill, item = "Smithing", "a piece of armor"
        elif kind == "field":
            skill, item = "Farming", "a bushel of produce"
        elif kind == "well":
            skill, item = "Herbalism", "a healing remedy"
        elif kind == "tavern":
            skill, item = "Cooking", "a hot meal"
        else:
            return
        if self.rng.random() > 0.2:      # not every tick
            return
        quality, res = a.sheet.craft(skill, self.rng)
        # the crafted good becomes a real Item: stocked in the owner's shop if
        # they have one, otherwise held in their inventory to sell or stock later
        good = make_item(skill, quality)
        shop = self.economy.shops.get(a.id)
        if shop is not None and shop.is_open:
            shop.stock.append(good)
        else:
            a.inventory.append(good)
        self._observe(a, f"Worked {skill} and made {item} (quality {quality}).", 2.0, "event")
        self.emit("craft", agent=a.id, agent_name=a.name, item=item, quality=quality,
                  skill=skill, skill_value=a.sheet.skill(skill), roll=res.roll,
                  outcome=res.outcome.value)

    def _on_goal_complete(self, agent: Agent, goal) -> None:
        """Hook the Mind calls when an agent finishes a goal. Turning a
        'build a livelihood' aim into a shop, or a quest into its reward,
        happens here."""
        if goal.kind == "build_livelihood":
            self.economy.found_shop(agent)
        elif goal.kind == "quest" and goal.quest_id:
            self.quests.complete(agent, goal.quest_id)

    # ---- player interaction -------------------------------------------
    def player_speak(self, player_name: str, x: float, y: float, text: str,
                     radius: float = 6.0) -> Optional[dict]:
        """Route a player's spoken line to the nearest living NPC and reply.

        The NPC remembers being addressed (so it can reference the exchange
        later), forms/updates an affinity toward the player, and answers in
        character via the `dialogue` tier. Returns the reply, or None if no NPC
        was within earshot.
        """
        target = None
        best = radius
        for a in self.living():
            d = math.hypot(a.x - x, a.y - y)
            if d <= best:
                best, target = d, a
        if target is None:
            return None

        pkey = f"player:{player_name}"
        self._observe(target, f"{player_name} (a traveler) said to me: \"{text}\"", 5.0, "dialogue")
        mems = target.memory.retrieve(f"{player_name} {text}", self.clock.minutes, k=3) if target.memory else []
        mem_txt = " ".join(f"[{m.text}]" for m in mems)
        aff = target.affinity(pkey)
        mood = "warmly" if aff > 0.2 else ("warily" if aff < -0.2 else "evenly")
        prompt = (f"A traveler named {player_name} approaches you at "
                  f"{self.world.loc(target.current_location).name} during the {self.clock.part_of_day} "
                  f"and says: \"{text}\". You regard them {mood}. "
                  f"Recent memories: {mem_txt or 'none'}. Reply in one short line, in character.")
        importance = 4.0 + abs(aff) * 3.0
        req = LLMRequest(prompt=prompt, system=self._persona_system(target),
                         importance=importance, tier=Tier.DIALOGUE, other=player_name, num_predict=60)
        resp = self.router.generate(req)
        line = resp.text.split("\n")[0][:180]
        target.speak(line, ttl=10)
        target.adjust_affinity(pkey, 0.02)
        target.social.satisfy(0.05)
        self._observe(target, f"I replied to {player_name}: \"{line}\"", 3.0, "dialogue")
        self.emit("dialogue", speaker=target.id, speaker_name=target.name,
                  listener=pkey, listener_name=player_name, location=target.current_location,
                  text=line, tier=resp.tier.value, model=resp.model, backend=resp.backend,
                  to_player=True)
        return {"agent_id": target.id, "agent_name": target.name, "text": line}

    # ---- persistence ---------------------------------------------------
    def save(self, path: str) -> None:
        from .persistence import save_world
        save_world(self, path)

    def load(self, path: str) -> bool:
        from .persistence import load_world
        return load_world(self, path)

    # ---- main loop -----------------------------------------------------
    def tick(self) -> None:
        self.clock.advance(self.cfg.minutes_per_tick)
        self.tick_count += 1

        for a in self.living():
            a.tick_needs()
            if a.say_ttl > 0:
                a.say_ttl -= 1
            self.mind.ensure_personality(a)
            self.mind.maybe_generate_goal(a)
            self._decide(a)
            self._move(a)
            self._activity_effects(a)
            self._maybe_craft(a)
            self.mind.progress_goal(a)
            self._maybe_reflect(a)

        for loc_id in list(self.world.locations.keys()):
            self._maybe_socialize(loc_id)

        self.economy.maybe_trade()
        self.quests.maybe_generate()
        self.divine.regen()

        self.emit("tick", tick=self.tick_count)

    # ---- serialization -------------------------------------------------
    def snapshot(self) -> dict:
        return {
            "clock": self.clock.to_dict(),
            "world": self.world.to_dict(),
            "agents": [a.to_dict() for a in self.agents.values()],
            "shops": [{"name": s.name, "location": s.location_id, "owner": s.owner_id,
                       "x": s.x, "y": s.y, "stock": len(s.stock)}
                      for s in self.economy.shops.values()],
            "quests": [{"id": q.id, "title": q.title, "domains": q.domains,
                        "status": q.status, "taker": q.taker_id,
                        "reward_coin": q.reward_coin}
                       for q in self.quests.quests.values()
                       if q.status in ("open", "active")],
            "tick": self.tick_count,
        }
