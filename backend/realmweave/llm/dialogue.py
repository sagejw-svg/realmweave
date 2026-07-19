"""A context-aware dialogue database for the GPU-free stub.

The goal is apparent intelligence: instead of a handful of generic lines, the
stub reads the signals already in the prompt (time of day, mood, where you are,
who you are talking to and their trade, and any death on your mind) and picks an
apt, varied line. No LLM, just a well-organised pool and a weighted chooser.
Selection is seeded by the prompt so a given situation is reproducible.
"""
from __future__ import annotations
import re

# Greetings addressed to {other}, coloured by the time of day.
GREET = {
    "morning": ["Morning, {other}.", "Up with the sun, {other}?",
                "Fresh morning, {other}. Sleep well?", "Early yet, {other}."],
    "afternoon": ["Good day, {other}.", "Fine afternoon, {other}.",
                  "Busy day, {other}?", "Well met, {other}."],
    "evening": ["Evening, {other}.", "Long day behind us, {other}.",
                "Winding down, {other}?", "Good evening to you, {other}."],
    "night": ["Late to be about, {other}.", "Can't sleep either, {other}?",
              "Mind the dark, {other}.", "Still up, {other}?"],
    "any": ["{other}. Fancy meeting you here.", "Ah, {other}.",
            "There you are, {other}."],
}

# Mood-coloured openers. Warm when they like {other}, cold when they don't.
WARM = ["Good to see a friendly face, {other}.", "Always a pleasure, {other}.",
        "You're looking well, {other}.", "I owe you a drink sometime, {other}.",
        "Glad you're about, {other}. It's been too long."]
COLD = ["{other}.", "Still here, {other}?", "I've nothing for you, {other}.",
        "Mind your business and I'll mind mine, {other}.",
        "We're not friends, {other}, let's not pretend."]
NEUTRAL = ["{other}. Keeping busy?", "Anything worth hearing, {other}?",
           "Same as ever, {other}.", "Cold enough for you, {other}?"]

# Remarks flavoured by WHERE the speaker is (keyed by location kind).
PLACE = {
    "tavern": ["The ale's honest tonight, if the stew is thin.",
               "Another round wouldn't hurt.", "Warmest room in Oakhollow, this.",
               "Bram waters the ale, I swear it."],
    "well": ["Water's cold and clean today.", "The well's low, we'll need rain.",
             "Careful on the stones, they're slick."],
    "field": ["The crop's coming on well.", "Good weather for the barley.",
              "Harvest'll be soon if this holds.", "Back's aching from the rows."],
    "farm": ["Plenty to do before the light goes.", "The soil's good to us this year.",
             "Feed's low, I'll want more from the mill."],
    "pasture": ["Flock's settled today.", "Lost a lamb to the cold last week.",
                "Grass is thin but they manage."],
    "smithy": ["Mind the sparks.", "Forge has been roaring all day.",
               "Iron's dear this season."],
    "mine": ["Deep work today, the seam runs thin.", "Watch the loose rock.",
             "Found a decent vein, might be iron."],
    "square": ["Whole village passes through here.", "Quiet in the square today.",
               "Heard the crier earlier?"],
    "gate": ["Roads have been quiet. Too quiet.", "No trouble at the gate today.",
             "Strangers about? Keep an eye out."],
    "orchard": ["Apples are near ripe.", "Blossom came early this year."],
    "stable": ["Horses are restless today.", "These stalls won't muck themselves."],
    "home": ["Peace and quiet at last.", "Come in from the cold."],
}

# Remarks addressed to {other} by THEIR trade (their role).
TO_ROLE = {
    "Blacksmith": ["How's the forge treating you, {other}?",
                   "Any new blades worth seeing, {other}?"],
    "Tavernkeeper": ["Save me a stool tonight, {other}?",
                     "How's trade at the Stag, {other}?"],
    "Farmer": ["How does the harvest look, {other}?",
               "Will the fields keep us fed this year, {other}?"],
    "Farmhand": ["Long rows today, {other}?", "The land keeping you busy, {other}?"],
    "Shepherd": ["How's the flock, {other}?", "Lose any to the cold, {other}?"],
    "Miner": ["Struck anything good down there, {other}?",
              "Mind the dark, {other}. It's hungry."],
    "Stable hand": ["How are the horses, {other}?", "Any new foals, {other}?"],
    "Herbalist": ["Got anything for an aching back, {other}?",
                  "You always know a remedy, {other}."],
    "Gate guard": ["All quiet on the road, {other}?", "Seen any strangers, {other}?"],
    "Street sweeper": ["You hear everything, {other}. Any news?",
                       "Keeping the square tidy, {other}?"],
    "Errand child": ["Slow down, {other}, you'll trip.",
                     "What's the gossip today, {other}?"],
}

# When a death is on the mind: gossip (to {other} about {subject}) or grief.
GOSSIP_DEATH = ["Terrible news about {subject}, isn't it?",
                "You heard about {subject}? Gone, just like that.",
                "The village is talking of nothing but {subject}.",
                "Say a word for {subject} when you can."]
GRIEF = ["Can't believe {subject} is gone. The village won't be the same.",
         "We buried {subject} today. Pour one out.",
         "{subject} deserved better than that end.",
         "I keep expecting to see {subject} round the corner."]

# Mundane small talk, always safe.
SMALLTALK = ["Clouds gathering over the fields.", "My back aches. Getting old, I am.",
             "Wonder what's cooking at the Stag.", "Quiet day. Suits me fine.",
             "Long as the roof holds, I'll not complain.", "Prices creep up every season.",
             "Sleep's been poor. Strange dreams."]

# Reactions to a divine suggestion, by the stance embedded in the prompt.
DIVINE = {
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

# --- reading the situation out of the prompt --------------------------------
_PLACE_KEYS = [
    ("tavern", ("tavern", "stag")), ("well", ("well",)),
    ("smithy", ("smithy", "forge")), ("mine", ("mine",)), ("gate", ("gate",)),
    ("square", ("square",)), ("pasture", ("pasture",)), ("orchard", ("orchard",)),
    ("stable", ("stable",)), ("farm", ("farm", "steading", "mill")),
    ("field", ("field", "wheat", "barley", "meadow")),
    ("home", ("cottage", "hut", "house", "room", "loft", "shack", "rest")),
]


def _pod(p):
    for t in ("morning", "afternoon", "evening", "night"):
        if t in p:
            return t
    return "any"


def _mood(p):
    return "warm" if "warmly" in p else "cold" if "coldly" in p else "neutral"


def _place_name(prompt):
    m = re.search(r" at (.+?)\. You are", prompt)
    return m.group(1) if m else "here"


def _place_kind(name):
    n = name.lower()
    for kind, keys in _PLACE_KEYS:
        if any(k in n for k in keys):
            return kind
    return ""


def _role(prompt):
    m = re.search(r"\(([^)]+)\)", prompt)
    return m.group(1) if m else ""


def _subject(prompt):
    m = re.search(r"([A-Z][\w']+(?: [A-Z][\w']+)?) has died", prompt)
    if m:
        return m.group(1)
    m = re.search(r"[Bb]uried ([A-Z][\w']+(?: [A-Z][\w']+)?)", prompt)
    return m.group(1) if m else ""


def _fmt(line, other, subject, place, role):
    return line.format(other=other or "friend", subject=subject or "them",
                       place=place or "here", role=(role or "friend"))


def divine(prompt, rng):
    """Reaction to a divine suggestion, by the stance embedded in the prompt."""
    p = prompt.lower()
    stance = ("refuse" if "refuse" in p else "partial" if "half-accept" in p
              else "bargain" if "bargain" in p else "accept")
    return rng.choice(DIVINE[stance])


def compose(prompt, other="friend", rng=None):
    """Pick an apt, varied line for a dialogue prompt. Weighted toward the parts
    of the situation that carry meaning (where you are, who you're talking to,
    a death on your mind) so replies feel considered rather than canned."""
    import random as _random
    if rng is None:
        rng = _random.Random(hash(prompt) & 0xFFFFFFFF)
    p = prompt.lower()
    place_name = _place_name(prompt)
    role = _role(prompt)

    subject = _subject(prompt)
    if subject or "has died" in p or "buried" in p or "grief" in p:
        pool = GOSSIP_DEATH if rng.random() < 0.55 else GRIEF
        return _fmt(rng.choice(pool), other, subject, place_name, role)

    pod, mood, place = _pod(p), _mood(p), _place_kind(place_name)
    cats = [("greet", 2), ("mood", 2), ("small", 2)]
    if place in PLACE:
        cats.append(("place", 4))
    if role in TO_ROLE:
        cats.append(("role", 3))
    total = sum(w for _, w in cats)
    pick, upto, chosen = rng.random() * total, 0, "small"
    for c, w in cats:
        upto += w
        if pick <= upto:
            chosen = c
            break
    if chosen == "greet":
        pool = GREET.get(pod, []) + GREET["any"]
    elif chosen == "mood":
        pool = WARM if mood == "warm" else COLD if mood == "cold" else NEUTRAL
    elif chosen == "place":
        pool = PLACE[place]
    elif chosen == "role":
        pool = TO_ROLE[role]
    else:
        pool = SMALLTALK
    return _fmt(rng.choice(pool), other, subject, place_name, role)
