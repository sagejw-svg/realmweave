# Character Systems: Combat, Equipment, and Magic (Proposal)

Status: **built** (phases 1-4 landed). This complements `DESIGN.md` section 4.1
(character and skill system) and `PROJECT_PLAN.md` section 4. It answers a
standing question: does Realmweave have spells, player stats, armor, and combat,
and if not, how do we add them without turning a living-world simulation into a
combat grinder.

Implementation status (save format now v15):

- Phase 1 harm/wounds: **done** (rules/harm.py; wounds feed health and mortality).
- Phase 2 abstract combat: **done** (rules/combat.py, sim.resolve_combat; wired
  into justice so dangerous perps resist arrest).
- Phase 3 equipment/armor: **done** (rules/equipment.py; weapon offense, armor
  wound-mitigation; the guard is seeded with gear).
- Phase 4 magic: **done** (rules/magic.py; a per-agent focus pool, spells
  mend/bolt/ward/frighten). Note: Faith casts from personal focus, not the global
  divine favor pool (which stays the player-god's suggestion budget), a small
  deviation from section 6 kept for system separation.

## 1. Where we are today

The character foundation is already in place and solid:

- One `CharacterSheet` (rules/skills.py) shared by NPCs and players: six
  attributes and about 25 skills on a 1-100 scale, governing-attribute
  modifiers, use-based progression with diminishing returns.
- A clean d100 resolver (rules/checks.py): roll-under with degrees of success
  (crit / success / partial / failure / fumble), advantage/disadvantage, and
  opposed checks that compare margins. All pure and deterministic given the RNG.
- Health as a 0-1 value (agents.py) that drains only from sustained
  need-starvation and a small frailty-weighted illness chance (sim.py
  `_mortality`). Death is permanent and remembered.
- Armor and weapons exist only as *tradeable goods* (economy/goods.py): a smith
  forges "a piece of armor" as an `Item` with quality and coin value. It cannot
  be worn and confers nothing.
- Combat *skills* (Blades, Archery, Tactics, Intimidation) and a fighters' guild
  exist, but they only feed quest matching, guild rank, and one opposed
  Blades-vs-Athletics check when the guard catches a wanted NPC (justice.py
  `_resolve_capture`). That capture is abstract and non-violent.
- Arcana and Faith are skills with emergent class labels (Mage, Devout) but no
  casting, resource, or effect behind them.

So: stats exist and are good. Armor, weapons, spells, and combat do not exist as
mechanics. The three requested systems are interdependent, because armor only
matters if there is harm to prevent, and offensive spells and weapons need
something to act on. This proposal therefore treats them as one coherent layer.

## 2. Design stance: light and abstract, emergence first

Realmweave is a living world, not a battle game. The setting doc
(`PROJECT_PLAN.md` section 13) deliberately excludes systemic atrocity and frames
discovery around exchange, not conquest. Combat here is the exception in a life,
not the loop. The guiding rules:

- **Rare and consequential.** Most days no one fights. When violence happens it
  is short, costly, and remembered, not a repeated activity.
- **Resolved by checks, not HP attrition.** No tactical turn grind, no hit-point
  bars ticking down blow by blow. An exchange is one or a few opposed checks that
  produce a *narrative outcome*: unharmed, shaken, wounded, downed, fled, or
  subdued.
- **Non-lethal by default.** Ordinary conflict ends in someone yielding, fleeing,
  or being subdued. Death is reserved for extreme results (a fumble against a
  lethal threat) or explicitly lethal contexts, so the world does not quietly
  depopulate.
- **Deterministic and stub-safe.** Every outcome is code-resolved from the RNG,
  reproducible with a seed, and runs with no GPU. The LLM only narrates and
  reacts; it never decides who wins.
- **Feeds the systems we already have.** Wounds feed health and mortality; fear
  and grief feed memory and reputation; a bandit on the road feeds quests.

## 3. Harm and wounds (the foundation)

Add a small **harm model** so that fights, accidents, hazards, and later spells
have a shared currency that is not a hit-point bar.

- A new `wounds` field on the agent (list of `Wound`), each with a severity
  (graze, hurt, grave) and a source note. Wounds do two things: they apply a
  situational penalty to physical checks (a grave wound is a stiff `-` modifier),
  and they pull on the existing `health` value so an untreated grave wound can
  contribute to mortality, reusing the current `_mortality` path rather than
  inventing a second death system.
- Wounds heal over time (rest, food) and faster with care: a Medicine or
  Herbalism check by a healer, or a Faith mend spell (section 6). Elda the
  herbalist becomes mechanically useful, not just flavor.
- Severity is set by the *degree* of the resolving check, not a damage roll. This
  keeps everything on the one d100 spine: a clean win grazes, a partial hurts, a
  bad loss leaves a grave wound.

This foundation is deliberately buildable and testable on its own, before any
equipment or magic.

## 4. Abstract combat resolution

A confrontation is an **opposed skill contest** using the existing `opposed()`
helper, not a new subsystem.

- Attacker rolls an offense skill (Blades / Archery / Intimidation / a spell
  skill) against the defender's best defense (Athletics to evade, Blades to
  parry, Tactics to out-position, or a ward spell). Equipment and wounds apply as
  modifiers and advantage/disadvantage.
- The *margin and degree* map to an outcome:

  | Result | Outcome |
  |--------|---------|
  | Attacker crit / large margin | Defender downed or grave wound |
  | Attacker success | Defender hurt, or forced to yield / flee |
  | Partial / tie | A graze and a standoff; positions shift |
  | Defender wins | Attack turns aside; attacker may be exposed next exchange |
  | Attacker fumble | Attacker stumbles, drops guard or weapon |

- Most encounters resolve in one to three exchanges, then someone flees, yields,
  or is subdued. Intent matters: a guard subdues, a bandit robs, a predator
  wounds. Lethal intent is a flag on the encounter, not the default.
- **Reuse, do not replace, justice.** `_resolve_capture` becomes one caller of
  this shared resolver: a desperate wanted NPC can now resist and wound a pursuer
  rather than always submitting, which makes the fighters' guild deputies matter.

## 5. Equipment and armor (giving the existing good a purpose)

Turn the armor and weapon *goods* into *worn gear* that modifies checks. This is
the smallest change that makes the current economy item meaningful.

- Add an `equipment` mapping on the agent with a few slots: **weapon**, **armor**,
  and one **trinket** (room for later focuses/holy symbols). Equipping an `Item`
  from inventory fills a slot.
- **Weapons** add an offense modifier and flavor which skill applies (a blade
  keys Blades, a bow keys Archery). Quality (the existing 1-100 on `Item`) scales
  the modifier, so a masterwork blade is genuinely better. This connects to the
  milestone perk already noted in `DESIGN.md` 4.1 ("Smithing 75 unlocks
  masterwork armor").
- **Armor** does not soak hit points; it **reduces wound severity** by one step
  on a hit (a grave becomes a hurt, a hurt becomes a graze) with a chance scaled
  by quality, and may carry a small mobility penalty so heavy armor trades evasion
  for protection. This keeps armor valuable without introducing a damage-race.
- Gear is authored on some NPCs (the guard has a decent blade and mail) and
  bought, looted, or crafted by others, so equipment differences read as status
  and history. The smith now forges gear people actually want to wear.

## 6. Magic: making Arcana and Faith real

Give the two dormant skills a real, bounded system that fits a low-industrial,
early-history tone. Magic is uncommon, costly, and mostly practical.

- **Two traditions, two resources.**
  - **Arcana** draws on a personal **focus** pool (a small reservoir keyed to
    Intellect/Endurance that refills with rest). Spend focus to cast; run dry and
    you cannot.
  - **Faith** draws on the existing **divine favor** resource (divine/), so
    piety and the god system already in place become the fuel. This reuses a
    system rather than adding a parallel one.
- **Casting is a check.** An Arcana or Faith check sets the effect's strength via
  the same degrees of success. A fumble backfires (lost focus, a scorch, a
  fright), keeping risk real.
- **A small, legible catalog** (utility-leaning, a little combat):

  | Spell | Tradition | Effect |
  |-------|-----------|--------|
  | Mend | Faith / Arcana | Heal a wound a step; the healer's answer to a blade |
  | Ward | Arcana | Temporary defense bonus for an exchange or two |
  | Kindle / Light | Arcana | Practical utility: fire, light at night (ties to perception) |
  | Frighten | Faith / Arcana | Force a foe to yield or flee without a killing blow |
  | Foresight | Faith | Brief advantage on a coming check |
  | Blight / Bolt | Arcana | The one offensive option: a wound at range, expensive |

- **Emergent casters.** An agent with high Arcana or Faith and the right
  personality can form a goal to learn or use magic, and the emergent class
  labels Mage and Devout finally mean something. Players with the skill cast
  through the same code path.
- Effects resolve in code; the LLM only narrates ("she traces a sign and the cut
  closes"). Deterministic and stub-safe like everything else.

## 7. Player-facing stats

Players already share the `CharacterSheet`, so "player stats" is mostly about
*surfacing and using* what exists: expose the sheet, wounds, equipment, focus,
and known spells over the WebSocket snapshot and the subjective "through their
eyes" view, and let player actions (a swing, a cast, equipping gear) route
through the same authoritative resolvers as NPCs. No separate player rules.

## 8. Integration and persistence

- **Save format.** Adds `wounds`, `equipment`, `focus`, and `known_spells` to the
  agent schema. Bump `SAVE_VERSION` (currently 12) to 13 with a migration that
  defaults these to empty/none, so existing saves load unchanged. New raw
  materials or spell reagents, if any, follow the pattern mining used.
- **Determinism and tests.** Each piece lands with unit tests on the deterministic
  stub path: wound severity from check degree, armor severity reduction, the
  combat outcome table, focus spend/refill, and each spell's effect. Mirrors the
  existing test suites (test_rules, test_supply, test_mining).
- **LLM tiers.** Combat and casting are code; only the narration and emotional
  fallout (fear, grief, a grudge remembered) touch the dialogue/narrative tiers,
  keeping GPU cost bounded per the local-first strategy.
- **Client.** The Godot client and the web map key off the same snapshot, so
  showing a wound state or a drawn weapon is a rendering add, not a protocol
  redesign.

## 9. What we deliberately do not build

- No hit-point attrition or tactical turn grid. Outcomes are narrative, from
  checks.
- No systemic violence as a path to wealth or power. Aggression stays costly and
  reputationally damaging, consistent with `PROJECT_PLAN.md` section 13.
- No always-lethal combat. Death remains rare and meaningful.
- No sprawling spellbook. A short, legible catalog that a person and an LLM can
  both reason about.

## 10. Suggested sequencing

Each phase is independently useful and testable:

1. **Harm and wounds** (section 3): the shared currency, wired into health and
   mortality. Smallest foundation.
2. **Abstract combat** (section 4): the opposed-check resolver and outcome table;
   refit justice capture to use it.
3. **Equipment and armor** (section 5): worn gear as modifiers; gives the smith's
   armor a real purpose.
4. **Magic** (section 6): focus and favor resources, casting checks, the spell
   catalog; Mend closes the loop with wounds.

A reasonable first slice is phases 1 and 2 together (a testable harm-and-combat
core), then equipment, then magic. Open question for discussion: whether the very
first slice should instead lead with equipment as pure stat modifiers (no combat
yet), since that touches the least and immediately makes the existing armor good
useful.
