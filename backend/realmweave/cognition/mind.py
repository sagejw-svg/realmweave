"""The Mind: goal generation, utility-based action selection, and goal progress.

This is what turns schedule-following villagers into agents that make their own
way. Each tick an agent's next action is chosen by scoring candidate actions
(satisfy a need, pursue the current goal step, or fall back to routine) and
picking the best, with the weights bent by personality. Goals are generated from
personality and needs, decomposed into plans by the planner, and advanced as the
agent actually carries them out.

The Mind operates on the simulation by duck typing (it uses sim.world, sim.rng,
sim.clock, sim.emit, sim._observe) to avoid an import cycle with sim.py.
"""
from __future__ import annotations
from typing import Optional, Tuple

from .personality import seed_personality
from .goals import Goal
from .planner import build_plan, goal_description

GOAL_THRESHOLD = 0.5     # minimum score before an agent commits to a goal


class Mind:
    def __init__(self, sim):
        self.sim = sim

    # ---- setup ---------------------------------------------------------
    def ensure_personality(self, agent) -> None:
        if not agent.personality:
            agent.personality = seed_personality(agent.id)

    # ---- goal generation ----------------------------------------------
    def propose_goal(self, agent) -> Optional[Goal]:
        p = agent.personality
        social = agent.social.value
        econ = getattr(self.sim, "economy", None)
        owns_shop = econ is not None and agent.id in econ.shops
        candidates = [
            (p["ambition"] * 0.5 + p["curiosity"] * 0.5 - p["caution"] * 0.3, "seek_adventure"),
            (p["sociability"] * 0.6 + (1.0 - social) * 0.3, "seek_companionship"),
            (p["industry"] * 0.6 + 0.2, "master_craft"),
            (p["curiosity"] * 0.7 - p["caution"] * 0.2, "explore"),
        ]
        # only pursue building a livelihood if you don't already own a shop
        if not owns_shop:
            candidates.append((p["ambition"] * 0.6 + p["greed"] * 0.4 + p["industry"] * 0.2,
                               "build_livelihood"))
        score, kind = max(candidates, key=lambda t: t[0])
        if score < GOAL_THRESHOLD:
            return None
        return Goal(kind=kind, description=goal_description(kind),
                    priority=min(1.0, score), steps=build_plan(kind, agent),
                    created_at=self.sim.clock.minutes)

    def maybe_generate_goal(self, agent) -> None:
        if agent.goal is not None:
            return
        # agents have downtime between aims (leisure, browsing, socializing)
        # rather than instantly grabbing a new quest every tick
        if self.sim.rng.random() > 0.05:
            return
        goal = self.propose_goal(agent)
        if goal is None:
            return
        agent.goal = goal
        self.sim.emit("goal_new", agent=agent.id, agent_name=agent.name,
                      goal=goal.kind, description=goal.description,
                      priority=round(goal.priority, 2), steps=len(goal.steps))
        self.sim._observe(agent, f"I have resolved to {goal.description}.", 6.0, "reflection")

    # ---- action selection (utility) -----------------------------------
    def choose(self, agent) -> Tuple[str, str]:
        """Return (activity, location) for this tick by scoring candidates."""
        p = agent.personality
        night = self.sim.clock.is_night
        cands = [
            ((1.0 - agent.energy.value) * (1.1 if night else 0.5), "sleep", agent.home),
            ((1.0 - agent.hunger.value) * 0.9, "eat", "tavern"),
            ((1.0 - agent.thirst.value) * 0.9, "drink", "well"),
            ((1.0 - agent.social.value) * p["sociability"] * 0.9, "socialize", "tavern"),
        ]
        # pursue the active goal's current step
        if agent.goal is not None and agent.goal.current_step is not None:
            step = agent.goal.current_step
            cands.append((agent.goal.priority * 0.85, step.activity, step.location))
        # browse a shop when comfortable and holding coin (greedy/curious folk more so)
        econ = getattr(self.sim, "economy", None)
        if econ is not None and agent.coin >= 5:
            shop_loc = econ.nearest_open_shop_location(agent)
            if shop_loc is not None:
                drive = 0.45 * max(p["greed"], p["curiosity"])
                cands.append((drive, "visit", shop_loc))
        # routine fallback (do your job / scheduled activity)
        block = agent.scheduled_block(self.sim.clock.hour)
        cands.append((0.35, block.activity, block.location))

        cands.sort(key=lambda c: c[0], reverse=True)
        _, activity, location = cands[0]
        return activity, location

    # ---- goal progress -------------------------------------------------
    def progress_goal(self, agent) -> None:
        g = agent.goal
        if g is None or g.current_step is None:
            return
        step = g.current_step
        at = agent.current_location == step.location
        if step.kind == "visit":
            if at:
                step.progress = step.target
        elif step.kind == "wait":
            if at:
                step.progress += 1
        else:  # work / socialize
            if at and agent.activity == step.activity:
                step.progress += 1

        if step.done:
            self.sim.emit("goal_step", agent=agent.id, agent_name=agent.name,
                          step=step.name, goal=g.kind)
            self.sim._observe(agent, f"Made progress toward my aim ({g.description}): {step.name}.",
                              4.0, "event")
            if g.advance():
                self.sim.emit("goal_complete", agent=agent.id, agent_name=agent.name,
                              goal=g.kind, description=g.description)
                self.sim._observe(agent, f"I accomplished my aim: {g.description}.", 7.0, "reflection")
                # let the sim turn certain finished goals into world state
                # (e.g. a 'build a livelihood' goal founds a real shop)
                hook = getattr(self.sim, "_on_goal_complete", None)
                if hook is not None:
                    hook(agent, g)
                agent.goal = None
