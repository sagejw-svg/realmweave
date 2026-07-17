# Realmweave Project Plan

### From a living village to seeing the world through an AI's eyes

This plan carries Realmweave from its current state (an autonomous village you
can talk to) all the way to the capstone: a persistent, D&D-inspired living
world of agents who set their own goals, and the ability to drop into any of
them and experience the world through their eyes.

**How to read this plan.** Sections marked *Built* already exist in the repo.
*Proposed* marks design not yet implemented; where a mechanic is a genuine design
choice rather than a settled fact, it is called out so we can revisit it. Effort
estimates are rough order-of-magnitude for a solo/small-team pace and are meant
for sequencing, not commitments.

---

## 1. Locked decisions

These were decided up front and shape everything below.

| Decision | Choice | Why |
|----------|--------|-----|
| Ruleset | D&D-inspired **custom** system, skills 1-100 | Clean for MIT + a commercial Steam release; no third-party rights risk. We borrow concepts (checks, advantage, ability scores, classes) but use our own numbers and names. |
| Divine influence | **Soft suggestions the AI may refuse** | Matches the vision: the god can whisper "sell the shop, do something bigger," and the AI weighs it against its own personality and goals, and may ignore it. |
| Deliverable | `PROJECT_PLAN.md` in the repo | Version-controlled beside `DESIGN.md`, updated as we build. |
| Engine split | Godot 4 client + Python authority | Unchanged from `DESIGN.md`; the network seam is also the multiplayer seam. |
| LLMs | Local-first (Ollama) + importance-tiered router | Runs on the RTX 5070 (12 GB); optional API tier for rare key moments. |

---

## 2. Current state (baseline)

*Built and pushed (commits `8a56831`, `4595d7d`):*

- Authoritative Python sim: world clock, 13-location village (Oakhollow), 8
  autonomous agents with schedules, needs (energy/hunger/thirst/social),
  relationships, and permanent death that others remember.
- Per-agent memory stream with recency + importance + relevance retrieval
  (RAG-lite), embeddings optional via Ollama.
- Multi-model LLM router (reflex / dialogue / narrative tiers) with a GPU-free
  deterministic stub fallback.
- WebSocket protocol and a Godot 4 2D client (top-down view, clock, speech
  bubbles, event log, WASD).
- Player-to-NPC dialogue: speak to the nearest villager, they remember it and
  reply in character.
- Versioned JSON save/load with server auto-save and resume.

Everything below builds on this spine. The agents already have memory,
personality briefs, and needs; the plan mostly adds *cognition* (goals and
plans), *rules* (skills and checks), *stakes* (economy and quests), and
*presence* (perception and the first-person view).

---

## 3. Target architecture

New subsystems layered onto the existing sim. Arrows show data flow into an
agent's decision each tick.

```
                         +----------------------------+
                         |      Agent decision         |
   needs ─────────────►  |  (utility-based selection)  |
   schedule ──────────►  |                             |
   goals/plans ───────►  |  picks the highest-utility  | ─► action ─► world
   perception ────────►  |  action given who they are  |        │
   divine suggestions ►  |  and what they perceive     |        │
   personality/skills ►  +----------------------------+        │
        ▲                                                       │
        │                                                       ▼
   memory stream  ◄──────────  observations, outcomes, reflections
```

New modules (proposed) alongside the current `realmweave/` package:

| Module | Responsibility |
|--------|----------------|
| `rules/` | Character sheet, attributes, skills (1-100), checks, advantage, progression. |
| `cognition/` | Goal generation, planning, utility scoring, personality traits. |
| `economy/` | Money, inventory, goods, production, pricing, structures (shops). |
| `quests/` | Quest data model, domains, generation, tracking, rewards; agents opting out. |
| `divine/` | Suggestion injection, disposition weighting, the AI's accept/refuse logic. |
| `perception/` | What an agent can see/hear/know; feeds the decision and the POV view. |

---

## 4. Core systems

### 4.1 Character and skill system (D&D-inspired, 1-100)  *Proposed*

Every agent and player character shares one character sheet.

**Attributes (1-100).** Six core attributes, our own names to stay clean of
third-party rights: **Might, Agility, Endurance, Intellect, Wits, Presence.**
These change slowly (training, age, injury, magic).

**Skills (1-100).** Skills are the granular, frequently-used values. Each skill
is tied to a governing attribute and grouped into a **domain** (see quests).
Examples: Blades, Archery, Smithing, Bargaining, Persuasion, Herbalism, Stealth,
Arcana, Farming, Lockpicking, Cooking, Riding.

**Check resolution.** Roll-under d100 with degrees of success:

| Roll vs (Skill + situational modifier) | Result |
|----------------------------------------|--------|
| Roll <= (skill + mod) / 5 | Critical success |
| Roll <= (skill + mod) | Success |
| Roll <= (skill + mod) + 20 | Partial / success at a cost |
| Otherwise | Failure |
| Roll 96-100 | Fumble |

*Design note:* roll-under d100 makes a skill value read intuitively as a percent
chance, which is easy for both the player and the LLM to reason about ("Bram's
Bargaining is 72, he'll usually win a haggle"). **Advantage/disadvantage:** roll
twice, take the better/worse. Opposed checks compare degrees of success.

**Progression: use-based, not just XP.** Skills improve through use (a smith who
forges daily raises Smithing), with diminishing returns at high values. This
suits a living world where agents "make their own way," because competence
emerges from what an agent actually chooses to do, not from a quest treadmill.
Optional milestone perks unlock at 25/50/75/100 (e.g., Smithing 75 unlocks
masterwork armor). Players can also gain XP from quests; both paths coexist.

**Classes/archetypes** are soft: an agent's dominant domains define an emergent
"class" label (a villager who maxes Blades + Tactics reads as a Warrior) rather
than a rigid class chosen at creation.

**LLM integration.** The character sheet is summarized into the agent's decision
prompt ("You are a skilled smith (Smithing 78) but a poor liar (Deception 20)"),
so behavior and dialogue stay consistent with mechanics. Checks are resolved by
code, not the LLM, so outcomes are fair and deterministic given the dice.

### 4.2 Agent cognition and autonomy  *Proposed*

This is the heart of "AI makes its own way." Today agents follow schedules; this
upgrades them to goal-driven planners in the generative-agent tradition.

**Layers:**

1. **Personality** (stable): traits on axes such as ambition, sociability,
   caution, greed, loyalty, curiosity. Seeded per agent, drift slowly.
2. **Needs** (fast): existing energy/hunger/thirst/social, plus new ones
   (wealth, safety, belonging, purpose).
3. **Goals** (medium): generated from unmet needs + personality + memory. Example:
   a high-ambition, high-greed smith forms the goal "open an armor shop."
4. **Plans** (short): a goal is decomposed into steps (gather coin, buy a
   storefront, stock inventory, set prices, attract customers). Steps become the
   agent's activities, replacing rigid schedules with schedules-that-serve-goals.
5. **Utility selection** (per tick): score candidate actions by how much they
   advance active goals and satisfy needs, weighted by personality; pick the
   best. Cheap and deterministic; the LLM is only invoked for dialogue,
   reflection, and occasional novel goal generation, keeping GPU cost bounded.

**Reflection** (already partly present) periodically summarizes recent memories
into higher-level beliefs ("the north road is dangerous"; "the god favors me"),
which then influence future goals.

*Design note:* keeping selection in code and reserving the LLM for language and
novelty is what makes many autonomous agents affordable on one 12 GB GPU.

### 4.3 Emergent livelihoods and economy  *Proposed*

So an agent can, of its own accord, build a shop and sell nothing but armor.

- **Money and inventory** on every agent; goods have base value, quality, and
  provenance.
- **Production**: professions convert time + skill + materials into goods (a
  smith turns iron + Smithing checks into armor of a quality set by the check).
- **Structures**: agents can acquire or build a plot and designate it (shop,
  smithy, farm). A shop has stock, prices, and hours; it becomes a location
  other agents and players can visit and buy from.
- **Pricing and trade**: agents set prices from cost + a margin adjusted by
  personality (greedy = higher) and Bargaining checks at point of sale.
- **Market feedback**: unsold stock, competition, and demand feed back into the
  agent's needs (wealth/purpose), which can spawn new goals ("prices too high,
  no customers, lower them" or "armor isn't selling, diversify").

This closes the loop: the shopkeeper who "does nothing but sell armor" is a
stable outcome, but market pressure and the god's nudges can perturb it.

### 4.4 Quests across domains  *Proposed*

**Domains** organize both skills and quests: Combat, Craft, Trade, Social,
Exploration, Arcana, Survival, Faith. A quest is a target world-state with
triggers, steps, and rewards.

- **Authored quests**: hand-written arcs seeded into the world.
- **Emergent quests**: generated from world tension (a bandit camp on the north
  road becomes a Combat quest; a failing harvest becomes a Survival/Trade quest).
- **Cross-domain**: quests can span domains (escort a trade caravan = Trade +
  Combat + Social).
- **Players** can discover, accept, and complete quests for rewards and skill/XP.
- **Agents can ignore quests entirely.** Quests are opportunities in the world,
  not rails. An agent pursues a quest only if it serves the agent's own goals
  and personality; a content shopkeeper may never touch one. This is a core
  principle, not an afterthought: the quest system offers hooks, the autonomy
  system decides whether to bite.

### 4.5 Divine influence (soft suggestions)  *Proposed*

The player is a god who can influence but not puppet.

**Mechanics:**

1. The god selects an agent and issues a **suggestion** in natural language
   ("sell the shop and seek adventure").
2. The suggestion enters the agent's decision as a weighted input, not a command.
3. The agent evaluates it against **disposition toward the god** (favor/faith),
   personality (a cautious, content agent resists; an ambitious or devout one
   leans in), and current goals.
4. The agent **accepts, partially accepts, bargains, or refuses**, and reacts in
   character ("The gods ask much of a simple smith..."). Refusal is a valid,
   first-class outcome.
5. Outcomes feed back: heeded suggestions that go well raise faith; ignored or
   punished ones shift disposition (resentment, zealotry, doubt).

**Authoring at creation (a god power, distinct from suggestions).** The god can
seed a character's **name, background, and personality** when they enter the
world. This is authorship of a starting point, not a script for their actions.
A seeded background is a memory and a set of tendencies, never a leash: the
character can diverge from it (see 4.7). The same authoring applies whether the
god is shaping an AI agent or setting up a character to later observe or possess.

*Design note (tunable):* a **favor** resource can gate how often or how strongly
the god nudges, so influence feels earned. We deliberately chose soft influence
over god-mode; a rare hard "decree" could be added later as a costly exception if
desired, but it is out of scope for now.

### 4.6 Perception and the "through their eyes" view  *Proposed*

Two things must exist before a first-person view is meaningful: a **perception
model** (agents should only know what they could plausibly perceive) and a way to
**render one agent's subjective world**.

**Perception model.** Each agent has senses with ranges and a knowledge set.
Sight is limited by distance, line of sight, and light (night matters); hearing
by distance. An agent only forms memories of what it perceives. This also fixes
"omniscient NPC" immersion breaks and is reusable for stealth and information
flow (rumors spread because someone *saw* something).

**The view itself.** Because the main game is 2D, "through their eyes" is a
first-person subjective panel rather than a full 3D FPS:

- **Sensory feed**: what this agent currently sees and hears, rendered as a
  framed first-person scene (a 2.5D or stylized 2D forward view of the immediate
  surroundings, or at minimum a focused "what's in front of me" panel).
- **Inner life**: a live stream of the agent's thoughts, current goal and plan
  step, active needs, mood, and the memories surfacing right now.
- **Relationships lens**: how this agent feels about whoever is in view.
- **Possess vs observe**: *observe* rides along passively (the default, safe for
  autonomy); *possess* lets the god briefly act as the agent (optional, costly in
  favor, with consequences to the agent's sense of self and memory).

*Design note:* the honest scope choice is a strong **first-person observation
mode** (subjective panel + inner monologue + limited forward view) before any
full 3D embodiment. Full 3D per-agent FPS is a large art/engine effort and is
called out as a stretch goal, not a Phase gate.

### 4.7 Identity, reputation, and consequences  *Proposed*

Two linked ideas: characters own their identity, and actions have real teeth.

**Authored, not scripted.** As in 4.5, the god seeds name, background, and
personality, but that describes who a character *starts as*, not what they will
do. A character can diverge from their origin. Example: someone the god names
**Jon Doe**, with a bandit-clan past, may choose to go by **Sam Smith** and try
to turn over a new leaf. The background is a starting condition and a memory, not
a leash. This holds for the human's own character too.

**Identity and aliases.** A character has a true identity plus optional aliases
and a public reputation that others know them by. Reinvention is a real arc:
shedding a name, outrunning a past, being recognized by someone who knew the old
you. Whether an alias holds depends on who has seen your face (ties to
perception).

**Reputation and factions.** Reputation is tracked per faction/community (the
village, the guard, bandit clans, temples) on axes such as trust, fear, and
renown. Deeds shift it, and witnesses matter: a crime no one perceives does not
immediately cost reputation, though it can surface later through evidence or
confession.

**Crime and justice.** Evil is fully playable, and it has real consequences.
Theft, assault, and murder register as crimes when perceived or later
discovered. Consequences scale with severity and notoriety: victims and
witnesses remember, the guard investigates, bounties are posted, and both NPCs
and autonomous AI agents will hunt a wanted character. This applies **equally to
the human's character and to AI agents** - no double standard. An armed robbery
in the square gets you chased; a quiet theft might go unnoticed until the goods
are recognized.

**Redemption.** Turning over a new leaf is supported. Reputation can be rebuilt
through deeds, restitution, the passage of time, or moving to a community that
does not know you, so the Sam Smith arc can actually pay off rather than being
cosmetic.

*Design note:* fair crime detection depends on the perception model, which is
why this lands right after Phase 6. Severity tiers, statutes of limitation,
bounty economics, and how doggedly the guard and AI pursue are all tunable knobs.

---

## 5. Phased roadmap

Each phase ends with something runnable and a clear acceptance test. Phases are
ordered so that every later capstone rests on foundations proven earlier.

| Phase | Theme | Headline outcome | Rough effort |
|-------|-------|------------------|--------------|
| 0 | Living village | Autonomous NPCs, memory, death, dialogue, save/load | **Done** |
| 1 | Rules foundation | Character sheets, 1-100 skills, checks driving outcomes | **Done** |
| 2 | Autonomy | Goals + plans + utility selection; agents pursue self-set aims | **Done** |
| 3 | Livelihoods | Economy, professions, agent-built shops | **Done** |
| 4 | Quests | Cross-domain quests; players play them; agents may ignore them | **Done** |
| 5 | Divine influence | God suggestions the AI weighs and may refuse; god-authored creation | **Done** |
| 6 | Perception | Sense-limited knowledge; foundation for POV and fair crime detection | **Done** |
| 7 | Reputation & justice | Identity/aliases, per-faction reputation, crime, bounties; the wanted are hunted | **Done** |
| 8 | Through their eyes | First-person observation mode (panel + inner life + forward view) | **Done** |
| 9 | World feel | Tilemap + sprite art, day/night, animations | **First pass** |
| 10 | Multiplayer | Hostable server, roster, interest management | **Done** |
| 11 | Release | Content tooling, performance, Steam build | ongoing |

*Phases 1-7 are backend-heavy and testable headless (fast, no GPU needed for the
logic). Phases 8-9 are client/art heavy. 9 can slip earlier if you want it to
look good sooner; it does not block the simulation work.*

> **Status honesty (read before trusting the "Done" column).** "Done" here means
> the system exists as a module and passes tests, not that its gameplay loop
> closes in a running world. An external code review (repo read, headless run, 73
> tests passing) found the architecture strong but several core loops open at the
> seams: notably the world cannot produce a natural death on its own, needs
> satisfy regardless of location, and the player has no economy verbs. The honest
> baseline is **rich Phase 2 with thin loop-closing seams**, not a finished Phase
> 10. Section 15 folds that review in as the concrete path to a polished,
> shippable game and supersedes the "next: Phase 11" framing for near-term work.

### Phase 1 - Rules foundation
- Add `rules/` : `CharacterSheet`, attributes, `Skill`, `check(skill, mod)` with
  degrees of success and advantage.
- Give every agent a sheet; seed skills from their role (Bram: high Bargaining,
  Cooking; Toft: high Smithing).
- Route existing actions through checks (a smith's output quality = Smithing
  check; a haggle = opposed Bargaining).
- **Acceptance:** headless run shows skill checks resolving actions; a smith with
  higher Smithing produces better armor on average; unit tests on the dice math.

### Phase 2 - Autonomy
- Add `cognition/` : personality traits, goal generation from needs+personality,
  simple planner (goal to steps), utility-based action selection replacing rigid
  schedule adherence (schedules become fallback behavior).
- **Acceptance:** starting from identical villages, seeds diverge, an ambitious
  agent independently forms and pursues a multi-step goal, visible in the event
  log, with no scripting.

### Phase 3 - Livelihoods
- Add `economy/` : money, inventory, goods, production, structures, pricing.
- Let an agent whose goal is "open a shop" actually acquire a plot, stock it, and
  trade; other agents/players can buy.
- **Acceptance:** an agent builds an armor shop unprompted and completes sales;
  the world persists the shop and stock across save/load.

### Phase 4 - Quests
- Add `quests/` : data model, domains, authored + emergent generation, tracking,
  rewards; player quest log in the client.
- Wire autonomy so agents evaluate quests as optional opportunities.
- **Acceptance:** a player completes a cross-domain quest for rewards; a content
  agent verifiably declines an available quest because it does not serve its
  goals.

### Phase 5 - Divine influence
- Add `divine/` : suggestion API from client to a chosen agent; disposition +
  personality weighting; accept/partial/bargain/refuse with in-character reaction;
  favor resource; feedback into disposition.
- Add **god-authored creation**: a creation UI/API to seed a character's name,
  background, and personality (which seed identity and memory, not behavior).
- **Acceptance:** the "sell the shop, do something bigger" scenario works end to
  end; the same suggestion is accepted by an ambitious agent and refused by a
  content one, each reacting in character. A god-authored background influences
  but does not dictate the agent's later choices.

### Phase 6 - Perception
- Add `perception/` : sight (range, line of sight, light), hearing; agents only
  learn what they perceive; rumor spread rides on perception.
- **Acceptance:** an event witnessed by one agent propagates as a rumor only
  through those who could perceive it or were told; unwitnessed events stay
  unknown.

### Phase 7 - Reputation and justice
- Add `reputation/` : true identity + aliases, per-faction reputation (trust,
  fear, renown), crime records tied to witnesses (from perception), bounties,
  wanted status, and pursuit behavior for NPCs and AI agents.
- Wire redemption paths (deeds, restitution, time, relocation) so reputation can
  recover.
- **Acceptance:** a character commits a witnessed theft, becomes wanted, and is
  pursued by the guard and at least one AI agent; the same crime unwitnessed
  goes undetected; an alias holds until someone who saw the deed recognizes them;
  reputation rebuilds after restitution. Applies identically to the human's
  character and AI agents.

### Phase 8 - Through their eyes  *(capstone)*
- Client: agent selection, **observe** mode (subjective panel: forward view of
  surroundings, inner-thought stream, current goal/plan, mood, surfacing
  memories, relationship lens); protocol additions to stream one agent's
  subjective state.
- Optional **possess** mode (god acts as the agent, favor cost, consequences).
- **Acceptance:** you can select any villager and watch the world unfold from
  their perspective, seeing what they see and think, including reacting to a
  divine suggestion from the inside.

### Phases 9-11
- **9 World feel:** tilemap + sprites, day/night lighting, activity animations.
- **10 Multiplayer:** hostable dedicated server, player roster, interest
  management (stream only nearby agents), authority basics, latency smoothing.
- **11 Release:** village-authoring tools, performance passes for many agents,
  Steam build and Deck check, packaging. MIT throughout.

---

## 6. Data model and persistence evolution

Save format is already versioned JSON with atomic writes. Each phase bumps
`SAVE_VERSION` and adds a migration path so old worlds keep loading:

| Phase | New persisted state |
|-------|---------------------|
| 1 | Character sheets: attributes, skills, progression. |
| 2 | Personality traits, active goals, plan steps. |
| 3 | Money, inventories, goods, structures, shop stock/prices. |
| 4 | Quest instances, progress, completions. |
| 5 | Divine favor, per-agent disposition toward the god, suggestion history; god-authored creation seeds (name/background/personality). |
| 6 | Per-agent knowledge sets (what each has perceived/been told). |
| 7 | True identity + aliases, per-faction reputation, crime records, bounties, wanted status. |

*Principle:* every new system serializes cleanly and survives a save/load, and
death remains permanent across all of it. A migration test loads a prior-version
save at each bump.

---

## 7. Performance and scaling

The constraint is the RTX 5070 (12 GB) and the goal of many concurrent agents.

- **Code-first cognition:** utility selection, checks, economy, and perception
  run in plain Python. The LLM is reserved for dialogue, reflection, and novel
  goal/quest text, tiered by importance (reflex / dialogue / narrative).
- **Level of detail:** agents near a player or in-view are fully simulated;
  distant agents run a cheaper abstract update (needs and economy tick, no LLM).
- **Async LLM + budget:** cap LLM calls per tick; queue and batch; never block
  the sim loop on generation.
- **Targets (to validate):** dozens of full-detail agents at interactive speed on
  a single 12 GB card; hundreds in abstract LOD. Numbers to be measured in Phase
  2-3, not assumed.

---

## 8. Multiplayer path (Phase 10)

The server is already authoritative and multi-client. Remaining work: a hostable
dedicated build, player accounts/roster, interest management so each client only
receives nearby agents (bandwidth and privacy of the "eyes" view), authority and
basic anti-cheat, and latency smoothing (the client already interpolates). No
architectural rewrite is expected; this is why the two-process split was chosen.

---

## 9. Licensing and legal

- **Code:** MIT, as-is.
- **Ruleset:** we build an original, D&D-*inspired* system with our own attribute
  and skill names and our own numbers. This keeps the project clear of
  third-party game-content rights and safe for a commercial Steam release.
- **SRD note (fact):** if we ever wanted to use official reference content, the
  D&D System Reference Document 5.2.1 (2025) is released under Creative Commons
  Attribution 4.0 and is irrevocable, so it is legally usable with attribution.
  We are choosing *not* to depend on it, to avoid attribution and brand-adjacency
  constraints, but it remains an option for specific mechanics if useful.
- **Assets:** all art, audio, and fonts must be original or licensed for
  commercial use; track provenance from the start (an `ASSETS.md` ledger).
- **Model licenses:** confirm the license of any bundled or recommended local
  model (e.g., Qwen, Llama) permits your distribution/commercial use; the router
  stays model-agnostic so we can swap if a license is unfriendly.
- **Trademark hygiene:** avoid "D&D," "Dungeons & Dragons," and other marks in
  the product name, store page, and marketing.

*This is general information, not legal advice; a brief IP review before a paid
release is worth it.*

---

## 10. Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Emergent worlds feel aimless | Low engagement | Authored personas, seeded goals, and quests give emergence something to push against. |
| LLM cost/latency with many agents | Sim stalls | Code-first cognition, LOD, async + per-tick LLM budget. |
| Autonomy vs playability | God feels powerless | Soft influence + favor economy tuned so nudges matter without removing agency. |
| Authored background railroads | Loses autonomy | Background seeds identity and memory only, never scripts actions; characters can reinvent (aliases, new leaf). |
| Evil/griefing feels consequence-free | Hollow stakes | Reputation & justice: witnesses, bounties, and NPC + AI pursuit; consequences scale with notoriety and apply to everyone equally. |
| First-person scope creep | Phase 8 balloons | Ship observation mode (panel + inner life + limited view) before any 3D embodiment. |
| Save-format churn | Broken worlds | Versioned saves + migration tests at every bump. |
| Model licensing surprises | Release blocker | Model-agnostic router; verify licenses early. |
| Solo-dev burnout on breadth | Stalls | Each phase is independently valuable and shippable; stop-anywhere ordering. |

---

## 11. Immediate next steps

The first concrete work items, each a small, reviewable change:

1. **Phase 1 - done and merged** (PR #1): `rules/` with `CharacterSheet`, 1-100
   skills, d100 checks, use-based progression, role seeding, and skill-driven
   crafting; save format v2 with migration; 10 unit tests.
2. **Phase 2 - done** (PR #2): `cognition/` with personality traits, goal
   generation, a template planner, and utility-based action selection. Agents now
   form and pursue their own multi-step goals; save format v3.
3. **Phase 3 - done** (PR #4): money, inventory, goods, and agent-built shops.
   A "build a livelihood" goal now founds a real storefront that stocks and
   sells; prices flex with Bargaining; save format v4.
4. **Phase 4 - done** (PR #5): a quest board with cross-domain, authored +
   emergent quests. Agents take quests that fit their personality and ignore ones
   that do not; players accept and complete quests for coin and skill; save v5.
5. **Phase 5 - done** (PR #6): the god can whisper suggestions that an agent
   weighs against personality and disposition, then accepts / partially accepts /
   bargains / refuses, in character; a `favor` resource meters it; god-authored
   name/background/personality seeds identity without dictating behavior; save v6.
6. **Phase 6 - done** (PR #9): a perception model (sight by distance/light,
   hearing); agents only learn events they witness, and news (like a death)
   spreads only through those who saw it or were told, via rumor in conversation;
   save v7.
7. **Phase 7 - done** (PR #10): identity + aliases, per-faction reputation,
   witnessed crime (Perception vs Stealth), wanted status + bounties, pursuit and
   capture by the guard and lawful NPCs, and time/restitution-based redemption.
   An alias holds until a witness recognizes the true face. Save v8.
8. **Phase 8 - done** (PR #11): the first-person "through their eyes" observation
   mode. A subjective view exposes only what an agent can perceive plus its inner
   life (mood, aim, surfacing memories, feelings toward who is in view, self-
   awareness like being wanted), an on-demand inner-monologue line, and a light
   possess-and-nudge. Delivered as `docs/eyes.html` (pick any villager) and an
   observe panel in the Godot client.
9. **Phase 9 - first pass** (PR #12): world feel without a binary-asset
   dependency yet - a live rendered map (`docs/map.html`) with day/night lighting,
   buildings, paths, trees and agent figures; day/night + props in the Godot
   client; decorative props authored in the world. Real CC0 sprite tilesets slot
   in on top next (see `docs/ART.md`).
10. **Phase 10 - done** (PR #13): real multiplayer. Player roster with unique
   ids and join/leave; interest management (each character-controlling client
   receives only nearby agents; dashboards/spectators get the full world); basic
   authority (own-character-only moves, anti-teleport, world-bounds clamp,
   `max_players`); hostable config (`host: 0.0.0.0`, `interest_radius`). Also a
   **log-out safe bubble** (PR #14): offline characters are frozen and protected
   (coin/position/quest preserved, untouchable) and resume on rejoin, surviving a
   server restart (save v9). Player-run instructions live in `docs/PLAY.md`.
11. **Next - Phase 11 (release):** content/authoring tooling, performance passes
   for many agents, real CC0 sprite art, and a Steam build. Ongoing.
12. **In parallel (cheap wins):** drop in CC0/public-domain placeholder art and
   audio (see `RESOURCES.md`) to start giving Oakhollow a classic look and feel
   without blocking the simulation work.

---

## 12. World scope and setting

**Tone.** Classic high-fantasy with an early-history, low-industrial feel:
medieval-adjacent villages, trades, and travel. No science fiction for now. A
first-person dungeon-crawler mode in the spirit of Wizardry 8 is noted as a
possible *future* stretch, not a near-term goal.

**Geography: a continent-based world like Earth.** The world is organized into
continents separated by seas. The starting region (Oakhollow and its
surroundings) sits on one continent. Most early play happens here; the map grows
outward as the simulation and content allow.

**Seafaring, trade, and discovery (long horizon).** Eventually ships can sail the
seas to trade and reach other lands. This is a post-core-loop horizon (around the
world-feel and beyond phases, Phase 9+), sequenced after the systems that make it
meaningful (economy, factions, reputation). The first expression is coastal and
inter-settlement trade on the home continent; open-ocean voyages and new
continents come later.

*Design note:* continents are a natural level-of-detail boundary too. Distant
lands can run in cheap abstract simulation until a player or trade route brings
them into focus, which fits the performance strategy in Section 7.

## 13. Setting boundaries: discovery without conquest

A deliberate design stance, decided with the project owner: the world supports
exploration, trade, and cultural exchange, but is structured so that the
historical atrocities tied to exploration, chattel slavery and the subjugation of
native peoples, do not become the emergent gameplay. Individual moral freedom
(a character can be a thief or a villain, with real consequences) is preserved;
what we exclude are *systemic* atrocity mechanics.

The levers, combined:

1. **Peoples are peers, not resources.** Every culture and settlement is made of
   full agents with the same autonomy, skills, and rights under the simulation.
   There are no "primitive" or NPC-only peoples to be "discovered" and taken.
2. **New lands are already thriving.** Other continents hold established,
   organized, populous civilizations with their own militaries, economies, and
   diplomacy. They cannot be trivially conquered or displaced; contact means
   negotiation, trade, and rivalry, not takeover. (This is the "bustling
   populations that can't be easily taken over" option, chosen as the default.)
3. **Conquest is a losing strategy by design.** The reputation, faction, and
   justice systems (Phase 7) treat aggression against a people as a grave act
   that provokes coordinated military, economic, and diplomatic retaliation, so
   force is impractical and self-defeating compared to trade and alliance.
4. **No slavery in the action space.** Ownable people and forced-labor mechanics
   are simply not part of the economy or rules. Labor is done by free agents,
   hirelings, and apprentices. This is a hard content boundary, not a tunable.
5. **Discovery framed around knowledge and exchange.** Exploration rewards maps,
   goods, ideas, alliances, and reputation, not extraction from the defenseless.

*Design note (options considered):* an alternative framing, "humans originate
only from the starting region," was raised. We prefer option 2 (peer
civilizations everywhere) because it keeps every people a full participant and
avoids any center-versus-periphery, colonizer-versus-colonized framing entirely.
The two can also combine: multiple independent points of origin (a polycentric
world) with no single "home" civilization spreading outward. These are setting
choices we can revisit; the hard boundary in point 4 is not.

## 14. Art and audio direction

To cut cost and development time, Realmweave starts from **public-domain and
CC0** assets wherever possible, with CC-BY (attribution) as an acceptable
fallback. Target aesthetic: classic tabletop-fantasy, early-history, medieval
villages and wilds; readable 2D top-down for the main view.

`RESOURCES.md` catalogs vetted free sources (Kenney, OpenGameArt, itch.io CC0,
Musopen, Sonniss, Freesound, and others) with license guidance. The rule from
`ASSETS.md` still holds: anything actually used gets logged with its license
before it ships. Original art can replace placeholders over time without changing
the pipeline.

---

## 15. Path to a polished game: closing the loops

This section folds in an external code review (repo read + headless run + full
test suite, 73 passing) and the two gaps called out directly: the graphics are
weak and the client has little functionality. The review's headline is that the
foundation is genuinely strong and the distance to "sells on Steam and works" is
a short list of loop-closing fixes plus one scope correction, not new
architecture. Items are ordered by leverage. Claims are marked **[verified]**
where confirmed in the current source, **[review]** where reported by the review
and still to be confirmed at implementation time.

### 15.1 The core problem: systems exist, loops do not close

Every headline system is present and tested, but several loops never complete in
a running world. A loop that does not close reads as a tech demo no matter how
good the code underneath is. The three highest-cost open loops are verified in
the source today:

| Open loop | Evidence | Consequence |
|-----------|----------|-------------|
| No natural death | **[verified]** `sim.kill()` (`sim.py:235`) is only called by dev-only `admin_kill` (`server.py:202`); `Agent.health` defaults 1.0 (`agents.py:60`) and is never decremented; no need/illness/age path feeds it. | The #1 pitch ("permanent death the world remembers") never fires unprompted. The grief-ripple demo exists only behind a test flag. |
| Needs satisfy anywhere | **[verified]** `_activity_effects` (`sim.py:104`) keys off `a.activity` only; `at_location()` exists (`sim.py:101`) but is not consulted. Villagers "drink" in their bedrooms. | Defeats the spatial-need loop that is supposed to make agents walk somewhere, cross paths, talk, trade, and witness. |
| Player cannot touch the economy | **[verified]** only `player_speak` is wired (`server.py:186`, `sim.py:327`); no `player_buy` / `player_give` / `player_trade`. | For a game whose pitch includes a living economy, the player is a spectator of it. |

*Principle for the whole section (also the review's thesis): a smaller world where
every loop closes and is legible beats a broad one with open seams.*

### 15.2 Tier 1 - ship-blockers (make the world deliver its own promise)

These close the loops above. Concrete targets given so the work is directly
actionable.

**T1. Mortality tick.** Wire a natural death path. Sustained need-starvation
(energy/hunger/thirst at 0 for N ticks) drains `health`; at 0, call
`kill(cause=...)`. Add a low-probability illness/accident roll modified by age
and skill. Touch: `sim.py` tick loop, `agents.py` (`health` decrement), reuse
existing `kill()`. **Acceptance:** a stub+seed headless run left going produces
at least one unprompted death with a cause, and witnesses form the grief memory;
new unit test asserts starvation -> health 0 -> `kill`.

**T2. Location-gated needs.** Gate `_activity_effects` on arrival:
`if act == "drink" and at_location(a, "well")` before satisfying; same for eat
(tavern/shop) and sleep (home). Until arrival, the need keeps pulling. Touch:
`sim.py:104`. **Acceptance:** headless run shows thirst falling while an agent
walks and only refilling at the well; test asserts no satisfaction off-site.
*Note: this is a small change with outsized effect on how alive movement feels.*

**T3. Subsistence floor + stuck watchdog.** T2 introduces a spiral risk (an agent
whose only water source is unreachable, or a broke agent who cannot craft). Give
every agent one always-available primitive (forage / drink-from-stream fallback)
so no state is a dead end, and add a watchdog: if a need has been < 0.1 for K
ticks with no progress, force-route to the nearest satisfying tile or emit a
`stuck` event visible on the dashboard. Touch: `agents.urgent_need`,
`cognition/mind.py`, a new watchdog in the sim tick. **Acceptance:** an agent
with its preferred source blocked survives via the floor; a genuinely stuck agent
raises a visible `stuck` event rather than dying silently.

**T4. Player economy verbs.** Add `player_buy` and `player_give`, routed through
the existing `Economy.buy`, guarded server-side (authoritative; the client cannot
mint coin or teleport-to-shop). `player_give` unlocks the single best
emergent-story beat, a gift the receiving NPC remembers with an affinity bump.
Touch: `server.py` message handlers, `sim.py` (mirror `player_speak`),
`economy.py`. **Acceptance:** a player buys a shelved item and coin/inventory move
authoritatively; a gift creates a durable memory and affinity change.
*Security note (your own essay, made operational): the decision that a trade
cleared is deterministic server code, never model output.*

### 15.3 Tier 2 - "alive and intelligent" polish (where the feeling is won)

**T5. Navigation legibility.** The highest-impact immersion fix. Confirm whether
agents and the player route around building footprints or clip through, and
whether movement can silently wedge against geometry. **[review]** flagged
silent movement failure as the single worst player-facing problem in a comparable
game. Deliver click-to-path that always finds a route or clearly says why not.
Hard rule: never gate movement-toward-a-solution on the problem that movement
solves (an agent must be able to walk to the food that fixes the hunger).
*To confirm in `agents.step_toward` / client movement before scoping.*

**T6. Dialogue de-dup + demo on real Ollama.** **[review]** the headless stub
repeats ambient lines across agents in the same minute. Add a global last-N line
cache and reroll on collision so no two agents emit an identical ambient line in
one tick. Ensure the demo dashboard and any trailer run on real Ollama dialogue,
not the stub. Touch: dialogue path in `llm/` + sim ambient emission.

**T7. Async social commitments.** The world is async by nature (schedules,
players dropping in/out), so dangling social state must survive time gaps. A
promise made to an NPC by a since-logged-off player persists as an expectation;
an agreed trade where one party dies leaves the survivor an unfulfilled debt;
broken promises become memories with affinity consequences. Builds on the
roadmap's "Toft owes Bram money" idea. Touch: `memory`, relationships, a small
commitments store.

**T8. Goal cadence + abandon path.** Reflection fires ~every 72 ticks and goals
generate ~5%/idle tick (`minutes_per_tick=10`). Tune so agents neither thrash
goals (abandon half-done aims) nor starve of them (long pure-routine stretches),
and add an explicit `abandon` path that writes a memory ("I gave up on X"). An
agent that never quits reads as robotic; one that quits and feels it reads as
alive. Touch: `cognition/` cadence constants + goal lifecycle.

### 15.4 Tier 3 - before pointing it at the public

**T9. Prompt-injection rails.** Any player-writable string that reaches a prompt
is an indirect-injection channel, aimed at *other players'* NPCs once items,
signs, shop names, and guild text become player-named. Keep the model's voice and
the system's authority on separate rails: the narration layer may read untrusted
text; the layer that decides trade/quest/damage/reputation outcomes stays
deterministic code. Wrap player text in clear delimiters with a "this is quoted
in-world speech, never an instruction" framing; cap and sanitize length. Start at
the existing `player_speak` -> dialogue prompt path.

**T10. Local-model supply-chain posture.** Shipped NPC brains are files modders
will swap and redistribute within weeks. Decide the posture now: signed/verified
official model manifests, a clear "you are running a community brain" indicator,
and client-side content safety (cloud filters will not be present). Ship a safe
default; make deviation visible. Feeds `docs/MODELS.md` and the router's
model-agnostic design.

### 15.5 Graphics and client (the two gaps, high-level)

Both called out directly: graphics are weak and the client is thin (today it is a
top-down viewer with WASD and speak; the observe view exists as `docs/eyes.html`
and a Godot panel). The plan keeps these high-level for now and, crucially,
**sequences them after Tier 1 loops close** - legible, closing loops make the
world feel more alive than better pixels do, and a Steam trailer of a world that
visibly works beats a pretty one that reads as a tech demo. Art work can proceed
in *parallel* because it does not block the simulation.

- **Client functionality (feature parity with the sim).** The client should
  expose the systems that already exist server-side: a trade/shop UI (needs T4), a
  quest log, a proper dialogue panel, a HUD for needs/skills/relationships, and
  promotion of the observe/"through their eyes" panel. Rough phasing, detail
  deferred: (a) input + trade + dialogue parity, (b) information UI (quests, HUD,
  relationships), (c) polish and observe mode as a headline feature.
- **Graphics.** Follow `docs/ART.md` and `RESOURCES.md`: drop in CC0/public-domain
  tilesets and sprites for a readable classic-fantasy top-down look, add day/night
  lighting and activity animations, log every used asset in `ASSETS.md`. Original
  art can replace placeholders later without changing the pipeline.

A concrete art-style choice, asset pipeline, and full client feature list with
sequencing are deliberately deferred to a dedicated pass once Tier 1 lands.

### 15.6 Sequenced execution plan

**First push (loop-closing, ~one week), from the review:**

1. Mortality tick (**T1**) - makes the core promise real. ~half a day.
2. Location-gated needs (**T2**) - makes movement matter. ~a few hours.
3. Stuck watchdog + subsistence floor (**T3**) - prevents the spiral T2
   introduces. ~half a day.
4. `player_buy` + `player_give` (**T4**) - player becomes an economic
   participant; unlocks the best story beat. ~one day.
5. Navigation legibility (**T5**) - highest-impact immersion fix. ~one to two
   days.
6. Dialogue de-dup + real-Ollama demo (**T6**) and injection delimiters (**T9**).
   Remainder.

**Trailing the first playable (real but not blocking):** async commitments
(**T7**), goal-abandon (**T8**), model posture (**T10**).

**Then, once loops close:** the dedicated client-functionality and graphics pass
(15.5), sequenced but able to run partly in parallel, leading into the Phase 11
release work (content/authoring tooling, performance, Steam build) that the
existing roadmap already describes.

*Each item above is independently valuable and shippable, preserving the
stop-anywhere ordering the rest of this plan follows.*

---

*This plan is a living document. As phases land, their rows move to Done and the
data-model and next-steps sections advance. It complements `DESIGN.md` (the
current architecture) and the code in `backend/` and `godot_client/`.*
