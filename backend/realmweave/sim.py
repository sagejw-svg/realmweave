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
from .economy.finance import Finance
from .economy.goods import make_item
from .economy.recipes import RECIPES, GATHER
from .quests.board import QuestBoard
from .divine.influence import DivineInfluence
from .perception import senses as perception
from .reputation.justice import Justice
from .factions.guilds import Guilds
from .llm.router import LLMRouter, LLMRequest, Tier

EventSink = Callable[[dict], None]

ARRIVE_RADIUS = 1.5

# ---- mortality / survival tuning --------------------------------------
# A need at or below this counts as starvation.
STARVE_THRESHOLD = 0.02
# Starvation must be *sustained* this many consecutive ticks before it bleeds
# health, so brief dips while walking to food/water are survivable.
STARVE_GRACE = 10
# Health lost per tick per starving need (past the grace), and regained per tick
# when an agent is not starving.
HEALTH_DRAIN = 0.03
HEALTH_REGEN = 0.03
# Subsistence floor: after this many consecutive ticks with a need critically
# low, an agent forages just enough to not die (a bare-hands floor so no state
# is ever an unrecoverable dead end), and a one-shot `stuck` event is emitted.
STUCK_TICKS = 15
STUCK_NEED = 0.10
FORAGE = 0.05                         # meager: reaching a real source is better


@dataclass
class SimConfig:
    minutes_per_tick: int = 10
    seed: int = 7
    social_chance: float = 0.5        # base chance two co-located agents talk
    reflection_interval: int = 720    # world minutes between agent reflections
    # per-agent, per-tick chance of a random illness/accident death. Modified by
    # frailty (low health). Defaults to 0.0 so seeded stub runs stay fully
    # deterministic (tests); the headless demo and server can raise it so the
    # world produces natural deaths - and the grief that follows - on its own.
    illness_chance: float = 0.0


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
        # logged-out player characters, frozen in a protected "resting" bubble
        # keyed by name: state is preserved and untouchable until they return
        self.offline_players: Dict[str, dict] = {}

        self.mind = Mind(self)
        self.economy = Economy(self)
        self.finance = Finance(self)
        self.quests = QuestBoard(self)
        self.divine = DivineInfluence(self)
        self.justice = Justice(self)
        self.guilds = Guilds(self)

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
        self.guilds.seed()               # the lawful faction (the guard) exists from tick one

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

    def _loc_kind(self, a: Agent) -> str:
        loc = self.world.locations.get(a.current_location)
        return loc.kind if loc is not None else ""

    def _activity_effects(self, a: Agent) -> None:
        """Apply the payoff of the current activity - but only where it makes
        sense. Eating, drinking, and sleeping satisfy their needs *on arrival* at
        the tavern, the well, and home respectively; while an agent is still
        walking there the need keeps pulling. This is what makes movement matter:
        needs are spatial, so agents actually go somewhere (and cross paths). The
        payoffs are generous so a single visit buys a real buffer - otherwise,
        with sources a walk away, an agent could never get ahead of its needs and
        would have no time left to pursue goals."""
        act = a.activity
        kind = self._loc_kind(a)
        if act == "sleep":
            if kind == "home" or a.current_location == a.home:
                a.energy.satisfy(0.10)
        elif act == "eat":
            if kind in ("tavern", "shop"):
                a.hunger.satisfy(0.34)
                a.thirst.satisfy(0.08)
        elif act == "drink":
            if kind in ("well", "tavern"):
                a.thirst.satisfy(0.50)
        elif act in ("work", "chores", "patrol"):
            a.energy.value = max(0.0, a.energy.value - 0.005)
            a.social.value = max(0.0, a.social.value - 0.003)
        elif act == "socialize":
            a.social.satisfy(0.05)

    def _survival_watchdog(self, a: Agent) -> None:
        """Guarantee a floor so no agent is ever trapped in a death-spiral it
        cannot act its way out of (e.g. its only water source is unreachable or
        occupied). If a survival need stays critically low for STUCK_TICKS, emit
        a visible `stuck` event once and let the agent forage a meager amount -
        enough to survive, never enough to make reaching a real source pointless.
        """
        low = min(a.energy.value, a.hunger.value, a.thirst.value)
        if low < STUCK_NEED:
            a._low_ticks = getattr(a, "_low_ticks", 0) + 1
        else:
            a._low_ticks = 0
        if a._low_ticks == STUCK_TICKS:      # fire exactly once at the threshold
            self.emit("stuck", agent=a.id, agent_name=a.name,
                      energy=round(a.energy.value, 2), hunger=round(a.hunger.value, 2),
                      thirst=round(a.thirst.value, 2), location=a.current_location)
            self._observe(a, "I am in a bad way and cannot get what I need.", 5.0, "event")
        if a._low_ticks >= STUCK_TICKS:
            if a.thirst.value < STUCK_NEED:
                a.thirst.satisfy(FORAGE)
            if a.hunger.value < STUCK_NEED:
                a.hunger.satisfy(FORAGE)
            if a.energy.value < STUCK_NEED:
                a.energy.satisfy(FORAGE)

    def _mortality(self, a: Agent) -> None:
        """The natural death path. Sustained need-starvation drains health; at 0
        the agent dies of what starved them. A small, frailty-weighted illness/
        accident roll (config: illness_chance, 0 by default) can also carry
        someone off. This is the beating heart of the pitch - a world left
        running can now produce a funeral, and the grief-ripple, with no dev
        hand on the scale."""
        starving = []
        if a.energy.value <= STARVE_THRESHOLD:
            starving.append("exhaustion")
        if a.thirst.value <= STARVE_THRESHOLD:
            starving.append("thirst")
        if a.hunger.value <= STARVE_THRESHOLD:
            starving.append("hunger")
        if starving:
            a._starve_ticks = getattr(a, "_starve_ticks", 0) + 1
            # only sustained starvation bleeds health, so a brief dip while
            # walking to relief is survivable; a genuinely stuck agent (caught by
            # the subsistence floor) is the only one who should be at real risk.
            if a._starve_ticks > STARVE_GRACE:
                a.health = max(0.0, a.health - HEALTH_DRAIN * len(starving))
                if a.health <= 0.0:
                    self.kill(a.id, cause=starving[0])
                    return
        else:
            a._starve_ticks = 0
            a.health = min(1.0, a.health + HEALTH_REGEN)
        chance = self.cfg.illness_chance
        if chance > 0.0:
            frailty = 1.0 + (1.0 - a.health) * 3.0     # the frail are likelier to fall
            if self.rng.random() < chance * frailty:
                self.kill(a.id, cause=self.rng.choice(("a sudden illness", "an accident")))

    def _observe(self, a: Agent, text: str, importance: float, kind: str = "observation") -> None:
        if a.memory is not None:
            a.memory.add(text, importance, self.clock.minutes, kind)

    # ---- decision + movement ------------------------------------------
    def _decide(self, a: Agent) -> None:
        # chasing a wanted criminal overrides ordinary life
        target_id = getattr(a, "_pursuing", "")
        if target_id:
            target = self.agents.get(target_id)
            if target is not None and target.alive and target.wanted > 0:
                a.activity, a.target_location = "pursue", target.current_location
                return
            a._pursuing = ""
        # survival needs still hard-override the rest
        urgent = a.urgent_need()
        if urgent is not None:
            a.activity, a.target_location = urgent
            return
        # commitment optimization: once an agent has chosen where to go, it keeps
        # walking there and does NOT re-evaluate every tick. It only forms a new
        # intent when it arrives at its destination (below) or is interrupted by a
        # survival need or a pursuit (handled above). This makes movement
        # purposeful and cuts decision churn.
        if (a.target_location and a.target_location in self.world.locations
                and a.current_location != a.target_location):
            return
        # arrived (or idle): the Mind scores needs, the active goal step, and
        # routine, and picks the next highest-utility action.
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
        # gossip: news travels through conversation, both directions
        self._spread_rumor(a, b)
        self._spread_rumor(b, a)

    def _spread_rumor(self, speaker: Agent, listener: Agent) -> None:
        """The speaker may pass on a fact the listener does not yet know."""
        fresh = speaker.known_facts - listener.known_facts
        if not fresh:
            return
        fact = sorted(fresh)[0]
        listener.known_facts.add(fact)
        if fact.startswith("death:"):
            who = self.agents.get(fact.split(":", 1)[1])
            name = who.name if who else "someone"
            self._observe(listener, f"{speaker.name} told me that {name} has died.", 6.0, "event")
            self.emit("rumor", fact=fact, from_agent=speaker.id, from_name=speaker.name,
                      to_agent=listener.id, to_name=listener.name, subject=name)

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
        # only those who WITNESS the death learn of it now (a death is loud, so it
        # also carries to anyone within earshot). Everyone else stays unaware until
        # the news reaches them by rumor. This is the core of the perception model.
        fact = f"death:{a.id}"
        dx, dy = a.x, a.y
        for other in self.witnesses(dx, dy, loud=True, exclude=a.id):
            other.known_facts.add(fact)
            aff = other.affinity(a.id)
            importance = 6.0 + max(0.0, aff) * 4.0
            self._observe(other, f"I saw that {a.name} died ({cause}). I feel the loss.", importance, "event")
            if aff > 0.2:
                req = LLMRequest(prompt=f"grief: {a.name} has died. React.",
                                 system=self._persona_system(other),
                                 importance=8.5, tier=Tier.NARRATIVE, other=a.name, num_predict=60)
                resp = self.router.generate(req)
                other.speak(resp.text.split("\n")[0][:180], ttl=12)

    # ---- perception ----------------------------------------------------
    def witnesses(self, x: float, y: float, loud: bool = False, exclude: str = ""):
        """Living agents who can perceive something happening at (x, y)."""
        night = self.clock.is_night
        return [a for a in self.living()
                if a.id != exclude and perception.can_perceive(a, x, y, night, loud)]

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
        """When an agent works at a production site, mechanics drive the outcome.
        Primary sites yield raw materials (gathering); refining sites consume the
        recipe's inputs - sourced from a neighbour or, failing that, the supplier
        at a premium - and a skill check sets the finished good's quality. A
        refiner who cannot secure its inputs simply makes nothing this tick."""
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

        # gathering: primary work brings in a raw material, no input needed
        mat = GATHER.get(kind)
        if mat is not None:
            a.materials[mat] = a.materials.get(mat, 0) + 1
            self._observe(a, f"Gathered {mat} (now {a.materials[mat]} on hand).", 1.5, "event")
            self.emit("gather", agent=a.id, agent_name=a.name, material=mat,
                      qty=a.materials[mat], location=a.current_location)
            return

        # refining: secure the recipe's inputs before making anything
        for material, qty in RECIPES.get(skill, []):
            have = a.materials.get(material, 0)
            if have < qty:
                self.economy.supply.acquire(a, material, qty - have)
            if a.materials.get(material, 0) < qty:
                # still short (could not afford supply): production waits
                self.emit("shortage", agent=a.id, agent_name=a.name,
                          material=material, skill=skill, location=a.current_location)
                return
        for material, qty in RECIPES.get(skill, []):
            a.materials[material] -= qty

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
        elif goal.kind == "join_guild":
            from .factions.guilds import best_guild_for
            self.guilds.join(agent, best_guild_for(agent))
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

    def _nearest_living(self, x: float, y: float, radius: float) -> Optional[Agent]:
        """The nearest living agent within `radius` of a point, or None."""
        target, best = None, radius
        for a in self.living():
            d = math.hypot(a.x - x, a.y - y)
            if d <= best:
                best, target = d, a
        return target

    def player_buy(self, player_name: str, x: float, y: float, coin: int,
                   item_index: Optional[int] = None, radius: float = 6.0) -> dict:
        """A player buys from the nearest open shop within reach. Authoritative:
        the caller (server) owns the player's coin and only debits it on a
        success we report here. The world side - stock, the owner's coin and
        memory of the sale - is settled deterministically in code, never by the
        model. Returns {ok, ...}; on success includes the item and price.
        """
        shop = self.economy.nearest_shop_within(x, y, radius)
        if shop is None or not shop.stock:
            return {"ok": False, "reason": "no open shop within reach"}
        if item_index is not None and 0 <= item_index < len(shop.stock):
            item = shop.stock[item_index]
        else:
            affordable = [it for it in shop.stock if self.economy.list_price(shop, it) <= coin]
            if not affordable:
                return {"ok": False, "reason": "cannot afford anything here"}
            item = min(affordable, key=lambda it: it.value())   # start with the humblest
        res = self.economy.sell_to_player(coin, shop, item, player_name)
        if res is None:
            return {"ok": False, "reason": "too costly"}
        return {"ok": True, "shop": shop.name, **res}

    def player_give(self, player_name: str, x: float, y: float, amount: int = 0,
                    gift: str = "a small gift", radius: float = 6.0) -> dict:
        """A player gives a gift (coin, or a named token) to the nearest NPC. The
        gift becomes a durable, warmly-remembered memory and lifts the NPC's
        affinity toward the player. This is the cheapest path to a real emergent
        story beat: an NPC who remembers a kindness and acts differently for it.
        """
        target = self._nearest_living(x, y, radius)
        if target is None:
            return {"ok": False, "reason": "no one close enough to receive a gift"}
        pkey = f"player:{player_name}"
        if amount and amount > 0:
            target.coin += int(amount)
            desc = f"{int(amount)} coin"
        else:
            desc = gift
        target.adjust_affinity(pkey, 0.15)      # a gift is remembered warmly
        self._observe(target, f"{player_name} gave me {desc}. I will remember this kindness.",
                      7.0, "event")
        self.emit("gift", player=player_name, to=target.id, to_name=target.name, gift=desc)
        return {"ok": True, "agent_id": target.id, "agent_name": target.name, "gift": desc}

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
            self._survival_watchdog(a)   # floor first, so it can rescue the stuck
            self._mortality(a)           # then judge health / natural death
            if not a.alive:              # died this tick: skip the rest of its turn
                continue
            self._maybe_craft(a)
            self.mind.progress_goal(a)
            self._maybe_reflect(a)

        for loc_id in list(self.world.locations.keys()):
            self._maybe_socialize(loc_id)

        self.economy.maybe_trade()
        self.finance.step()          # daily rent, wages, and the relief floor
        self.guilds.step()           # daily guild dues and rank progression
        self.quests.maybe_generate()
        self.divine.regen()
        self.justice.step()

        self.emit("tick", tick=self.tick_count)

    # ---- subjective view (through their eyes) -------------------------
    def subjective_view(self, agent_id: str) -> Optional[dict]:
        from .perception.observe import build_subjective
        a = self.agents.get(agent_id)
        if a is None:
            return None
        return build_subjective(self, a)

    def inner_thought(self, agent_id: str) -> Optional[str]:
        """Generate a first-person inner-monologue line for an agent, in the
        moment. Uses the LLM (dialogue tier) with the stub as a GPU-free fallback."""
        a = self.agents.get(agent_id)
        if a is None or not a.alive:
            return None
        view = self.subjective_view(agent_id)
        who = ", ".join(s["name"] for s in view["seen"][:3]) or "no one in particular"
        mem = view["memories"][0]["text"] if view["memories"] else "the day so far"
        prompt = (f"It is {view['part_of_day']} at {view['where']}. You are {view['mood']}, "
                  f"{view['activity']}. You see {who}. On your mind: {mem}. "
                  f"Your aim: {view['goal']}. Think one short first-person line to yourself.")
        req = LLMRequest(prompt=prompt, system=self._persona_system(a),
                         importance=4.0, tier=Tier.DIALOGUE, num_predict=50)
        resp = self.router.generate(req)
        return resp.text.split("\n")[0][:200]

    # ---- identity ------------------------------------------------------
    def display_name(self, agent: Agent, viewer_id: str = "") -> str:
        """The name a given viewer knows this agent by. An alias holds unless the
        viewer has seen the true face behind it (e.g. witnessed a crime)."""
        if agent.alias and viewer_id not in agent.recognized_by:
            return agent.alias
        return agent.name

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
            "favor": round(self.divine.favor, 1),
            "treasury": self.finance.treasury,
            "ledger": self.economy.ledger.tail(12),
            "guilds": [{"id": gid, "members": self.guilds.members(gid),
                        "coffer": self.guilds.coffers[gid]}
                       for gid in self.guilds.rosters],
            "tick": self.tick_count,
        }
