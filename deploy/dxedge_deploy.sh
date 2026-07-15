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
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO" "$APP_DIR"
fi
git config --global --add safe.directory "$APP_DIR" || true

# dependency (websockets): distro package, else pip
apt-get install -y python3-websockets \
  || pip3 install --break-system-packages websockets \
  || pip3 install websockets

# storage-host config: AI off (scripted NPCs); listen on all interfaces
python3 - "$APP_DIR/backend/config.json" <<'PY'
import json, sys
p = sys.argv[1]
cfg = json.load(open(p))
cfg["force_stub"] = True
cfg["server"]["host"] = "0.0.0.0"
cfg["server"]["port"] = 8765
cfg["server"]["max_players"] = 32
json.dump(cfg, open(p, "w"), indent=2)
print("configured", p)
PY

# main service (restart on crash / reboot)
cat >/etc/systemd/system/realmweave.service <<EOF
[Unit]
Description=Realmweave world server
After=network.target

[Service]
WorkingDirectory=$APP_DIR/backend
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
echo
echo "Connect the Godot client (or a locally opened dashboard) to that ws:// address."
echo "For https browser dashboards you need wss:// - see docs/HOSTING.md for the"
echo "reverse-proxy options (route through the site's nginx, or use Caddy once the"
echo "other site is retired)."
