"""The quest board: generation, agent interest, assignment, and rewards.

Quests are posted here (authored at world start, then emergent over time). Any
agent may take one, but only if it genuinely appeals to them: `interest` scores a
quest against the agent's personality and skills, and a content, cautious agent
will decline an adventure that does not serve their own aims. Players take quests
too, and both are rewarded with coin and skill on completion.
"""
from __future__ import annotations
from typing import Dict, List, Optional

from ..cognition.goals import Goal, Step
from .quest import Quest, QUEST_TEMPLATES

INTEREST_THRESHOLD = 0.6     # an agent must want it at least this much to take it


class QuestBoard:
    def __init__(self, sim):
        self.sim = sim
        self.quests: Dict[str, Quest] = {}
        self._counter = 0

    # ---- posting / generation -----------------------------------------
    def _new_id(self) -> str:
        self._counter += 1
        return f"q{self._counter}"

    def post_template(self, tmpl: dict, giver_id: str = "") -> Quest:
        steps = [Step(name=n, activity=a, location=l, kind=k, target=t)
                 for (n, a, l, k, t) in tmpl["steps"]]
        q = Quest(id=self._new_id(), title=tmpl["title"], description=tmpl["description"],
                  domains=list(tmpl["domains"]), giver_id=giver_id, objectives=steps,
                  reward_coin=tmpl["coin"], reward_skill=tmpl["skill"],
                  reward_amount=tmpl["amount"], created_at=self.sim.clock.minutes)
        self.quests[q.id] = q
        self.sim.emit("quest_posted", quest=q.id, title=q.title,
                      domains=q.domains, reward_coin=q.reward_coin)
        return q

    def seed(self) -> None:
        """Post a couple of starting quests so the world begins with opportunity."""
        self.post_template(QUEST_TEMPLATES[0])          # the North Road
        self.post_template(QUEST_TEMPLATES[2])          # gather herbs

    def maybe_generate(self) -> None:
        """Occasionally post a fresh emergent quest, keeping a few open."""
        if len(self.open_quests()) >= 3:
            return
        if self.sim.rng.random() < 0.01:
            tmpl = self.sim.rng.choice(QUEST_TEMPLATES)
            self.post_template(tmpl)

    def open_quests(self) -> List[Quest]:
        return [q for q in self.quests.values() if q.status == "open"]

    # ---- agent interest / taking --------------------------------------
    def interest(self, agent, quest: Quest) -> float:
        """How much this agent wants this quest (0..1-ish). Personality-driven."""
        p = agent.personality
        d = set(quest.domains)
        score = 0.3
        if d & {"Combat", "Exploration"}:
            score += p["ambition"] * 0.5 + p["curiosity"] * 0.4 - p["caution"] * 0.4
        if "Trade" in d:
            score += p["greed"] * 0.5 + p["ambition"] * 0.2
        if d & {"Social", "Faith"}:
            score += p["sociability"] * 0.5 + p["loyalty"] * 0.2
        if d & {"Craft", "Survival"}:
            score += p["industry"] * 0.4
        # competence in the rewarded skill adds a little pull
        if agent.sheet is not None:
            score += (agent.sheet.skill(quest.reward_skill) / 100.0) * 0.2
        return score

    def try_offer(self, agent) -> Optional[Goal]:
        """If an open quest appeals to the agent, assign it and return a Goal for
        it. Otherwise return None (the agent ignores the board this time)."""
        best, best_score = None, INTEREST_THRESHOLD
        for q in self.open_quests():
            s = self.interest(agent, q)
            if s >= best_score:
                best, best_score = q, s
        if best is None:
            return None
        best.status = "active"
        best.taker_id = agent.id
        self.sim.emit("quest_accepted", quest=best.id, title=best.title,
                      agent=agent.id, agent_name=agent.name)
        self.sim._observe(agent, f"I took on a quest: {best.title}.", 6.0, "reflection")
        return Goal(kind="quest", description=f"see through the quest '{best.title}'",
                    priority=min(1.0, best_score), steps=best.fresh_objectives(),
                    quest_id=best.id, created_at=self.sim.clock.minutes)

    # ---- completion / rewards -----------------------------------------
    def complete(self, taker, quest_id: str) -> None:
        q = self.quests.get(quest_id)
        if q is None or q.status == "completed":
            return
        q.status = "completed"
        taker.coin += q.reward_coin
        if getattr(taker, "sheet", None) is not None and q.reward_skill:
            cur = taker.sheet.skill(q.reward_skill)
            taker.sheet.skills[q.reward_skill] = min(100, cur + q.reward_amount)
        self.sim.emit("quest_completed", quest=q.id, title=q.title,
                      taker=getattr(taker, "id", q.taker_id),
                      taker_name=getattr(taker, "name", q.taker_id),
                      reward_coin=q.reward_coin, reward_skill=q.reward_skill)
        if getattr(taker, "memory", None) is not None:
            self.sim._observe(taker, f"I completed the quest '{q.title}' and was rewarded.", 7.0, "event")

    # ---- delve quests (driven by the sim's expedition system) ---------
    def post_delve(self, dungeon, taker) -> Quest:
        """Post a delve quest already taken by `taker`, who has answered the call
        to descend `dungeon`. The sim drives the delve; complete()/fail() close it."""
        step = Step(name=f"delve {dungeon.name}", activity="delve",
                    location=getattr(dungeon, "entrance_loc", "") or "square",
                    kind="wait", target=1)
        q = Quest(id=self._new_id(), title=f"Delve {dungeon.name}",
                  description=f"{dungeon.entrance} Danger {dungeon.danger}.",
                  domains=["Combat", "Exploration"], giver_id="", objectives=[step],
                  reward_coin=30 + dungeon.danger * 20, reward_skill="Blades",
                  reward_amount=2, status="active", taker_id=taker.id,
                  created_at=self.sim.clock.minutes)
        self.quests[q.id] = q
        self.sim.emit("quest_posted", quest=q.id, title=q.title,
                      domains=q.domains, reward_coin=q.reward_coin)
        self.sim.emit("quest_accepted", quest=q.id, title=q.title,
                      agent=taker.id, agent_name=taker.name)
        self.sim._observe(taker, f"I answered the call to delve {dungeon.name}.", 6.0, "reflection")
        return q

    def fail(self, quest_id: str, reason: str = "") -> None:
        q = self.quests.get(quest_id)
        if q is None or q.status in ("completed", "failed"):
            return
        q.status = "failed"
        self.sim.emit("quest_failed", quest=q.id, title=q.title,
                      taker=q.taker_id, reason=reason)

    def get(self, quest_id: str) -> Optional[Quest]:
        return self.quests.get(quest_id)

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        return {"counter": self._counter, "quests": [q.to_dict() for q in self.quests.values()]}

    def load(self, data: dict) -> None:
        self._counter = int(data.get("counter", 0))
        self.quests = {}
        for qd in data.get("quests", []):
            q = Quest.from_dict(qd)
            self.quests[q.id] = q
