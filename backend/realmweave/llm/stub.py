"""Deterministic, GPU-free stand-in for an LLM.

Lets the whole simulation run (and be tested in CI) without Ollama. It produces
short, in-character lines using simple templates seeded by the request so the
world still feels populated. Swap it out transparently via the router.
"""
from __future__ import annotations
import random
from typing import List

_GREETINGS = [
    "Well met, {other}.", "Morning to you, {other}.", "Ah, {other}. Good to see a familiar face.",
    "You look weary, {other}.", "{other}. Fancy meeting you here.",
]
_TAVERN = [
    "Another round for the house, aye?", "The stew's thin tonight but the ale is honest.",
    "Heard the roads north have gone quiet. Too quiet.", "Wipe that table, would you? Patrons are watching.",
    "One more and I'm cutting you off, friend.",
]
_WORK = [
    "Back to it, then. Work won't do itself.", "These hooves won't clean themselves.",
    "Mind the fire, it's hungry today.", "Another cart to load before dusk.",
    "The well's running low. We'll need to ration.",
]
_IDLE = [
    "Quiet day. Suits me fine.", "Clouds gathering over the fields.",
    "My back aches. Getting old, I am.", "Wonder what's cooking at the Stag.",
]
_GRIEF = [
    "Can't believe {other} is gone. The village won't be the same.",
    "We buried {other} today. Pour one out.",
    "{other} deserved better than that end.",
]


class StubLLM:
    name = "stub"

    def line(self, kind: str, speaker: str = "", other: str = "", seed: str = "") -> str:
        rng = random.Random(hash((kind, speaker, other, seed)) & 0xFFFFFFFF)
        if kind == "greeting":
            pool = _GREETINGS
        elif kind == "tavern":
            pool = _TAVERN
        elif kind == "work":
            pool = _WORK
        elif kind == "grief":
            pool = _GRIEF
        else:
            pool = _IDLE
        return rng.choice(pool).format(other=other or "friend", speaker=speaker or "someone")

    def generate(self, prompt: str, system: str = "", **kw) -> str:
        # crude routing by keyword so the stub stays vaguely relevant
        p = prompt.lower()
        other = kw.get("other", "friend")
        if "died" in p or "grief" in p or "buried" in p:
            return self.line("grief", other=other, seed=prompt)
        if "tavern" in p or "ale" in p or "stag" in p:
            return self.line("tavern", seed=prompt)
        if "work" in p or "stable" in p or "field" in p or "smith" in p:
            return self.line("work", seed=prompt)
        if "meet" in p or "greet" in p or "hello" in p:
            return self.line("greeting", other=other, seed=prompt)
        return self.line("idle", seed=prompt)
