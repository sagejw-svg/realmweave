"""Attributes, skills, and the CharacterSheet shared by agents and players.

D&D-inspired but original: six attributes and a catalog of 1-100 skills, each
tied to a governing attribute and grouped into a domain (which also organizes
quests). Progression is use-based with diminishing returns, so competence
emerges from what a character actually does. Character sheets serialize cleanly
for save/load.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple

from .checks import check, CheckResult, Outcome

ATTRIBUTES = ["Might", "Agility", "Endurance", "Intellect", "Wits", "Presence"]
DOMAINS = ["Combat", "Craft", "Trade", "Social", "Exploration", "Arcana", "Survival", "Faith"]
UNTRAINED = 10           # default value for a skill a character has never used
DEFAULT_ATTRIBUTE = 50

# skill -> (governing attribute, domain)
SKILL_CATALOG: Dict[str, Tuple[str, str]] = {
    "Blades": ("Might", "Combat"),
    "Archery": ("Agility", "Combat"),
    "Tactics": ("Intellect", "Combat"),
    "Intimidation": ("Presence", "Combat"),
    "Athletics": ("Might", "Exploration"),
    "Stealth": ("Agility", "Exploration"),
    "Perception": ("Wits", "Exploration"),
    "Lockpicking": ("Agility", "Exploration"),
    "Streetwise": ("Wits", "Social"),
    "Persuasion": ("Presence", "Social"),
    "Insight": ("Wits", "Social"),
    "Bargaining": ("Presence", "Trade"),
    "Appraisal": ("Intellect", "Trade"),
    "Smithing": ("Might", "Craft"),
    "Cooking": ("Endurance", "Craft"),
    "Brewing": ("Endurance", "Craft"),
    "Herbalism": ("Intellect", "Craft"),
    "Farming": ("Endurance", "Survival"),
    "Mining": ("Might", "Survival"),
    "Survival": ("Endurance", "Survival"),
    "Riding": ("Agility", "Survival"),
    "AnimalHandling": ("Presence", "Survival"),
    "Medicine": ("Intellect", "Survival"),
    "Arcana": ("Intellect", "Arcana"),
    "Faith": ("Presence", "Faith"),
}

# how quickly skills improve through use (higher = faster). Diminishing returns
# are applied on top of this so mastery is slow.
TRAIN_RATE = 0.15

_QUALITY_ADJ = {
    Outcome.CRIT_SUCCESS: 20,
    Outcome.SUCCESS: 6,
    Outcome.PARTIAL: -8,
    Outcome.FAILURE: -22,
    Outcome.FUMBLE: -38,
}


@dataclass
class CharacterSheet:
    attributes: Dict[str, int] = field(default_factory=lambda: {a: DEFAULT_ATTRIBUTE for a in ATTRIBUTES})
    skills: Dict[str, int] = field(default_factory=dict)

    # ---- lookups -------------------------------------------------------
    def skill(self, name: str) -> int:
        return self.skills.get(name, UNTRAINED)

    def attribute(self, name: str) -> int:
        return self.attributes.get(name, DEFAULT_ATTRIBUTE)

    def attribute_mod(self, name: str) -> int:
        """A small +/- from the governing attribute (range about -5..+5)."""
        return (self.attribute(name) - DEFAULT_ATTRIBUTE) // 10

    def effective(self, name: str, mod: int = 0) -> int:
        attr = SKILL_CATALOG.get(name, ("Wits", "Social"))[0]
        return self.skill(name) + self.attribute_mod(attr) + mod

    # ---- actions -------------------------------------------------------
    def check(self, name: str, rng, mod: int = 0, advantage: int = 0) -> CheckResult:
        return check(self.effective(name, mod), rng, advantage)

    def train(self, name: str, rng, amount: int = 1) -> None:
        """Use-based improvement with diminishing returns near mastery."""
        cur = self.skill(name)
        chance = TRAIN_RATE * (100 - cur) / 100.0
        if rng.random() < chance:
            self.skills[name] = min(100, cur + amount)

    def craft(self, name: str, rng):
        """Resolve a crafting action: returns (quality 1-100, CheckResult) and
        trains the skill through use."""
        res = self.check(name, rng)
        base = self.skill(name)
        quality = base + _QUALITY_ADJ[res.outcome] + rng.randint(-5, 5)
        quality = max(1, min(100, int(quality)))
        self.train(name, rng)
        return quality, res

    # ---- emergent identity --------------------------------------------
    def domain_scores(self) -> Dict[str, int]:
        scores = {d: 0 for d in DOMAINS}
        for name, value in self.skills.items():
            dom = SKILL_CATALOG.get(name, (None, None))[1]
            if dom:
                scores[dom] += value
        return scores

    def dominant_domain(self) -> str:
        scores = self.domain_scores()
        return max(scores, key=scores.get) if any(scores.values()) else "Survival"

    def emergent_class(self) -> str:
        return _CLASS_BY_DOMAIN.get(self.dominant_domain(), "Commoner")

    def top_skills(self, n: int = 3):
        return sorted(self.skills.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def summary(self) -> str:
        tops = ", ".join(f"{k} {v}" for k, v in self.top_skills(3))
        return f"{self.emergent_class()} ({tops})" if tops else self.emergent_class()

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        return {"attributes": dict(self.attributes), "skills": dict(self.skills)}

    def load_dict(self, data: dict) -> None:
        if "attributes" in data:
            self.attributes.update({k: int(v) for k, v in data["attributes"].items()})
        self.skills = {k: int(v) for k, v in data.get("skills", {}).items()}

    @classmethod
    def from_dict(cls, data: dict) -> "CharacterSheet":
        sheet = cls()
        sheet.load_dict(data)
        return sheet


_CLASS_BY_DOMAIN = {
    "Combat": "Warrior",
    "Craft": "Artisan",
    "Trade": "Merchant",
    "Social": "Diplomat",
    "Exploration": "Scout",
    "Arcana": "Mage",
    "Survival": "Woodsman",
    "Faith": "Devout",
}


# ---- role-based seeding ------------------------------------------------
# Starting sheets for the authored cast. Attribute overrides + trained skills;
# anything unlisted defaults (attributes 50, skills untrained at 10).
_ROLE_SEEDS = {
    "Tavernkeeper": ({"Presence": 62, "Intellect": 55, "Endurance": 55},
                     {"Bargaining": 70, "Cooking": 66, "Brewing": 62, "Persuasion": 58, "Insight": 52, "Blades": 25}),
    "Stable hand": ({"Agility": 62, "Endurance": 58},
                    {"Riding": 68, "AnimalHandling": 72, "Athletics": 55, "Blades": 30, "Survival": 40}),
    "Blacksmith": ({"Might": 70, "Endurance": 66},
                   {"Smithing": 82, "Athletics": 50, "Appraisal": 45, "Blades": 38, "Intimidation": 30}),
    "Street sweeper": ({"Wits": 60},
                       {"Perception": 72, "Streetwise": 62, "Stealth": 46, "Insight": 55}),
    "Farmer": ({"Endurance": 64, "Might": 55},
               {"Farming": 78, "Survival": 56, "AnimalHandling": 50, "Cooking": 42, "Appraisal": 40}),
    "Gate guard": ({"Might": 60, "Endurance": 62},
                   {"Blades": 68, "Tactics": 56, "Perception": 62, "Athletics": 58, "Intimidation": 55}),
    "Errand child": ({"Agility": 56, "Endurance": 45},
                     {"Athletics": 58, "Stealth": 55, "Streetwise": 58, "Perception": 50}),
    "Herbalist": ({"Intellect": 64, "Wits": 60},
                  {"Herbalism": 78, "Medicine": 70, "Arcana": 55, "Appraisal": 50, "Insight": 60, "Faith": 45}),
    "Miner": ({"Might": 68, "Endurance": 66},
              {"Mining": 80, "Athletics": 56, "Appraisal": 48, "Survival": 46, "Smithing": 35, "Intimidation": 30}),
}


def role_sheet(role: str) -> CharacterSheet:
    attrs = {a: DEFAULT_ATTRIBUTE for a in ATTRIBUTES}
    skills: Dict[str, int] = {}
    seed = _ROLE_SEEDS.get(role)
    if seed:
        attrs.update(seed[0])
        skills.update(seed[1])
    return CharacterSheet(attributes=attrs, skills=skills)
