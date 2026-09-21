# MTU Headless Print Node (Pixel 3 / Termux)

Forward local IPP print jobs from your LAN to Michigan Tech PaperCut Web Print (`printing.mtu.edu`) over the MTU VPN. One virtual printer per user; jobs auto-route to `husky-bw` or `husky-color`.

## Architecture

```
[Mac/Win/Linux] --IPP/mDNS--> [Pixel 3 Termux] --HTTPS--> [printing.mtu.edu Web Print]
                                      |
                               Ghostscript inkcov
                               (color detection)
```

## Quick start (from your PC via ADB)

### 1. Prepare the Pixel

```powershell
# Enable developer options + USB debugging on the phone first.
adb devices

# Install Termux from F-Droid (not Play Store build):
# https://f-droid.org/packages/com.termux/

# Grant storage if you sideload files manually (optional)
adb shell pm grant com.termux android.permission.READ_EXTERNAL_STORAGE
```

### 2. Push the project

The F-Droid Termux build is **not debuggable**, so `run-as com.termux` will fail. Use shared storage instead:

```powershell
# From your PC — push to Downloads
adb push C:\Users\Edison\Projects\mtu-print-node /sdcard/Download/mtu-print-node
```

Then **on the phone in Termux**:

```bash
termux-setup-storage          # grant storage permission (one-time)
cp -r ~/storage/downloads/mtu-print-node ~/
```

Or clone directly inside Termux (no ADB copy needed):

```bash
adb shell am start -n com.termux/.HomeActivity
# In Termux:
pkg install git -y
git clone <your-repo-url> ~/mtu-print-node
```

### 3. Probe Web Print **before** installing anything else

This architecture only works if MTU has PaperCut **Web Print** enabled. Many schools disable it and force the desktop client for billing popups.

**Step A — public check (no credentials, works off-campus):**

```bash
cd ~/mtu-print-node
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/probe_wsd.py --public-only
```

**Step B — authenticated discovery (requires MTU VPN + credentials file):**

```bash
# After filling config/credentials.json:
# Or explicitly: --account default
```

Look for `Submit a Job found: True`. If discovery reports Web Print is **not** detected, stop here — the scraper path won't work and you'll need to pivot (desktop PaperCut client, Mobility Print, or LPR with the background client).

Debug HTML snapshots land in `logs/papercut-probe/`.

### 4. Install dependencies (inside Termux)

```bash
bash ~/mtu-print-node/scripts/install_termux.sh
```

Or interactively:

```bash
pkg update && pkg upgrade -y
pkg install python ghostscript git termux-api -y
cd ~/mtu-print-node
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/users.json.example config/users.json
```

### 5. Configure users and credentials

**Printer layout** — edit `~/mtu-print-node/config/users.json` (no passwords here):

```json
{
  "users": [{
    "id": "alice",
    "credential_id": "default",
    "display_name": "MTU Print - Alice",
    "queues": { "bw": "husky-bw", "color": "husky-color" }
  }]
}
```

**MTU login** — stored separately in a restricted secrets file:

```bash
bash scripts/init_credentials.sh
# Creates config/credentials.json with mode 600
```

Edit `config/credentials.json`:

```json
{
  "accounts": {
    "default": {
      "username": "your_mtu_username",
      "password": "your_mtu_password"
    }
  }
}
```

Security properties:
- `credentials.json` is **gitignored** — never committed
- Daemon **refuses to start** if the file is world/group-readable (`chmod 600` required on Termux)
- Passwords are **never logged** and must not appear in `users.json`
- Multiple accounts: add `"bob": { ... }` and set `"credential_id": "bob"` per printer user

Lock it down after editing:

```bash
chmod 600 config/credentials.json
```

### 6. Connect MTU VPN on the phone

Install **OpenConnect** or **Cisco Secure Client**, connect to MTU VPN, and leave it on. Termux traffic routes through Android's active VPN automatically.

Verify from Termux:

```bash
curl -I https://printing.mtu.edu/
```

### 7. Full upload probe (optional, after discovery passes)

```bash
```

### 8. Start the daemon

```bash
bash scripts/run_daemon.sh
# Or with termux-wake-lock + boot script (see install_termux.sh)
```

### 9. Add printers on client machines

Discover via Bonjour (`MTU Print - Alice`) or add manually:

| User  | URL |
|-------|-----|
| Alice | `ipp://<pixel-ip>:8631/printer` |
| Bob   | `ipp://<pixel-ip>:8632/printer` |

Use **IPP Everywhere** or **Generic IPP Printer** driver. Clients send PDF over IPP.

## Files

| File | Purpose |
|------|---------|
| `src/color_detect.py` | Ghostscript `inkcov` color analysis |
| `src/ipp_behaviour.py` | ippserver hook per user |
| `src/daemon.py` | Multi-printer IPP + mDNS daemon |

## Notes

- **Web Print may be disabled** — always run `--discover` before deploying the daemon.
- PaperCut has no public upload API; the scraper replays browser forms including hidden CSRF fields.
- Web Print only accepts PDF/images; IPP clients normally emit PDF automatically.
- Keep the Pixel plugged in; use `termux-wake-lock` to avoid sleep kills.
- Lock down `config/credentials.json` (`chmod 600`). Do not store passwords in `users.json`.