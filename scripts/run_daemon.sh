#!/data/data/com.termux/files/usr/bin/bash
set -eu
cd "$(dirname "$0")/.."
source .venv/bin/activate
termux-wake-lock
exec python src/daemon.py -c config/users.json -v "$@"
