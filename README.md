# Realmweave

A persistent, living high-fantasy world simulation powered by local LLMs. NPCs
have their own routines, memories, relationships, and mortality. You influence
the world; you don't own it. Single-player now, multiplayer by design. MIT.

See [DESIGN.md](DESIGN.md) for the full architecture and roadmap.

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

Phase 0 (done): living village, routines, memory, death, protocol, 2D client.
Phase 1 (in progress): player dialogue reaching NPCs and save/load are **done**;
still to come: sprites/tilemap, day-night lighting, inventory/objects.
Phase 2: agent goals/plans, factions, rumor spread, economy, illness.
Phase 3: hostable dedicated server, player roster, interest management.
Phase 4: content tooling, performance, Steam build.

Contributions welcome under the MIT License.
