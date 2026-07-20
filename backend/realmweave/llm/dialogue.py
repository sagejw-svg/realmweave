"""A context-aware dialogue database for the GPU-free stub.

The goal is apparent intelligence without an LLM: read the signals already in the
prompt (time of day, mood, where you are, who you are talking to and their trade,
a death on your mind, and the speaker's recent memories) and pick an apt, varied
line. Two mechanisms do the heavy lifting:

  1. A small generative GRAMMAR (Tracery-style fragment recombination) so a compact,
     human-editable fragment set yields thousands of non-repeating lines.
  2. Memory/relationship conditioning: recent memories that mention the other person
     (or carry a clear sentiment) let a canned line become specific and personal.

Selection is seeded by the prompt so a given situation is reproducible.
"""
from __future__ import annotations
import random as _random
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

# Mundane small talk (legacy pool; the GRAMMAR below now produces most of it).
SMALLTALK = ["Clouds gathering over the fields.", "My back aches. Getting old, I am.",
             "Wonder what's cooking at the Stag.", "Quiet day. Suits me fine.",
             "Long as the roof holds, I'll not complain.", "Prices creep up every season.",
             "Sleep's been poor. Strange dreams."]

# Lines that reference shared history, chosen when a memory mentions the other
# person or carries a clear sentiment. This is what makes canned lines feel personal.
HISTORY = {
    "kindness": ["I've not forgotten your kindness, {other}.",
                 "That good turn of yours still warms me, {other}.",
                 "You did right by me once, {other}. I remember."],
    "debt": ["I still owe you for that, {other}.",
             "You stood by me when it counted, {other}.",
             "Don't think I've forgotten what you did for me, {other}."],
    "quarrel": ["We've had our words, {other}. Let's leave them buried.",
                "I've a long memory, {other}. Mind that.",
                "You and I aren't square yet, {other}."],
    "familiar": ["Feels like we're always crossing paths, {other}.",
                 "You again, {other} - small village.",
                 "Can't turn a corner without you, {other}. Not that I mind."],
}
_MEM_KEYS = [
    ("kindness", ("gift", "gave", "kind", "shared", "generous", "thanked")),
    ("debt", ("helped", "aided", "saved", "stood by", "carried", "mended", "healed")),
    ("quarrel", ("argued", "angry", "insult", "stole", "wronged", "cheated", "struck", "threatened")),
]

# --- generative grammar: recombine fragments into fresh, coherent chatter -----
# Symbols reference each other with #symbol#. _expand() resolves them recursively.
GRAMMAR = {
    "smalltalk": ["#weather#", "#ache#", "#village_talk#", "#gripe#", "#hope#", "#observe#"],

    "weather": ["#sky# #weather_tail#"],
    "sky": ["Clouds are gathering", "Sky's clear for once", "Wind's turned cold",
            "Looks like rain", "Sun's out, rare enough", "Frost on the ground this morning"],
    "weather_tail": ["over the fields.", "these past days.",
                     "- mark my words, the weather's turning.", ". Won't last, I'd wager."],

    "ache": ["#body# #ache_tail#"],
    "body": ["My back", "These old knees", "My hands", "This shoulder of mine"],
    "ache_tail": ["aches something fierce.", "isn't what it was.",
                  "tells me a storm's coming.", "won't let me sleep."],

    "village_talk": ["Heard #rumor_subj# #rumor_tail#", "They're saying #rumor_subj# #rumor_tail#"],
    "rumor_subj": ["the roads north", "the miller", "the harvest",
                   "the gate watch", "prices at market", "the old well"],
    "rumor_tail": ["are worth watching.", "again - who's to say.",
                   ", if you believe it.", ". Small village, big mouths."],

    "gripe": ["#gripe_subj# #gripe_tail#"],
    "gripe_subj": ["Prices", "The work", "This weather", "The young ones today"],
    "gripe_tail": ["never let up.", "creep up every season.",
                   "will be the end of me.", "test a soul's patience."],

    "hope": ["Long as #hope_subj#, I'll not complain.", "If #hope_subj#, we'll manage well enough."],
    "hope_subj": ["the roof holds", "the well stays full", "the crop comes in",
                  "the cold breaks soon", "the roads stay open"],

    "observe": ["Quiet day. #quiet_tail#", "Busy about the village today. #busy_tail#"],
    "quiet_tail": ["Suits me fine.", "Too quiet, if you ask me.", "I'll take it."],
    "busy_tail": ["No rest for any of us.", "Feels like a festival's coming.",
                  "Everyone's got somewhere to be."],
}


def _expand(sym, rng, depth=0):
    """Resolve a grammar symbol into a concrete string, recursively."""
    if depth > 8 or sym not in GRAMMAR:
        return sym
    choice = rng.choice(GRAMMAR[sym])
    return re.sub(r"#(\w+)#", lambda m: _expand(m.group(1), rng, depth + 1), choice)


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


def _memories(prompt):
    """Recent memories are embedded as 'Recent memories: [text] [text]. Say one line'."""
    m = re.search(r"[Rr]ecent memories:\s*(.+?)(?:\.\s*Say one line|$)", prompt)
    if not m:
        return []
    body = m.group(1)
    if body.strip().lower().startswith("none"):
        return []
    return [t.strip() for t in re.findall(r"\[(.*?)\]", body)]


def _history_line(mems, other, mood, rng):
    """A shared-history line if a memory carries clear sentiment or names the other."""
    if not mems:
        return ""
    blob = " ".join(mems).lower()
    for cat, keys in _MEM_KEYS:
        if any(k in blob for k in keys):
            if cat == "quarrel" and mood != "cold":
                continue
            if cat in ("kindness", "debt") and mood == "cold":
                continue
            return rng.choice(HISTORY[cat])
    # otherwise, if a memory clearly involves the other person, a "familiar" line
    if other and other != "friend" and other.lower() in blob:
        return rng.choice(HISTORY["familiar"])
    return ""


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
    of the situation that carry meaning (where you are, who you're talking to, a
    death on your mind, your shared history with them) so replies feel considered
    rather than canned. Small talk is grammar-generated for variety."""
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
    mems = _memories(prompt)

    cats = [("greet", 2), ("mood", 2), ("small", 3)]
    if place in PLACE:
        cats.append(("place", 4))
    if role in TO_ROLE:
        cats.append(("role", 3))
    if _history_line(mems, other, mood, rng):
        cats.append(("history", 3))   # personal callbacks when we share history
    total = sum(w for _, w in cats)
    pick, upto, chosen = rng.random() * total, 0, "small"
    for c, w in cats:
        upto += w
        if pick <= upto:
            chosen = c
            break

    if chosen == "greet":
        line = rng.choice(GREET.get(pod, []) + GREET["any"])
    elif chosen == "mood":
        line = rng.choice(WARM if mood == "warm" else COLD if mood == "cold" else NEUTRAL)
    elif chosen == "place":
        line = rng.choice(PLACE[place])
    elif chosen == "role":
        line = rng.choice(TO_ROLE[role])
    elif chosen == "history":
        line = _history_line(mems, other, mood, rng)
    else:
        # grammar-generated small talk (occasionally fall back to the legacy pool)
        line = _expand("smalltalk", rng) if rng.random() < 0.85 else rng.choice(SMALLTALK)
    return _fmt(line, other, subject, place_name, role)
