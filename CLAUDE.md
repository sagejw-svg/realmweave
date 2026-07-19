# CLAUDE.md - Realmweave

Orientation for an AI agent working on this repo. Read this first, then only the
specific files a task needs. Do not re-explore the whole tree.

## What this is
Realmweave: a persistent, living high-fantasy world simulation. NPCs are
autonomous agents (routines, needs, memory, relationships, mortality). Players
influence but do not fully control an emergent world. Open source, MIT. A Python
authoritative backend + a Godot 4 2D client, joined by a WebSocket + JSON
protocol (which is also the multiplayer seam).

AI is optional and local-first: a tiered LLM router (Ollama) with a
deterministic **stub** fallback so everything runs and tests with no GPU. The
hosted world runs with `force_stub: true` (scripted NPCs, no LLM).

## Agent quickstart (read this, do not re-explore)

This file is auto-loaded. Use the map below; do not crawl the whole tree. Grab
only what a task needs.

Verify client graphics for real (headless, no GPU, no editor) instead of
guessing: `tools/screenshot.sh out.png` starts the stub server and renders a PNG
of the Godot client. It works in a plain Linux sandbox (downloads Godot 4.3 if
missing, uses xvfb + software GL). The client has a built-in capture mode:
`-- --capture=PATH --capture-delay=SECONDS --weather=clear|rain|snow --hour=NN
--player=NAME` (keep delay ~3s so a run fits tight time budgets).

Character sprite reference (Kenney char sheet, col,row, 17px pitch): docs/ART.md.
Cols 0-1 are full figures, cols 6+ are armour icons; role->tile is `ROLE_TILE`
in `godot_client/scripts/Main.gd`.

Cowork/sandbox gotchas:
- Files written with the Edit tool land on the host but can lag the Linux
  shell's mount view. When a shell step must read a just-edited file, write it
  from the shell instead, or check its size first.
- `git` inside the mounted Windows folder can hit a stuck `.git/index.lock`
  that the sandbox cannot delete. Finish the commit on Windows
  (`del .git\index.lock` then `git commit`).
- The mount reports every file as mode 100755; run `git config core.fileMode
  false` to avoid spurious mode diffs.

## Key locations
- Repository / working folder: `C:\Users\USER\Documents\realmweave` (this repo; on
  the dev machine it is a connected Cowork folder you can read and write).
- Hosted world (storage/relay, AI off): DigitalOcean droplet `147.182.233.116`,
  runtime config at `/etc/realmweave/config.json` (via `REALMWEAVE_CONFIG`).
- Client renderers (both key off the same streamed positions/kinds/time-of-day):
  - Web map: `docs/map.html` (also served on GitHub Pages).
  - Godot client script: `godot_client/scripts/Main.gd` (single self-contained script).
- Art / render + lighting notes: `docs/ART.md`.
- Tile/sprite assets (CC0 Kenney): `godot_client/assets/{tiles,sprites}/`, mirrored
  to `docs/assets/{tiles,sprites}/` for the web map; logged in `ASSETS.md`.
- Backend package: `backend/realmweave/`; tests: `backend/tests/` (stdlib unittest).
- North-star docs: `DESIGN.md`, `PROJECT_PLAN.md`.

## Environment / conventions
- Windows. Use `py`, NOT `python` (the bare `python` hits a Store stub).
- Repo root: `C:\Users\USER\Documents\realmweave`.
- Writing style: never use em dashes; use hyphens sparingly.
- Git flow: feature branch -> push -> `gh pr create` -> `gh pr merge --admin
  --squash --delete-branch`. `main` is protected (CODEOWNERS review + CI).
- After merging, sync local with `git fetch && git reset --hard origin/main`.

## Common commands
```powershell
cd C:\Users\USER\Documents\realmweave\backend
py -m unittest discover -s tests -p "test_*.py"   # run all tests (stdlib unittest, NOT pytest)
py run_headless.py --ticks 144 --stub             # watch the world in the terminal, no GPU
py run_server.py                                  # start the WebSocket server (ws://127.0.0.1:8765)
```
Godot client: open `godot_client/project.godot` in Godot 4.3+, press Play (F5).

## Layout
```
backend/
  config.json            models, tiers, sim + server settings
  run_headless.py        terminal runner (no GPU)
  run_server.py          WebSocket server for clients
  realmweave/
    time_system.py world.py agents.py memory.py sim.py server.py config.py
    cognition/           personality, goals, planner
    economy.py quests.py divine.py perception.py justice.py   (systems)
    llm/ router.py ollama_client.py stub.py api_backend.py
  tests/                 test_*.py (stdlib unittest)
godot_client/            single-file 2D client (scripts/Main.gd)
docs/                    HOSTING.md MODELS.md PLAY.md ART.md + dashboards (*.html on GitHub Pages)
deploy/                  dxedge_deploy.sh (droplet installer)
packaging/               PyInstaller / Inno Setup installer
.github/workflows/       ci + release (Build installer on tag v*)
```
North-star docs: `DESIGN.md` (architecture + roadmap) and `PROJECT_PLAN.md`.

## Architecture notes
- The backend is authoritative. The client is a viewer + input device.
- Save/load is versioned JSON with migrations; bump the version when the schema
  changes and add a migration.
- Determinism: stub + seed give reproducible runs; tests target that path.
- Live time control is server-authoritative (speed ladder + pause), exposed in
  the snapshot/hello and adjustable via a `set_speed` command.

## Deployment (droplet)
Hosted "storage-host" world on a DigitalOcean droplet (147.182.233.116),
storage/relay only, AI off. Runtime config lives OUTSIDE the repo at
`/etc/realmweave/config.json` (read via `REALMWEAVE_CONFIG`) so the systemd
auto-update `git pull` never conflicts. Re-deploy:
```
cd /opt/realmweave && sudo git checkout -- . && sudo git pull && sudo bash deploy/dxedge_deploy.sh
```

## Gotchas (learned the hard way)
- CI Godot export: `Godot_win64.exe` is a GUI-subsystem binary; PowerShell does
  not wait for it. Use the `*_console.exe` and/or `Start-Process -Wait`.
- Auto-update breaks if the deploy edits a tracked file. Keep server config in
  the external `REALMWEAVE_CONFIG` file, not `backend/config.json`.
- Tests can fail if a stray `backend/data/world_save.json` is auto-loaded; use a
  temp `save_path` in tests.

## Roadmap status
Phases 0-10 done (living village, cognition, economy, quests, divine, perception,
justice, subjective view, props/map, multiplayer). Recent: packaging/installer,
live time control + in-game settings menu.
Recent: deep-but-forgiving economy DONE - a single audited coin path with a JSONL
world/economy ledger, daily rent + wages, and a forgiving relief floor
(economy/ledger.py, economy/finance.py); supply chains DONE - recipes + gather/
refine, local-preferred sourcing with an NPC supplier at a premium
(economy/recipes.py, economy/supply.py); guilds/factions DONE - fighters/thieves/
mages/merchants with rosters, tenure-based ranks, daily dues, and member benefits
(merchant supply discount, fighters deputized for justice pursuit), the gate
guard seeded as the lawful faction, and a join_guild goal (factions/guilds.py).
Save format at v12 with migrations; tests: test_finance/test_supply/test_guilds.
NEXT: inter-agent raw-goods market (gatherers sell surplus to refiners directly,
not just via the NPC premium), guild job boards/contracts, and Phase 9 art polish
(client render quality).
