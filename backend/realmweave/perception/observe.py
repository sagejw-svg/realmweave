"""Build one agent's subjective world - what it perceives and thinks.

This is the data behind the "through their eyes" view: only what the agent could
actually sense (via the perception model), plus its inner life (mood, current
aim, the memories surfacing right now, how it feels about who is in view, and its
own self-awareness, e.g. being wanted). Names are shown as the observed agent
knows them, so an alias holds unless they have recognized the true face.
"""
from __future__ import annotations

from . import senses as perception


def mood_of(agent) -> str:
    if not agent.alive:
        return "gone"
    if agent.wanted > 0:
        return "hunted and wary"
    if agent.energy.value < 0.25:
        return "bone-tired"
    if agent.hunger.value < 0.25:
        return "hungry"
    if agent.thirst.value < 0.25:
        return "parched"
    if agent.social.value < 0.25:
        return "lonely"
    if agent.social.value > 0.7:
        return "warm and content"
    return "even-keeled"


def build_subjective(sim, agent) -> dict:
    night = sim.clock.is_night

    seen = []
    for other in sim.living():
        if other.id == agent.id:
            continue
        if perception.can_perceive(agent, other.x, other.y, night):
            aff = agent.affinity(other.id)
            feel = "warmly" if aff > 0.2 else ("coldly" if aff < -0.2 else "neutrally")
            seen.append({
                "id": other.id,
                "name": sim.display_name(other, agent.id),
                "role": other.role,
                "activity": other.activity,
                "affinity": round(aff, 2),
                "feel": feel,
                "known_wanted": (f"wanted:{other.id}" in agent.known_facts),
            })

    context = agent.activity + " " + " ".join(s["name"] for s in seen[:3])
    memories = []
    if agent.memory is not None:
        memories = [{"text": m.text, "importance": m.importance}
                    for m in agent.memory.retrieve(context or "today", sim.clock.minutes, k=4)]

    self_notes = []
    if agent.wanted > 0:
        self_notes.append(f"I am wanted (a bounty of {agent.bounty} on my head).")
    if agent.alias:
        self_notes.append(f"Here they call me {agent.alias}.")
    if agent.god_disposition > 0.2:
        self_notes.append("I feel the gods favor me.")
    elif agent.god_disposition < -0.2:
        self_notes.append("The gods and I are not on good terms.")
    if agent.coin > 400:
        self_notes.append("My purse is heavy these days.")

    return {
        "type": "subjective",
        "agent": {
            "id": agent.id, "name": agent.name, "role": agent.role,
            "char_class": agent.sheet.emergent_class() if agent.sheet else "",
            "alias": agent.alias, "wanted": agent.wanted, "coin": agent.coin,
        },
        "where": sim.world.loc(agent.current_location).name,
        "time": sim.clock.stamp(),
        "part_of_day": sim.clock.part_of_day,
        "is_night": night,
        "mood": mood_of(agent),
        "activity": agent.activity,
        "goal": agent.goal.description if agent.goal else "no particular aim right now",
        "goal_step": (agent.goal.current_step.name if (agent.goal and agent.goal.current_step) else ""),
        "seen": seen,
        "memories": memories,
        "self_notes": self_notes,
        "needs": {
            "energy": round(agent.energy.value, 2),
            "hunger": round(agent.hunger.value, 2),
            "thirst": round(agent.thirst.value, 2),
            "social": round(agent.social.value, 2),
        },
    }
