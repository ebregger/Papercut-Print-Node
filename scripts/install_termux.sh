#!/data/data/com.termux/files/usr/bin/bash
# One-shot Termux bootstrap for the PaperCut print node.
set -euo pipefail

PKG="com.termux"
TERMUX_HOME="/data/data/${PKG}/files/home"
PROJECT="${TERMUX_HOME}/mtu-print-node"

echo "==> Updating Termux packages"
pkg update -y
pkg upgrade -y

echo "==> Installing system dependencies"
pkg install -y \
  python \
  ghostscript \
  git \
  termux-api \
  cups \
  openssh

echo "==> Creating Python virtual environment"
python -m venv "${PROJECT}/.venv"
source "${PROJECT}/.venv/bin/activate"
pip install --upgrade pip wheel
pip install -r "${PROJECT}/requirements.txt"

echo "==> Preparing spool and config directories"
mkdir -p "${PROJECT}/spool" "${PROJECT}/config" "${PROJECT}/logs"
if [[ ! -f "${PROJECT}/config/users.json" ]]; then
  cp "${PROJECT}/config/users.json.example" "${PROJECT}/config/users.json"
fi
if [[ ! -f "${PROJECT}/config/credentials.json" ]]; then
  bash "${PROJECT}/scripts/init_credentials.sh"
fi

echo "==> Installing termux-services unit (optional)"
mkdir -p "${TERMUX_HOME}/.termux/boot"
cat > "${TERMUX_HOME}/.termux/boot/mtu-print-node" <<'BOOT'
#!/data/data/com.termux/files/usr/bin/bash
sleep 30
cd ~/mtu-print-node
source .venv/bin/activate
termux-wake-lock
nohup bash scripts/run_daemon.sh \
  >> logs/daemon.log 2>&1 &
BOOT
chmod +x "${TERMUX_HOME}/.termux/boot/mtu-print-node"

echo "==> Done. Next steps:"
echo "  1. Connect the VPN on the phone (OpenConnect / Cisco Secure Client)"
echo "  2. Edit ~/mtu-print-node/config/credentials.json (chmod 600)"
echo "  3. Install/start the multicast helper APK from a computer (see README.md)"
echo "  4. Run: bash scripts/run_daemon.sh"
