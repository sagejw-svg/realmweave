#!/usr/bin/env bash
# Headless screenshot of the Realmweave Godot client, rendered against a
# GPU-free stub server. For a plain Linux sandbox / CI (not Windows).
#
# Usage:  tools/screenshot.sh [OUT.png] [--weather=clear] [--hour=13] [--delay=3]
# Env:    GODOT=/path/to/godot to reuse an existing binary.
set -euo pipefail

OUT="${1:-shot.png}"; [ $# -gt 0 ] && shift || true
WEATHER=clear; HOUR=13; DELAY=3
for a in "$@"; do case "$a" in
  --weather=*) WEATHER="${a#*=}";;
  --hour=*)    HOUR="${a#*=}";;
  --delay=*)   DELAY="${a#*=}";;
esac; done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GODOT="${GODOT:-/tmp/godot}"

# Godot 4.3 (downloaded once if absent)
if [ ! -x "$GODOT" ]; then
  echo "fetching Godot 4.3..."
  curl -sL -o /tmp/godot.zip \
    https://github.com/godotengine/godot/releases/download/4.3-stable/Godot_v4.3-stable_linux.x86_64.zip
  (cd /tmp && unzip -oq godot.zip && mv Godot_v4.3-stable_linux.x86_64 "$GODOT" && chmod +x "$GODOT")
fi
python3 -c 'import websockets' 2>/dev/null || pip install --break-system-packages -q websockets

# Stub config (no Ollama, no GPU), kept outside the repo via REALMWEAVE_CONFIG.
CFG=/tmp/rw_stub_config.json
cat > "$CFG" <<'JSON'
{"force_stub": true,
 "models": {"reflex": "", "dialogue": "", "narrative": ""},
 "api": {"enabled": false, "provider": "anthropic", "model": "", "api_key_env": "ANTHROPIC_API_KEY", "tiers": ["narrative"]},
 "sim": {"minutes_per_tick": 10, "seed": 7},
 "server": {"host": "127.0.0.1", "port": 8765, "broadcast_hz": 4, "ticks_per_second": 8, "save_path": "/tmp/rw_stub_save.json"}}
JSON
rm -f /tmp/rw_stub_save.json
export REALMWEAVE_CONFIG="$CFG"

( cd "$ROOT/backend" && python3 run_server.py >/tmp/rw_server.log 2>&1 ) &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
for i in $(seq 1 20); do
  python3 -c "import socket,sys;s=socket.socket();s.settimeout(1);sys.exit(0 if s.connect_ex(('127.0.0.1',8765))==0 else 1)" && break
  sleep 0.4
done

export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
# import once (safe if already imported), then capture
xvfb-run -a -s "-screen 0 1024x720x24" "$GODOT" --path "$ROOT/godot_client" \
  --rendering-driver opengl3 --import >/tmp/rw_import.log 2>&1 || true
xvfb-run -a -s "-screen 0 1024x720x24" "$GODOT" --path "$ROOT/godot_client" \
  --rendering-driver opengl3 -- \
  --capture="$OUT" --capture-delay="$DELAY" --weather="$WEATHER" --hour="$HOUR" --player=Tester \
  >/tmp/rw_capture.log 2>&1

echo "wrote $OUT"
