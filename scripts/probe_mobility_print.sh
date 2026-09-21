#!/data/data/com.termux/files/usr/bin/bash
# Probe MTU PaperCut Mobility Print ports from Termux (requires MTU VPN).
set -euo pipefail

HOST="${1:-print.mtu.edu}"
TIMEOUT="${2:-5}"

echo "=== Mobility Print probe: ${HOST} ==="
echo "VPN should be connected on the phone before running this."
echo ""

probe() {
  local label="$1"
  shift
  echo ">> ${label}"
  if output="$("$@" 2>&1)"; then
    echo "${output}"
    if echo "${output}" | head -1 | grep -qE 'HTTP/[0-9.]+ 200'; then
      echo "   *** Mobility Print responded with HTTP 200 ***"
      return 0
    fi
    if echo "${output}" | head -1 | grep -qE 'HTTP/[0-9.]+'; then
      echo "   (got a response — note status above)"
      return 0
    fi
  else
    echo "${output}"
    echo "   (failed — timeout, refused, or unreachable)"
    return 1
  fi
}

http_ok=0
https_ok=0
probe "HTTP  :9163/printers (GET)" curl -m "${TIMEOUT}" -sS -I "http://${HOST}:9163/printers" && http_ok=1 || true
echo ""
probe "HTTPS :9164/printers (GET)" curl -m "${TIMEOUT}" -sS -k -I "https://${HOST}:9164/printers" && https_ok=1 || true

echo ""
if [[ "${http_ok}" -eq 1 || "${https_ok}" -eq 1 ]]; then
  echo "Result: Mobility Print ports responded. Next step: rewrite handoff to Mobility Print API."
  exit 0
fi
echo "Result: No response on 9163/9164 — firewall closed or Mobility Print not installed."
exit 1
