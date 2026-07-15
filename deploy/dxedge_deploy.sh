#!/usr/bin/env bash
# Deploy the Realmweave world server on an Ubuntu droplet (storage-host mode:
# the server holds/relays the world with AI OFF and scripted NPCs; players run
# their own AI). Runs as its own systemd service and AUTO-UPDATES from GitHub.
# Independent of anything else on the box (e.g. a Dockerized site).
#
# Run on the droplet as root (do NOT paste the whole file; run this one line):
#   curl -fsSL https://raw.githubusercontent.com/sagejw-svg/realmweave/main/deploy/dxedge_deploy.sh | sudo bash
set -euo pipefail

APP_DIR=/opt/realmweave
REPO=https://github.com/sagejw-svg/realmweave
PORT=8765

echo "== Realmweave deploy =="
apt-get update -y
apt-get install -y python3 python3-pip git

# code
git config --global --add safe.directory "$APP_DIR" || true
if [ -d "$APP_DIR/.git" ]; then
  # discard any local edits from older deploys so the pull can fast-forward
  git -C "$APP_DIR" checkout -- . 2>/dev/null || true
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO" "$APP_DIR"
fi

# dependency (websockets): distro package, else pip
apt-get install -y python3-websockets \
  || pip3 install --break-system-packages websockets \
  || pip3 install websockets

# storage-host config lives OUTSIDE the repo so `git pull` (auto-update) never
# conflicts. The server reads it via $REALMWEAVE_CONFIG (set in the unit below).
# AI off (scripted NPCs), listen on all interfaces, gentler world clock, and the
# save file lives in /var/lib so the working tree stays pristine.
mkdir -p /etc/realmweave /var/lib/realmweave
cat >/etc/realmweave/config.json <<'JSON'
{
  "force_stub": true,
  "sim":    {"minutes_per_tick": 2},
  "server": {"host": "0.0.0.0", "port": 8765, "ticks_per_second": 1,
             "max_players": 32, "save_path": "/var/lib/realmweave/world_save.json"}
}
JSON
echo "wrote /etc/realmweave/config.json"

# main service (restart on crash / reboot)
cat >/etc/systemd/system/realmweave.service <<EOF
[Unit]
Description=Realmweave world server
After=network.target

[Service]
WorkingDirectory=$APP_DIR/backend
Environment=REALMWEAVE_CONFIG=/etc/realmweave/config.json
ExecStart=/usr/bin/python3 run_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# auto-update: pull main and restart only if there are new commits
cat >/usr/local/bin/realmweave-update.sh <<EOF
#!/usr/bin/env bash
set -e
cd "$APP_DIR"
before=\$(git rev-parse HEAD)
git pull --ff-only origin main || exit 0
after=\$(git rev-parse HEAD)
if [ "\$before" != "\$after" ]; then
  systemctl restart realmweave
  echo "realmweave updated \$before -> \$after"
fi
EOF
chmod +x /usr/local/bin/realmweave-update.sh

cat >/etc/systemd/system/realmweave-update.service <<EOF
[Unit]
Description=Realmweave auto-update
[Service]
Type=oneshot
ExecStart=/usr/local/bin/realmweave-update.sh
EOF

cat >/etc/systemd/system/realmweave-update.timer <<EOF
[Unit]
Description=Realmweave auto-update timer (every 5 min)
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now realmweave
systemctl enable --now realmweave-update.timer

# open the port if ufw is active (site's Docker nginx keeps 80/443)
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw allow ${PORT}/tcp || true
fi

sleep 2
systemctl --no-pager status realmweave | head -n 6 || true
IP=$(hostname -I | awk '{print $1}')
echo
echo "Realmweave is LIVE on  ws://${IP}:${PORT}   (AI off / scripted NPCs)"
echo "Auto-updates from GitHub every 5 minutes."
echo "World clock: ~2 in-game minutes per real second (a day every ~12 min)."
echo "Tune it in /etc/realmweave/config.json (sim.minutes_per_tick, server.ticks_per_second)"
echo "then: systemctl restart realmweave"
echo
echo "Connect the Godot client (or a locally opened dashboard) to that ws:// address."
echo "For https browser dashboards you need wss:// - see docs/HOSTING.md for the"
echo "reverse-proxy options (route through the site's nginx, or use Caddy once the"
echo "other site is retired)."
