# Hosting a persistent world (storage-host, AI offloaded)

This is the deployment you want: a small always-on server that **holds the world
and relays it**, while the **AI runs on the players' side** (their local model or
their own API key). NPCs are scripted for now, so the server needs **no GPU and
no LLM**.

## What the server does (and doesn't)

The server does:

- Keep the **authoritative world state** and advance the lightweight, scripted
  simulation (needs, schedules, movement, economy, quests, justice - all plain
  Python, no AI).
- **Persist** the world (autosave) and **relay** it to every connected client
  with interest management.
- Enforce authority (own-character moves, anti-teleport, the log-out safe bubble).

The server does NOT:

- Run any LLM. With AI turned off, villagers still live their routines and the
  economy/quests still run; dialogue uses the built-in canned lines. This is the
  "NPCs are scripted for now" mode.

Players who want rich, model-driven dialogue run the AI themselves (local Ollama
or their own API model - see `docs/MODELS.md`). The heavy compute lives with the
player, not on your host.

## Turn AI off on the host

In `backend/config.json` on the server:

```json
"force_stub": true,
"server": {
  "host": "0.0.0.0",
  "port": 8765,
  "ticks_per_second": 4,
  "autosave_seconds": 60,
  "interest_radius": 24.0,
  "max_players": 16
}
```

`force_stub: true` means zero LLM calls. `host: 0.0.0.0` accepts outside players.

## How big a server? (answer: small)

Because the AI is offloaded, the host is tiny. The current world (a handful of
agents) runs comfortably on the **smallest cloud VM** (about 1 vCPU / 1 GB RAM).
CPU/RAM scale with the number of agents and connected players, **not** with AI.
You only need a big or GPU server if you later choose to run local LLMs on the
host, which this design deliberately avoids.

Rule of thumb: start on the cheapest droplet, watch CPU during peak players, and
resize up only if you actually need to.

## DigitalOcean (or any VPS)

DigitalOcean supports **resizing a droplet** later: you can increase CPU/RAM (a
CPU/RAM-only resize is reversible if you don't grow the disk; growing the disk is
permanent). So starting small and upgrading later is fine - power off, resize in
the control panel, power on. Verify current options in your DO dashboard.

### One-time setup (Ubuntu droplet)

```bash
sudo apt update && sudo apt install -y python3 python3-pip git
git clone https://github.com/sagejw-svg/realmweave
cd realmweave/backend
pip install -r requirements.txt
# edit config.json: force_stub true, host 0.0.0.0 (as above)
python3 run_server.py    # test it, then Ctrl+C and run as a service below
```

### Run 24/7 as a service

`/etc/systemd/system/realmweave.service`:

```ini
[Unit]
Description=Realmweave world server
After=network.target

[Service]
WorkingDirectory=/root/realmweave/backend
ExecStart=/usr/bin/python3 run_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now realmweave
sudo systemctl status realmweave
```

### Quick deploy on an existing Ubuntu droplet (one command)

On the droplet as root, run **only this one line** (do not paste the whole
script). It clones Realmweave, installs it, writes a storage-host config
(AI off), runs it as a service, and sets up **auto-update from GitHub**:

```bash
curl -fsSL https://raw.githubusercontent.com/sagejw-svg/realmweave/main/deploy/dxedge_deploy.sh | sudo bash
```

The server comes up on `ws://<droplet-ip>:8765` immediately (connect the Godot
client, or a locally opened dashboard). A systemd timer pulls `main` every 5
minutes and restarts only when there are new commits, so pushes go live on their
own, no manual redeploy.

For the **https browser dashboards** you need `wss://` (TLS). Add a DNS record
(e.g. `realm.dxedge.net`) and reverse-proxy to `127.0.0.1:8765`:

- If nginx runs **on the host**: use `deploy/realmweave.nginx` + `certbot --nginx`.
- If nginx runs **in Docker** (like the DXEdge stack): add a `server` block for
  `realm.dxedge.net` to that nginx's config proxying to the host (the droplet's
  private IP, or add `extra_hosts: ["host.docker.internal:host-gateway"]` and use
  `host.docker.internal:8765`), mount a cert for the new domain, and reload the
  nginx container. Cleanest of all: once the other site is retired, let Realmweave
  own 80/443 with Caddy (automatic TLS).

### Co-hosting on an existing droplet (e.g. behind nginx)

If your droplet already runs nginx + Let's Encrypt for another site, add a
subdomain (say `realm.example.com`, an A record to the droplet) and reverse-proxy
`wss://` to the Realmweave port. nginx server block:

```nginx
server {
    listen 443 ssl;
    server_name realm.example.com;
    # reuse certbot/Let's Encrypt certs
    ssl_certificate     /etc/letsencrypt/live/realm.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/realm.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }
}
```

`sudo certbot --nginx -d realm.example.com` to issue the cert, then run the
Realmweave server (systemd unit above, or a container). Players connect to
`wss://realm.example.com`. On a small (1 GB) droplet already running another app,
watch memory; a resize to 2 GB gives comfortable headroom for both.

### Secure it with wss:// (TLS)

Browsers and public clients should connect over `wss://`, not raw `ws://`. Put a
reverse proxy in front. With [Caddy](https://caddyserver.com) and a domain:

`/etc/caddy/Caddyfile`:

```
realm.example.com {
    reverse_proxy 127.0.0.1:8765
}
```

Caddy fetches a certificate automatically; players then connect to
`wss://realm.example.com`. (nginx works too, with a `proxy_pass` + `Upgrade`
headers block.)

### Back up the world

The world is a single JSON file (`backend/data/world_save.json`). Back it up on a
schedule (cron + copy to object storage). That file plus the code is the entire
world; nothing else is stateful.

## Firewall

Open the port you serve on (8765 for direct `ws://`, or 80/443 if using Caddy for
`wss://`). On DigitalOcean, use a Cloud Firewall or `ufw`.

## Roadmap note

Right now "AI offloaded to players" means scripted dialogue on the host and
optional model dialogue on the client. A future step is a clean **client-side
dialogue channel**: the host emits a dialogue *request*, and the player's client
answers it with their local/API model and shares the line back. The seam already
exists (the pluggable API backend); this is a Phase 11 item.
