# How to run Realmweave

There are three ways to experience it today, from zero-install to the full
interactive client. On Windows the Python launcher is usually `py` instead of
`python`.

## 1. Just look (no install)

Open the published pages in any browser - they show a demo village with no setup:

- Map: https://sagejw-svg.github.io/realmweave/map.html
- Through their eyes: https://sagejw-svg.github.io/realmweave/eyes.html
- World dashboard: https://sagejw-svg.github.io/realmweave/
- Dev status: https://sagejw-svg.github.io/realmweave/dev.html

For **live** data instead of the demo, start the server (below) and open the same
pages from your local `docs/` folder, or point their URL bar at your server.

## 2. Watch the world run (no graphics client)

Only needs Python 3.10+.

```bash
git clone https://github.com/sagejw-svg/realmweave
cd realmweave/backend
python run_headless.py --ticks 200 --stub
```

You'll see the village live in your terminal: villagers pursuing their own aims,
trading, taking quests, and more. `--stub` runs without any GPU. Fun flags:
`--say "Is the Stag open?"`, `--kill bram`, `--save data/save.json`,
`--load data/save.json`.

## 3. Play the interactive client (the actual game)

This is the Godot client. You need Python and Godot.

**Step 1 - start the server**

```bash
cd realmweave/backend
pip install -r requirements.txt      # installs 'websockets'
python run_server.py                 # serves ws://127.0.0.1:8765
```

Leave it running. To play the world with the AI villagers actually talking,
install [Ollama](https://ollama.com) and pull a model (see the README); otherwise
set `"force_stub": true` in `backend/config.json` to play GPU-free with canned
dialogue.

**Step 2 - open the client**

1. Install **Godot 4.3+** (standard build) from https://godotengine.org.
2. In Godot, "Import" and open `realmweave/godot_client/project.godot`.
3. Press **Play** (F5). It connects to your server and drops you into Oakhollow.

**Controls**

- **WASD** - walk your character.
- **Enter** - focus the chat box; type and press Enter again to speak to the
  nearest villager. They remember what you say.
- **`/suggest <text>`** in the chat - whisper a divine suggestion to the nearest
  villager (as the god). They may heed it or refuse.
- **O** - see the world through the eyes of the nearest villager (press again to
  stop). A richer version is the browser `eyes.html` page.

> The in-game art is currently placeholder (drawn shapes and labels). Real CC0
> sprite tiles slot in on top; see `docs/ART.md`.

## Multiplayer / hosting

The server is authoritative and supports many players at once. To host for
others, in `backend/config.json` set:

```json
"server": { "host": "0.0.0.0", "port": 8765, "interest_radius": 24.0, "max_players": 16 }
```

Run `python run_server.py`, open the port on your firewall/router, and others
point their client (or the browser pages) at `ws://YOUR_IP:8765`. For anything
public, put it behind a `wss://` (TLS) reverse proxy.

**Logging out is safe.** When you disconnect, your character enters a protected
resting bubble: their coin, position, and active quest are preserved and they
cannot be robbed, harmed, or starve while away. Rejoin with the same name to
resume exactly where you left off (this even survives a server restart).
