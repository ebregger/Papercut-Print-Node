#!/data/data/com.termux/files/usr/bin/bash
# Create a restricted credentials file for MTU PaperCut logins.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXAMPLE="${ROOT}/config/credentials.json.example"
TARGET="${ROOT}/config/credentials.json"

if [[ -f "${TARGET}" ]]; then
  echo "Credentials file already exists: ${TARGET}"
  echo "Edit it directly, then ensure: chmod 600 ${TARGET}"
  exit 0
fi

cp "${EXAMPLE}" "${TARGET}"
chmod 600 "${TARGET}"
echo "Created ${TARGET} (mode 600)"
echo ""
echo "Edit that file and replace YOUR_MTU_USERNAME / PASTE_YOUR_MTU_PASSWORD_HERE"
echo "Then run the Web Print probe:"
echo "  python src/probe_papercut.py --discover --account default"
