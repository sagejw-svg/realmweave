"""Turn a chosen goal into an ordered, executable plan of Steps.

Plans are intentionally simple templates for Phase 2: they string together the
activities and locations the agent already understands (work, socialize, visit,
wander). Later phases (economy, quests) will let plans reference real resources
and world state; the structure here does not need to change for that.
"""
from __future__ import annotations
from typing import List

from .goals import Step
from ..factions.guilds import GUILDS, best_guild_for

# each factory takes the agent and returns the goal's steps
def _build_livelihood(agent) -> List[Step]:
    return [
        Step("save up coin", "work", agent.workplace, "work", target=6),
        Step("scout a storefront in the square", "visit", "square", "visit", target=1),
        Step("lay claim to a place of my own", "chores", agent.home, "work", target=3),
    ]


def _seek_adventure(agent) -> List[Step]:
    return [
        Step("harden myself with work", "work", agent.workplace, "work", target=4),
        Step("gather supplies at the square", "visit", "square", "visit", target=1),
        Step("linger at the gate, weighing the road", "wait", "gate", "wait", target=3),
    ]


def _seek_companionship(agent) -> List[Step]:
    return [
        Step("go where folk gather", "socialize", "tavern", "socialize", target=5),
    ]


def _master_craft(agent) -> List[Step]:
    return [
        Step("practice my craft in earnest", "work", agent.workplace, "work", target=10),
    ]


def _explore(agent) -> List[Step]:
    return [
        Step("wander the square", "visit", "square", "visit", target=1),
        Step("range out to the fields", "visit", "field", "visit", target=1),
        Step("walk the road to the gate", "visit", "gate", "visit", target=1),
        Step("circle back past the well", "visit", "well", "visit", target=1),
    ]


def _join_guild(agent) -> List[Step]:
    hall = GUILDS[best_guild_for(agent)].hall
    return [
        Step("earn a name worth vouching for", "work", agent.workplace, "work", target=4),
        Step("present myself at the guild hall", "visit", hall, "visit", target=1),
        Step("prove my worth to the guild", "wait", hall, "wait", target=3),
    ]


_PLANS = {
    "build_livelihood": _build_livelihood,
    "seek_adventure": _seek_adventure,
    "seek_companionship": _seek_companionship,
    "master_craft": _master_craft,
    "explore": _explore,
    "join_guild": _join_guild,
}

_DESCRIPTIONS = {
    "build_livelihood": "build a livelihood and open a shop of my own",
    "seek_adventure": "leave the quiet life and seek adventure on the road",
    "seek_companionship": "find good company and belong",
    "master_craft": "become a true master of my craft",
    "explore": "see every corner of the village and beyond",
    "join_guild": "earn a place in a guild and rise through its ranks",
}


def build_plan(kind: str, agent) -> List[Step]:
    factory = _PLANS.get(kind, _master_craft)
    return factory(agent)


def goal_description(kind: str) -> str:
    return _DESCRIPTIONS.get(kind, "make my own way in the world")
