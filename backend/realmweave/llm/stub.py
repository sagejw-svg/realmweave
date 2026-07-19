"""Deterministic, GPU-free stand-in for an LLM.

Lets the whole simulation run (and be tested in CI) without Ollama. It produces
short, in-character lines using simple templates seeded by the request so the
world still feels populated. Swap it out transparently via the router.
"""
from __future__ import annotations
import random
from typing import List

from . import dialogue

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
_DIVINE = {
    "accept": ["As you will it, so shall it be.", "The gods speak, and I heed. It is done.",
               "Yes... I feel the pull of something greater."],
    "partial": ["I'll take a step that way, no more.", "Perhaps, in part. I am not so bold.",
                "A little, then. We shall see where it leads."],
    "bargain": ["And what will the heavens grant me in return?", "If I do this, what is owed to me?",
                "Ask it, but know I expect a fair trade."],
    "refuse": ["The gods ask much of a simple soul. I'll keep my own road.",
               "With respect to the heavens, this is not my path.",
               "I hear you, but no. My life is here."],
}


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
        # A dedicated, per-prompt RNG (never touches the sim's RNG stream), then
        # the context-aware dialogue database picks an apt, varied line.
        rng = random.Random(hash(prompt) & 0xFFFFFFFF)
        p = prompt.lower()
        if "divine voice" in p or "the gods" in p:
            return dialogue.divine(prompt, rng)
        return dialogue.compose(prompt, other=kw.get("other", "friend"), rng=rng)
