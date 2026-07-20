# Realmweave Backlog

Working to-do list for world content, art, and UX. Complements the phased
roadmap in `PROJECT_PLAN.md` (this file is the near-term, concrete task board).
Effort is rough: S = hours, M = a day or two, L = multi-day.

Legend: [ ] todo · [~] in progress · [x] done

## Now / next (top of the stack, 2026-07-20)

Recently shipped (on the open PRs #45/#46/#47, not yet merged): LPC art render path,
world zoom, client+server versions, the tag-filterable **Memories** panel, the
scrollable/pausable **event log**, and the LLM-free dialogue grammar. See "Current
work state" in `CLAUDE.md` for the full status and known-weak list.

Next up, roughly in order:

- [ ] **Decide + do the PR merge order** (#45 -> #46 -> #47) to consolidate and stop
      branch divergence. Effort: S
- [ ] **User verification pass**: F5 the client, confirm the Memories panel (click tag
      chips) and event-log scroll/pause, and send day+night screenshots for graphics tuning.
- [ ] **Reliable graphics verification** - the top blocker. A CI job (or stable local
      render) that produces a client screenshot artifact, so visuals stop shipping
      unverified. Today the sandbox render dies and remote screenshots can't capture the
      GL window. Effort: M
- [ ] **Character overview: next tabs** - Bag (inventory + coin + bounty) and Social
      (relationships/affinity) reuse the panel + tagged-payload pattern just built. Effort: M
- [ ] **Building/character depth sort** and **architecture-aware light occlusion**
      (`LightOccluder2D`) - the real night-scene quality jump. Effort: M / L

## World and map content

- [~] **Flesh out the lands around town.** Define the region beyond the village
      edge (roads out, biomes, borders) so Oakhollow sits in a place, not a void.
      Touches `backend/realmweave/world.py` (new outer locations/zones) and the
      map renderers. Effort: L
- [x] **Farms and croplands.** Fields and farms carry a ripeness that grows
      over time; working a ripe one harvests grain (yield scales with ripeness),
      then it regrows. Grain feeds the existing Cooking chain, so the fields
      actually feed the village. Growth stages show on the map (bare/green/gold).
- [x] **Fields with animals / livestock.** Ambient animals (sheep, cow, horses,
      pig, hens) graze near home by day and gather at a pen at night
      (`realmweave/livestock.py`), streamed in the snapshot and drawn on the map.
- [x] **Seasonal crop growth.** Crops grow by season and lie dormant in winter;
      deliberately forgiving, so a fallow winter never starves the village. The
      current season shows on the dashboard clock.
- [x] **Granary + haul grain.** A new granary holds a shared grain store;
      farmhands tip their reaped grain in when they reach the granary or the
      tavern, and the cook draws from the store (free) before buying. Shown on
      the map (with a live count) and the dashboard.
- [x] **Egg & milk yields.** Hens lay eggs and the cow gives milk on a timer; a
      living field hand does the daily rounds and gathers them into a shared
      larder, shown on the dashboard. (Could later feed cooking or be sold.)
- [ ] **Crop destruction (raiders / blight).** The one way a harvest should fail:
      a raid or blight ruins standing crops in a field. Rare and telegraphed;
      ties to a future threat/event system. Effort: M
- [x] **Stable buildout.** The stable is now a fenced paddock with a herd of
      four horses and two goats, tended by Isla the stable hand. Drawn on the
      live map and the atlas.
- [x] **Dungeons.** Four dungeons with lore (`realmweave/dungeons.py`) - the
      Kobold Warren, the Hollow Barrow, the Weeping Caverns, and the Welldeep
      (the Gilded Stag's cellar rats down the Old Well into deep mystery), marked
      on the maps and described on the atlas. *Delvable:* `sim.resolve_delve`
      plays a dungeon level by level as combat exchanges scaling with danger and
      depth (wounds, rare death, loot); a full clear reveals the mystery. Able
      adventurers mount expeditions (gated by `delve_chance`, off in tests, on in
      the server/headless); cleared dungeons show on the map and delves in the
      Chronicle. Delves are quest-driven: a delve quest is posted and taken, and
      the adventurer physically travels to the dungeon's frontier before descending.
      *Could still add:* a physical party rather than a lone hero, interior
      tiles/rooms, and per-dungeon bosses and loot tables.
- [ ] **More scenery variety.** Additional tree types, scattered rocks, bushes,
      dirt paths. `default_props()` in `world.py` + renderer glyphs. Effort: S

## Simulation and dialogue

- [x] **Villagers walk the roads.** Nearest-neighbour road network + routing so
      NPCs follow paths instead of cutting across (`world.py`, `sim.py`).
- [x] **Dialogue line database.** `realmweave/llm/dialogue.py`: rich line pools
      keyed by time of day, mood, place, the other's trade, and gossip/grief,
      with a weighted composer that reads the prompt and picks an apt line. The
      stub now sounds context-aware (role-, place-, and mood-appropriate) without
      calling the LLM. Could grow: more categories, trade/haggle banter, per-NPC
      verbal tics, weather/season lines.

## Art and graphics

- [x] **Upgraded building icons on the atlas map** (`docs/assets/maps/`,
      generated by `docs/assets/maps/generate_maps.py`).
- [ ] **Bring the new building look to the live renderers.** Match the upgraded
      icon style in `docs/map.html` and the Godot client (`Main.gd`) so the live
      map and game view match the atlas. Effort: M
- [x] **Animal sprites** for livestock (drawn on the live map + atlas; could be
      upgraded to tile art later).
- [ ] **Dungeon tiles and entrance art.** Effort: M
- [ ] **Optional higher-fidelity art pass.** If we want painted scenes rather
      than vector/tile art, use an image generator (see Tooling). Log every
      asset in `ASSETS.md` with its license. Effort: varies
- [ ] **Architecture-aware night lighting.** Lights are radial `PointLight2D`
      blobs that pass straight through walls/roofs. Add `LightOccluder2D` polygons
      to building sprites so light is blocked by geometry, and shape the emitters
      to windows/doors (rectangular, warm near source) instead of pure circles.
      Effort: L
- [ ] **Building/character depth sort.** Buildings are drawn before all villagers,
      so a villager standing *behind* a building still overlaps it. Y-sort
      buildings and characters together (or use a real `YSort`/`y_sort_enabled`)
      so depth reads correctly. Effort: M
- [ ] **Anchor building labels to the structure base** rather than floating; avoid
      overlap with light pools and path edges. Effort: S

## UI and UX

- [x] **Needs legend on the dashboard.** energy / hunger / thirst / social with
      ok / low / urgent colors (`docs/index.html`).
- [ ] **Surface needs in the character view too** (`docs/eyes.html`) with the
      same labeling, so a single NPC's needs are readable. Effort: S
- [ ] **Player-facing "what do I need" panel** for an embodied player character
      (once player needs are modeled). Effort: M
- [ ] **Event log panel: scroll bars + pause/play.** The in-client event log
      (bottom panel in `Main.gd`) currently shows only the last few lines and
      auto-scrolls. Add a scroll bar to page back through the history and a
      pause/resume toggle so the stream can be frozen while reading. Effort: M
- [ ] **Character overview panel (scrollable, tabbed).** Clicking/inspecting an
      agent opens a scrollable overview with tabs: **Kills** (from death/justice
      events), **Bag** (inventory items + coin + bounty), **Memories**, **Social**
      (relationships / affinity), **Quests**, and **Crafting** (known recipes and
      outputs). Modeled on the character view in play.artificiety.world. Builds on
      the existing observe/subjective stream. Effort: L
- [ ] **Tagged, filterable memories** (the standout from Artificiety). Give each
      memory tags - derived from its `kind`, the people/places it names, and the
      event type - and render them as clickable chips in the overview; clicking a
      tag filters the memory list (faceted, multi-select). Most data already
      exists: `MemoryEntry` has text/importance/kind, and inventory/coin/bounty/
      recipes/quests/justice are all modeled. The work is (1) a protocol field
      exposing the richer per-agent payload, (2) tag derivation, and (3) a Godot
      `ScrollContainer` + tab UI with toggle-able tag chips. Effort: M

## Tooling

- [ ] **Add an image-generation connector** so raster art can be produced in-app
      for the higher-fidelity art pass. James to enable; I can suggest options.
      Effort: S
- [ ] **CI screenshot artifact for the client.** A CI job that runs `tools/screenshot.sh`
      (headless Godot + xvfb + stub server) and uploads a PNG per PR, so client visuals are
      checked automatically instead of relying on a manual F5. This is the fix for the
      top-of-`CLAUDE.md` "graphics verification" weakness. Effort: M
- [ ] **Unify the version number to a single source.** Client (`CLIENT_VERSION`), server
      (`__version__`), and installer (`AppVersion`) are three separate strings that can drift.
      Read one canonical version (e.g. a `VERSION` file or `backend/realmweave.__version__`)
      into all three at build time. Effort: S
- [ ] **Run the LPC/client branch through CI** (export + tests) rather than hand-building the
      exe in the sandbox, which has been unreliable. Effort: M
- [ ] **Dialogue pre-built-intelligence, remaining steps** (from the plan): offline
      corpus-baker (LLM expands the grammar once, curated to data files), utility-AI/GOAP
      cleanup of the reflex tier, and a runtime response cache keyed by situation signature.
      Effort: M each
