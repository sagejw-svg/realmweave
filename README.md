# Realmweave

A persistent, living high-fantasy world simulation powered by local LLMs. NPCs
have their own routines, memories, relationships, and mortality. You influence
the world; you don't own it. Single-player now, multiplayer by design. MIT.

[![CI](https://github.com/sagejw-svg/realmweave/actions/workflows/ci.yml/badge.svg)](https://github.com/sagejw-svg/realmweave/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-d9c46b.svg)](LICENSE)
[![Roadmap](https://img.shields.io/badge/roadmap-10%2F12%20phases-5aa0c0)](PROJECT_PLAN.md)
[![Live dashboard](https://img.shields.io/badge/live-dashboard-5ab97a)](https://sagejw-svg.github.io/realmweave/)
[![Through their eyes](https://img.shields.io/badge/first-person-d9c46b)](https://sagejw-svg.github.io/realmweave/eyes.html)
[![Dev status](https://img.shields.io/badge/dev-status-9a7bd0)](https://sagejw-svg.github.io/realmweave/dev.html)

**Want to play or run it now? See [docs/PLAY.md](docs/PLAY.md).** Three paths:
look at the [live pages](https://sagejw-svg.github.io/realmweave/) in a browser
(no install), watch the world run headless (`python backend/run_headless.py
--ticks 200 --stub`), or play the interactive Godot client (start the server,
open `godot_client/project.godot` in Godot 4, press Play).

### Downloads

- **All releases:** https://github.com/sagejw-svg/realmweave/releases
- **Windows installer (latest):**
  [RealmweaveSetup.exe](https://github.com/sagejw-svg/realmweave/releases/latest/download/RealmweaveSetup.exe)
  (available once a tagged release finishes building)

Prefer to host a persistent world? See [docs/HOSTING.md](docs/HOSTING.md) for a
24/7 storage-host deployment where the server keeps the world and players run the
AI themselves.

See [DESIGN.md](DESIGN.md) for the current architecture, and
[PROJECT_PLAN.md](PROJECT_PLAN.md) for the full phased roadmap from here to
seeing the world through an AI's eyes (skills, autonomy, economy, quests, and
divine influence).

---

## What's in this drop

- **A working authoritative simulation** (Python): 8 autonomous villagers in
  *Oakhollow* with schedules, needs, memory + retrieval, relationships, and
  permanent death that others remember.
- **A tiered LLM router** (Ollama + a GPU-free stub fallback): cheap models for
  ambient chatter, mid models for real dialogue, a strong/`narrative` tier for
  key moments.
- **A WebSocket server** streaming the world to clients (already the multiplayer
  seam).
- **A Godot 4 2D client**: top-down view, live clock, NPC speech bubbles, event
  log, WASD movement.
- **A headless runner** so you can feel the world breathe in a terminal with no
  GPU at all.

---

## Quick start (no GPU) - see the world in 60 seconds

You only need Python 3.10+.

```bash
cd realmweave/backend
python run_headless.py --ticks 144 --stub
```

You'll get an hourly digest of who is doing what, live dialogue, and memories.
Try the drama test (kills the tavernkeeper at tick 40 and watch grief ripple):

```bash
python run_headless.py --ticks 120 --stub --kill bram
```

Talk to a villager and persist the world:

```bash
# a traveler speaks to the nearest NPC at tick 20, then the world is saved
python run_headless.py --ticks 60 --stub --say "Is the Stag still serving?" --save data/save.json
# resume that exact world (dead stay dead, memories intact)
python run_headless.py --ticks 60 --stub --load data/save.json
```

In the Godot client, press Enter to focus the chat box, type a line, and press
Enter again to speak to whichever villager is closest. Their reply appears as a
speech bubble and in the event log. The server auto-saves every 60s and on exit,
and resumes automatically on next launch.

`--stub` forces the deterministic, GPU-free LLM. Drop it once Ollama is running.
On Windows the Python launcher is usually `py` instead of `python`.

---

## Full setup (Windows + RTX 5070, 12 GB)

### 1. Install Ollama and pull models
Install Ollama for Windows from https://ollama.com, then:

```powershell
ollama pull qwen2.5:1.5b-instruct   # reflex tier (ambient chatter)
ollama pull qwen2.5:7b-instruct     # dialogue tier (real conversations)
ollama pull qwen2.5:14b-instruct    # narrative tier (deaths, big moments)
ollama pull nomic-embed-text        # memory embeddings (RAG)
```

**Want different models, or Claude / an API model?** See
[docs/MODELS.md](docs/MODELS.md). You can swap any Ollama model, or enable a
remote model (Claude / OpenAI-compatible) for chosen moments; it stays
local-first by default and falls back automatically if the API is unreachable.

Ollama serves on `http://127.0.0.1:11434` by default. On 12 GB, keep one large
model resident at a time; the router is built around that constraint. If 14B is
tight alongside everything else, set the `narrative` model to `qwen2.5:7b-instruct`
in `backend/config.json` for now.

Model choices are current recommendations for a 12 GB card; swap freely in
`config.json` (e.g. `llama3.1:8b` for the dialogue tier).

### 2. Install the Python server dependency
The core sim is standard-library only. The networked server needs one package:

```powershell
cd realmweave\backend
pip install -r requirements.txt   # websockets
```

### 3. Run the server
```powershell
python run_server.py
# -> Realmweave server listening on ws://127.0.0.1:8765
```
To run the server without a GPU while you set things up, set
`"force_stub": true` in `backend/config.json`.

### 4. Run the Godot client
Install **Godot 4.3+** (standard, non-.NET is fine) from https://godotengine.org.
Open `godot_client/project.godot`, then press Play (F5). It connects to
`ws://127.0.0.1:8765`, drops you into Oakhollow, and you can walk with **WASD**.

---

## Configuration (`backend/config.json`)

```json
{
  "ollama_host": "http://127.0.0.1:11434",
  "force_stub": false,
  "models": {
    "reflex": "qwen2.5:1.5b-instruct",
    "dialogue": "qwen2.5:7b-instruct",
    "narrative": "qwen2.5:14b-instruct"
  },
  "reflex_max_importance": 3.0,
  "dialogue_max_importance": 7.0,
  "sim":    {"minutes_per_tick": 10, "seed": 7, "social_chance": 0.5, "reflection_interval": 720},
  "server": {"host": "127.0.0.1", "port": 8765, "broadcast_hz": 4, "ticks_per_second": 8}
}
```

- `force_stub`: run the whole thing without Ollama/GPU.
- `reflex_max_importance` / `dialogue_max_importance`: the thresholds that route a
  request to a cheaper or stronger model.
- `ticks_per_second`: how fast in-game time advances in real time.

---

## Project layout

```
realmweave/
  backend/    Python simulation, LLM router, WebSocket server
  godot_client/  Godot 4 2D client
  DESIGN.md   architecture, decisions, roadmap
```

Key files to read first: `backend/realmweave/sim.py` (the loop),
`backend/realmweave/agents.py` (the cast), `backend/realmweave/llm/router.py`
(the tiering), `godot_client/scripts/Main.gd` (the whole client).

---

## Roadmap (short version)

Done: **0** living village, **1** rules & 1-100 skills, **2** agent autonomy,
**3** livelihoods & economy, **4** cross-domain quests, **5** divine influence,
**6** perception, **7** reputation & justice, **8** through-their-eyes first-person
view, **9** world feel (first pass), **10** multiplayer. Next: **11** release.
See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the detail.

## Dashboards

Four auto-updating pages live under `docs/` and are published via GitHub Pages
at https://sagejw-svg.github.io/realmweave/ :

- **World dashboard** (`index.html`) - the live game world (below).
- **Map** (`map.html`) - a rendered top-down view of Oakhollow with day/night
  lighting, buildings, trees, and agent figures, updating live.
- **Through their eyes** (`eyes.html`) - a first-person view: pick any villager
  and see and think from their perspective.
- **Development status** (`dev.html`) - phase roadmap plus live GitHub data (CI
  status, recent commits, open PRs, and open issues by triage label). This one
  reads the public GitHub API, so it shows real data straight from GitHub Pages
  or any browser, no local server needed.

### World dashboard

`docs/index.html` is a self-contained, auto-updating view of the world: clock,
villagers (AI NPCs), human players online, shops, quests, and a live event
chronicle. It separates NPCs, human players, and the god/overseer, and shows each
villager's Devotion (feeling toward the overseer). It connects to the game server
over WebSocket and refreshes in real time.

- **Live (recommended):** start the server (`python run_server.py`), then open
  `docs/index.html` in your browser. It connects to `ws://127.0.0.1:8765` and
  updates live. You can change the server URL in the top bar.
- **GitHub Pages / preview:** the page is also published at
  https://sagejw-svg.github.io/realmweave/ . A page served over https cannot reach
  a local `ws://localhost` server (browser mixed-content rules), so on Pages it
  shows built-in **demo data**. For live data, open the file locally as above, or
  run the server behind a `wss://` (TLS) endpoint and point the URL bar at it.

## Multiplayer & hosting

The server has always been authoritative and multi-client; Phase 10 makes it a
real multiplayer host:

- **Player roster** with unique ids (same display name is fine), join/leave
  events, and a shared world all clients see.
- **Interest management:** a client controlling a character receives only the
  agents near it (`interest_radius` in `config.json`), which bounds bandwidth as
  the world and player count grow. Spectator clients with no character (the
  dashboards) still get the full world.
- **Basic authority / anti-cheat:** the server is the source of truth. A client
  may only move its own character, only a sane distance per update (no
  teleporting), clamped to the world bounds. `max_players` caps the lobby.

To host for others, set the server to bind all interfaces and pick your limits in
`backend/config.json`:

```json
"server": { "host": "0.0.0.0", "port": 8765, "interest_radius": 24.0, "max_players": 16 }
```

Then `python run_server.py`, open the port on your firewall/router, and players
point their client (or the dashboards) at `ws://YOUR_IP:8765`. For anything
public, run it behind a `wss://` (TLS) reverse proxy.

## Contributing

Everyone is welcome, coder or not. Ideas, bug reports, playtesting, art, music,
and docs all count. Submissions go through guided issue forms and a short
approval step by the head developer, then a merge gate (CI + review) that applies
equally to human and AI-assisted contributions.

- Read [CONTRIBUTING.md](CONTRIBUTING.md) for how a suggestion becomes part of the game.
- See [GOVERNANCE.md](GOVERNANCE.md) for roles and the approval flow.
- Open a [new issue](https://github.com/sagejw-svg/realmweave/issues/new/choose)
  and pick the Idea, Bug, or Code proposal template.

Contributions are accepted under the MIT License.
