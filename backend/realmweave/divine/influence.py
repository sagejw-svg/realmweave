"""Divine influence: the god suggests, but the agent decides.

The player-as-god can whisper a suggestion to an agent ("sell the shop and seek
something greater"). The agent weighs it against its own personality and its
disposition toward the god, then accepts, partially accepts, bargains, or
refuses, and reacts in character. Refusal is a first-class, valid outcome: this
is influence, not control. A limited `favor` resource meters how much the god can
push, so nudges feel earned.

The god can also author a character's name, background, and personality. That
seeds who a character *starts as* (identity and memory), never what they do:
behavior still emerges from goals and utility.
"""
from __future__ import annotations
from enum import Enum
from typing import Dict, Optional

from ..llm.router import LLMRequest, Tier

MAX_FAVOR = 10.0
SUGGESTION_COST = 1.0


class Outcome(str, Enum):
    ACCEPT = "accept"
    PARTIAL = "partial"
    BARGAIN = "bargain"
    REFUSE = "refuse"


# words that hint at which traits a suggestion appeals to (for the client's
# convenience; callers may also pass an explicit thrust)
_TRAIT_KEYWORDS = {
    "ambition": ["bigger", "greater", "more", "ambition", "rise", "grand", "great", "empire", "expand", "conquer", "power"],
    "curiosity": ["adventure", "explore", "road", "world", "discover", "travel", "beyond", "wander", "seek"],
    "greed": ["wealth", "riches", "coin", "gold", "profit", "sell", "fortune", "trade"],
    "sociability": ["friends", "company", "people", "together", "help", "community", "kin"],
    "caution": ["settle", "rest", "stay", "safe", "careful", "home", "quiet", "content"],
    "loyalty": ["duty", "serve", "loyal", "protect", "family", "honor"],
    "industry": ["work", "craft", "master", "build", "diligent", "labor"],
}


def infer_thrust(text: str) -> Dict[str, float]:
    t = text.lower()
    thrust = {trait: 1.0 for trait, kws in _TRAIT_KEYWORDS.items() if any(k in t for k in kws)}
    return thrust or {"ambition": 1.0}


class DivineInfluence:
    def __init__(self, sim):
        self.sim = sim
        self.favor = MAX_FAVOR

    def regen(self) -> None:
        if self.favor < MAX_FAVOR:
            self.favor = min(MAX_FAVOR, self.favor + 0.02)

    # ---- how receptive is this agent? ---------------------------------
    def receptiveness(self, agent, thrust: Dict[str, float]) -> float:
        p = agent.personality or {}
        w_sum = sum(thrust.values()) or 1.0
        align = sum(p.get(t, 0.5) * w for t, w in thrust.items()) / w_sum   # 0..1
        # bold suggestions (ambition/curiosity) meet resistance from cautious folk
        bold = (thrust.get("ambition", 0.0) + thrust.get("curiosity", 0.0)) / w_sum
        align -= p.get("caution", 0.5) * bold * 0.5
        disposition = getattr(agent, "god_disposition", 0.0)
        recept = 0.32 + align * 0.6 + disposition * 0.25
        return max(0.0, min(1.0, recept))

    @staticmethod
    def classify(recept: float) -> Outcome:
        if recept >= 0.72:
            return Outcome.ACCEPT
        if recept >= 0.56:
            return Outcome.PARTIAL
        if recept >= 0.46:
            return Outcome.BARGAIN
        return Outcome.REFUSE

    # ---- the suggestion -----------------------------------------------
    def suggest(self, agent_id: str, text: str,
                thrust: Optional[Dict[str, float]] = None,
                goal_kind: str = "") -> Optional[dict]:
        agent = self.sim.agents.get(agent_id)
        if agent is None or not agent.alive:
            return None
        thrust = thrust or infer_thrust(text)
        recept = self.receptiveness(agent, thrust)
        # a depleted favor pool makes the god's voice fainter
        if self.favor < SUGGESTION_COST:
            recept *= 0.7
        outcome = self.classify(recept)
        self.favor = max(0.0, self.favor - SUGGESTION_COST)

        reaction = self._reaction(agent, text, outcome)

        applied = False
        if outcome in (Outcome.ACCEPT, Outcome.PARTIAL) and goal_kind:
            from ..cognition.planner import build_plan, goal_description
            from ..cognition.goals import Goal
            agent.goal = Goal(kind=goal_kind, description=goal_description(goal_kind),
                              priority=0.9, steps=build_plan(goal_kind, agent),
                              created_at=self.sim.clock.minutes)
            applied = True

        delta = {"accept": 0.12, "partial": 0.06, "bargain": 0.0, "refuse": -0.06}[outcome.value]
        agent.god_disposition = max(-1.0, min(1.0, getattr(agent, "god_disposition", 0.0) + delta))

        self.sim._observe(agent, f"The god urged me: '{text}'. I chose to {outcome.value}.", 7.0, "reflection")
        self.sim.emit("divine_suggestion", agent=agent.id, agent_name=agent.name, text=text,
                      outcome=outcome.value, reaction=reaction, receptiveness=round(recept, 2),
                      applied=applied, favor=round(self.favor, 1))
        return {"agent_id": agent.id, "agent_name": agent.name, "outcome": outcome.value,
                "reaction": reaction, "receptiveness": round(recept, 2), "applied": applied,
                "favor": round(self.favor, 1)}

    def _reaction(self, agent, text: str, outcome: Outcome) -> str:
        stance = {
            Outcome.ACCEPT: "You accept the god's urging, moved to act.",
            Outcome.PARTIAL: "You half-accept, willing to take a smaller step.",
            Outcome.BARGAIN: "You bargain, asking what the heavens will grant in return.",
            Outcome.REFUSE: "You refuse, politely but firmly; this is not your path.",
        }[outcome]
        system = self.sim._persona_system(agent)
        prompt = (f"A divine voice urges you: \"{text}\". {stance} "
                  f"Reply in one short line, in character, reacting to the gods.")
        req = LLMRequest(prompt=prompt, system=system, importance=8.0,
                         tier=Tier.NARRATIVE, other="the gods", num_predict=60)
        resp = self.sim.router.generate(req)
        return resp.text.split("\n")[0][:180]

    # ---- god-authored creation ----------------------------------------
    def author(self, agent_id: str, name: str = "", background: str = "",
               personality: Optional[Dict[str, float]] = None) -> Optional[dict]:
        agent = self.sim.agents.get(agent_id)
        if agent is None:
            return None
        changed = []
        if name:
            old = agent.name
            agent.name = name
            changed.append(f"name {old} -> {name}")
        if background:
            # background seeds identity and memory, not behavior
            agent.persona = (agent.persona + " " + background).strip()
            self.sim._observe(agent, f"Background: {background}", 9.0, "reflection")
            changed.append("background")
        if personality:
            agent.personality.update({k: float(v) for k, v in personality.items()})
            changed.append("personality")
        self.sim.emit("divine_authored", agent=agent.id, agent_name=agent.name, changed=changed)
        return {"agent_id": agent.id, "agent_name": agent.name, "changed": changed}

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        return {"favor": self.favor}

    def load(self, data: dict) -> None:
        self.favor = float(data.get("favor", MAX_FAVOR))
