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
NEXT: deep-but-forgiving economy + guilds/factions (thieves/fighters/mage guilds,
police/guards, supply chains with NPC-fallback-at-a-premium, rent/wages, a JSONL
world/economy ledger log).
