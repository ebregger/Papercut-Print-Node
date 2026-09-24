#!/data/data/com.termux/files/usr/bin/bash
set -eu
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PATH="/data/data/com.termux/files/usr/bin:$PATH"
PYTHON="$PWD/.venv/bin/python"
termux-wake-lock

readarray -t printer_config < <(python - <<'PY'
import json
from pathlib import Path
config = json.loads(Path("config/users.json").read_text())
settings = config.get("settings", {})
users = config["users"]
base_port = int(settings.get("base_port", 8631))
print(base_port)
print(int(settings.get("frontend_port", base_port + len(users))))
print(users[0].get("display_name", f"Papercut - {users[0]['id']}"))
PY
)
backend_port="${printer_config[0]}"
frontend_port="${printer_config[1]}"
printer_name="${printer_config[2]}"

mkdir -p logs/ippeve-spool
"$PYTHON" src/daemon.py -c config/users.json --no-mdns --no-wsd -v "$@" &
daemon_pid=$!
/data/data/com.termux/files/usr/bin/ippeveprinter -r off -s 10,10 -f application/pdf -F application/pdf \
  -c /data/data/com.termux/files/usr/bin/cat \
  -D "socket://127.0.0.1:${backend_port}" \
  -d "$PWD/logs/ippeve-spool" -p "$frontend_port" \
  "Papercut - Edison" &
frontend_pid=$!
"$PYTHON" src/advertise_ipp_frontend.py \
  --name "$printer_name" --port "$frontend_port" \
  --path ipp/print &
beacon_pid=$!

cleanup() {
  kill "$beacon_pid" "$frontend_pid" "$daemon_pid" 2>/dev/null || true
  wait "$beacon_pid" "$frontend_pid" "$daemon_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
wait -n "$daemon_pid" "$frontend_pid" "$beacon_pid"
