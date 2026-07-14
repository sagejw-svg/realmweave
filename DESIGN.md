# Realmweave - Design & Architecture

A persistent, living high-fantasy world simulation powered primarily by local
LLMs (Ollama + multi-model routing), with optional stronger API models reserved
for key moments. Players influence, but do not fully control, an emergent world
with meaningful consequences. Open source under the MIT License.

This document is the north star for the project. It records the vision, the
architecture we are building toward, what the first milestone actually contains,
and the phased roadmap. It distinguishes what is **built today** from what is
**planned**, so decisions stay honest as scope grows.

---

## 1. Design pillars

1. **A world that runs whether you watch or not.** NPCs (agents) have autonomy
   and daily routines: the tavernkeeper serves and washes dishes, the stable
   hand mucks stalls, the sweeper works the square, the farmer watches the sky.
   The simulation advances on its own clock.
2. **Influence, not omnipotence.** Players are participants. They can shift
   relationships, trigger events, and leave marks, but the world has its own
   momentum and pushes back.
3. **Consequences that stick.** Death has lasting impact and no full restart.
   The dead stay dead; the living remember them; the world reshapes around the
   loss.
4. **Local-first.** The default experience runs on the player's own machine
   against Ollama. Stronger remote models are optional and reserved for rare,
   high-importance "narrative" beats.
5. **Mundane detail as immersion.** The feeling of life comes from small,
   grounded moments, not constant spectacle. Cozy first, epic when earned.

---

## 2. Target hardware & LLM strategy

Reference machine: **RTX 5070, 12 GB GDDR7** (Blackwell), Windows.

The 12 GB budget shapes model choice. The sweet spot is 7B-14B models at Q4_K_M
or FP8, which fit comfortably and run at conversational speed (roughly 70-90
tok/s on 7-8B class models). We therefore route by *importance* across three
tiers rather than paying for a big model on every line of ambient chatter:

| Tier | When it fires | Suggested model | Footprint |
|------|---------------|-----------------|-----------|
| `reflex` | Ambient one-liners, background chatter (importance <= 3) | `qwen2.5:1.5b-instruct` | ~1.5 GB |
| `dialogue` | Real conversations players will read, reflections (3-7) | `qwen2.5:7b-instruct` or `llama3.1:8b` | ~4.5-8 GB |
| `narrative` | Deaths, betrayals, world-shaping beats (> 7) | `qwen2.5:14b-instruct` locally, or an API model | ~8.7 GB local |
| embeddings | Memory relevance (RAG) | `nomic-embed-text` | ~0.3 GB |

Only one large model is resident at a time; the router keeps the common path
cheap so the world can host many agents without stalling. If Ollama is
unreachable or a model errors, the router transparently falls back to a
deterministic **stub** LLM so the world never freezes (and so the project builds
and tests without a GPU at all).

The `narrative` tier has a pluggable API backend (off by default, local-first).
That is the seam where a stronger hosted model can be dropped in for the rare
moments that deserve it.

---

## 3. System architecture

Two processes, one authoritative world, connected by a WebSocket + JSON
protocol. This split was chosen deliberately: the simulation and AI live in
Python (fast to iterate, rich ecosystem), the rendering and input live in
Godot 4 (2D now, the path to a Steam release later), and the network seam
between them is *already* the multiplayer seam.

```
+-------------------------------+          WebSocket / JSON          +----------------------+
|   Python backend (authority)  | <--------------------------------> |  Godot 4 client(s)   |
|                               |   snapshot / event  |  player cmd   |                      |
|  Simulation loop (sim.py)     |                                     |  2D top-down render  |
|   - WorldClock (time_system)  |                                     |  WASD movement       |
|   - World / locations (world) |                                     |  clock + event HUD   |
|   - Agents: needs, schedules, |                                     |  speech bubbles      |
|     routines, relationships   |                                     +----------------------+
|   - MemoryStream (RAG-lite)   |                                              ^
|   - Mortality / grief         |                                              |
|                               |                                     (N clients share the
|  LLMRouter (llm/)             |                                      same world = MP path)
|   - reflex / dialogue /       |
|     narrative tiers           |         +------------------+
|   - OllamaClient (stdlib) ----+-------> |  Ollama server   |  local models on the 5070
|   - StubLLM fallback          |         +------------------+
+-------------------------------+
```

### Why the backend is authoritative
Because a shared, server-authoritative world is the only sane basis for
multiplayer and for consequences that must be consistent across observers. The
client is a viewer plus an input device. Even in single-player, the server runs
locally as its own process (or, later, embedded).

---

## 4. Core systems (what exists today)

**World & time (`world.py`, `time_system.py`).** A hand-authored starter
village, *Oakhollow*, with 13 locations (tavern + kitchen, homes, stable,
smithy, well, square, fields, gate). The clock tracks minutes since epoch and
exposes day/season/part-of-day; one tick = 10 in-game minutes by default.

**Agents (`agents.py`).** Eight authored villagers, each with a role, a home, a
workplace, a persona brief (fed to the LLM), an hourly schedule, four needs
(energy, hunger, thirst, social) that decay over time, a health value, and a
relationship map (affinity -1..1). Each tick an agent decides what to do from:
(1) urgent survival needs that override routine, (2) the scheduled block for the
current hour, (3) opportunistic socializing when co-located. Movement is simple
2D steering toward the target location.

**Memory / RAG-lite (`memory.py`).** Each agent owns a memory stream. Entries
carry text, an importance score (0-10), timestamps, and an optional embedding.
Retrieval blends recency (exponential decay), importance, and relevance (cosine
if embeddings are available via Ollama, else keyword overlap), returning only
the handful of memories that matter for the current moment. This is the same
recipe as generative-agent research, kept deliberately small.

**LLM router (`llm/`).** Tiered model selection by importance, an stdlib-only
Ollama client, and the deterministic stub fallback described above.

**Simulation loop (`sim.py`).** Ties it together: advance clock, decay needs,
decide + move each agent, apply activity effects, resolve co-located social
encounters (which call the router for dialogue), periodic agent reflection, and
mortality. Emits structured events (`tick`, `dialogue`, `death`, `reflection`)
to any subscriber. Deterministic given a seed + stub, which makes it testable.

**Death & grief.** `sim.kill(agent_id, cause)` is permanent. The agent stops
acting but its memories persist; every living agent records the loss with
importance scaled by affinity, and close friends escalate to the `narrative`
tier for a grief line. A rumor is added to the world. No restart.

**Server (`server.py`).** Async WebSocket server: streams `hello` (world),
`snapshot` (agents + players + clock, at `broadcast_hz`), and `event` frames;
accepts `player_join`, `player_move`, `player_say`, and a dev-only `admin_kill`.
Multiple connections already share one world.

**Godot client (`godot_client/`).** A single-script 2D top-down viewer:
locations as colored zones, NPCs as labeled tokens with speech bubbles, a live
world clock, an event log, and WASD movement broadcast back to the server.

---

## 5. Data / message contracts

Snapshot (server -> client, ~4 Hz):
```json
{"type":"snapshot","tick":42,
 "clock":{"day_index":0,"day_name":"Sunday","hhmm":"10:10","part_of_day":"morning","is_night":false},
 "agents":[{"id":"bram","name":"Bram Cask","role":"Tavernkeeper","x":20.0,"y":18.0,
            "activity":"work","alive":true,"health":1.0,"location":"tavern",
            "say":"Another round?","needs":{"energy":0.7,"hunger":0.6,"thirst":0.6,"social":0.5}}],
 "players":[{"id":"player:James","name":"James","x":32,"y":24}]}
```
Event (server -> client, on occurrence): `{"type":"event","event":{"kind":"death","name":"Bram Cask","cause":"a sudden fever",...}}`

Player commands (client -> server): `player_join`, `player_move`, `player_say`.

---

## 6. Roadmap

**Phase 0 - Living village (this drop).** Authoritative sim, 8 autonomous
agents with routines/needs/memory, tiered LLM router with Ollama + stub, death
with lasting memory, WebSocket protocol, Godot 2D client, headless runner.
Status: **built and tested headless.**

**Phase 1 - Make it feel alive.** Real tilemap + sprite art; day/night lighting;
richer activity animations; player dialogue actually reaching NPCs (route
`player_say` into the target agent's next decision + memory); inventory/objects;
weather that affects farming and mood; persistence to disk (save/load world +
memories).

**Phase 2 - Depth of consequence.** Agent goals and plans (multi-step, not just
schedules); factions and reputation; rumor propagation through the social graph;
economy (Toft literally owes Bram money - make it matter); illness/injury feeding
mortality; procedural events (a caravan, a theft, a fever season).

**Phase 3 - Multiplayer.** Promote the local server to a hostable dedicated
server; player accounts/roster; interest management (only stream nearby agents);
authority/anti-cheat basics; latency smoothing (client already lerps).

**Phase 4 - Release.** Onboarding and a "session zero" for a fresh world; content
tooling for authoring villages; performance passes for many agents; Steam build,
Deck check, and packaging. MIT throughout.

---

## 7. Key decisions & residual risks

- **Two-process split (Python + Godot).** Buys iteration speed and a clean
  multiplayer seam. Cost: an IPC boundary and serialization overhead. Mitigated
  by keeping snapshots small and broadcasting at a modest rate.
- **Local-first LLMs on 12 GB.** Keeps it free to run and private, but caps model
  quality. Mitigated by importance-tiered routing and an optional API `narrative`
  tier. Residual risk: dialogue latency under many simultaneous conversations;
  mitigate with per-tick budget caps and async generation (planned).
- **Emergence vs. authored quality.** Fully emergent worlds can feel aimless.
  Mitigated by authored personas, schedules, and seeded relationships that give
  the emergence something to push against.
- **Determinism.** Stub + seed give reproducible runs for testing; live LLMs are
  non-deterministic by nature. Tests target the deterministic path.

---

## 8. Repository layout

```
realmweave/
  DESIGN.md                 this document
  README.md                 setup & run instructions (Windows / RTX 5070)
  LICENSE                   MIT
  backend/
    config.json             models, tiers, sim + server settings
    requirements.txt         websockets (core is stdlib-only)
    run_headless.py          run the world in the terminal (no GPU needed)
    run_server.py            start the WebSocket server for the Godot client
    realmweave/
      time_system.py  world.py  agents.py  memory.py  sim.py  server.py  config.py
      llm/ router.py  ollama_client.py  stub.py
  godot_client/
    project.godot
    scenes/Main.tscn
    scripts/Main.gd          single-file 2D client
    icon.svg
```
