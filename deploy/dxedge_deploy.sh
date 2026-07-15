#!/usr/bin/env bash
# Deploy the Realmweave world server on an Ubuntu droplet (storage-host mode:
# the server holds/relays the world with AI OFF and scripted NPCs; players run
# their own AI). Independent of anything else on the box.
#
# Run on the droplet as root:
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

# dependency (websockets). Prefer the distro package; fall back to pip.
apt-get install -y python3-websockets \
  || pip3 install --break-system-packages websockets \
  || pip3 install websockets

# storage-host config: AI off (scripted NPCs); bind localhost, nginx does TLS
python3 - "$APP_DIR/backend/config.json" <<'PY'
import json, sys
p = sys.argv[1]
cfg = json.load(open(p))
cfg["force_stub"] = True
cfg["server"]["host"] = "127.0.0.1"
cfg["server"]["port"] = 8765
cfg["server"]["max_players"] = 32
json.dump(cfg, open(p, "w"), indent=2)
print("configured", p)
PY

# run as a service, restart on crash / reboot
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

systemctl daemon-reload
systemctl enable --now realmweave
sleep 2
systemctl --no-pager status realmweave | head -n 8 || true

echo
echo "Realmweave is running on 127.0.0.1:${PORT} (AI off / scripted NPCs)."
echo "Next steps:"
echo "  1. DNS: add an A record (e.g. realm.dxedge.net) -> this droplet's IP."
echo "  2. nginx: copy deploy/realmweave.nginx to /etc/nginx/sites-available/realmweave,"
echo "     edit the server_name, then:"
echo "       ln -s /etc/nginx/sites-available/realmweave /etc/nginx/sites-enabled/"
echo "       certbot --nginx -d realm.dxedge.net"
echo "       systemctl reload nginx"
echo "  3. Players / dashboards connect to  wss://realm.dxedge.net"
echo
echo "Update later with:  cd $APP_DIR && git pull && systemctl restart realmweave"
