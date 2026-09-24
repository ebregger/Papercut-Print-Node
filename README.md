# Michigan Tech PaperCut Print Node

A headless print server running on an Android device (Pixel 3 with Termux) that receives local IPP print jobs over Wi-Fi and securely forwards PDF documents to Michigan Technological University's PaperCut Mobility Print service over the campus VPN.

Windows 10/11 automatically discovers the printer over mDNS/DNS-SD (`_ipp._tcp.local.`) using the standard **Microsoft IPP Class Driver**, allowing seamless printing from any application without installing proprietary drivers or desktop billing popups.

---

## Architecture Overview

```
[Windows / macOS Client]
        │
        │  IPP 2.0 Print-Job (PDF) via LAN
        │  mDNS Discovery (_ipp._tcp.local.)
        ▼
[Pixel 3 (Termux)]
  ├── Android Multicast Helper (Foreground service holding WifiManager.MulticastLock)
  ├── DNS-SD Beacon (src/advertise_ipp_frontend.py on wlan0:5353)
  ├── CUPS ippeveprinter Front-End (Port 8632 /ipp/print)
  │       │
  │       ▼ (Local socket relay: 127.0.0.1:8631)
  └── Python PaperCut Daemon (src/daemon.py)
          │
          │  HTTPS / IPP over MTU VPN (tun0)
          ▼
[Michigan Tech PaperCut Mobility Print] (printing.mtu.edu)
          │
          ▼
   [Campus Printers (husky-bw / husky-color)]
```

### Why the Android Multicast Helper is Needed
Android's Wi-Fi driver aggressively filters incoming multicast packets to conserve battery unless an application explicitly requests and holds a `WifiManager.MulticastLock`. 
The included `android/multicast-helper` app runs as a minimal foreground service on the phone, preventing Android from dropping mDNS multicast queries (`UDP 5353`) and enabling computers on the LAN to discover the printer.

---

## Quick Start & Setup Guide

### 1. Prepare the Pixel 3 (Termux)
1. Enable **Developer Options** and **USB Debugging** on the Pixel.
2. Install **Termux** from [F-Droid](https://f-droid.org/packages/com.termux/) (do not use the obsolete Google Play version).
3. Connect the phone to your MTU campus VPN (e.g. Cisco Secure Client or OpenConnect) and keep it active.

### 2. Build and Install the Multicast Helper
From your Windows PC with Android SDK build-tools and JDK:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_multicast_helper.ps1
adb install -r android/multicast-helper/build/multicast-helper.apk
adb shell am start -n edu.mtu.printnode.multicast/.MainActivity
```
The helper will display a persistent notification confirming that the multicast lock is held.

### 3. Bootstrap Termux Dependencies
Push the repository to the device or clone it directly inside Termux:

```bash
# Inside Termux on the Pixel:
bash scripts/install_termux.sh
```
This updates packages, installs CUPS, Ghostscript, Python, OpenSSH, sets up the Python virtual environment (`.venv`), and creates default configuration templates.

### 4. Configure Users and Credentials
Initialize your credentials file:

```bash
bash scripts/init_credentials.sh
```

1. **`config/credentials.json`** (strict `chmod 600` permissions; gitignored):
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
2. **`config/users.json`**:
   ```json
   {
     "settings": {
       "base_port": 8631,
       "frontend_port": 8632
     },
     "users": [
       {
         "id": "edison",
         "credential_id": "default",
         "display_name": "Papercut - Edison",
         "queues": { "bw": "husky-bw", "color": "husky-color" }
       }
     ]
   }
   ```

### 5. Start the Print Node Daemon
Inside Termux:

```bash
bash scripts/run_daemon.sh
```
*Tip: Install the `Termux:Boot` companion app if you want `~/.termux/boot/mtu-print-node` to start the daemon automatically upon device reboot.*

---

## Connecting Clients (Windows Setup)

### Automatic Discovery (Recommended)
1. Open Windows **Settings > Bluetooth & devices > Printers & scanners**.
2. Click **Add device**.
3. Windows will discover `Papercut - Edison` via mDNS and automatically configure it with the **Microsoft IPP Class Driver**.
4. Print a test page from Windows to verify end-to-end delivery through PaperCut.

### Manual Setup (Fallback)
If local Wi-Fi client isolation blocks mDNS discovery:
- Run the included PowerShell helper from Windows:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts/add_windows_ipp_printer.ps1 -PixelIp <pixel-wifi-ip> -Port 8632 -PrinterName "Papercut - Edison"
  ```
- Or navigate to **Add manually > Add a printer using an IP address or hostname**, choose **IPP Device**, and enter:
  `ipp://<pixel-wifi-ip>:8632/ipp/print`

---

## Project Structure

| Path | Description |
| :--- | :--- |
| `src/daemon.py` | Core multi-user IPP backend daemon managing local queues and forwarding |
| `src/advertise_ipp_frontend.py` | DNS-SD beacon advertising `_ipp._tcp.local.` on the phone's Wi-Fi interface |
| `src/mdns_service.py` | Low-level mDNS responder implementation |
| `src/mobility_print_client.py` | PaperCut Mobility Print IPP client for job submission |
| `src/color_detect.py` | Ghostscript ink coverage analysis for auto-routing color vs monochrome |
| `src/ipp_util.py` | IPP attribute parsing, normalization, and sides extraction |
| `android/multicast-helper/` | Native Android foreground service holding `WifiManager.MulticastLock` |
| `scripts/run_daemon.sh` | Orchestration script launching backend, `ippeveprinter`, and mDNS beacon |
| `scripts/install_termux.sh` | Complete Termux environment bootstrap script |
| `scripts/add_windows_ipp_printer.ps1`| PowerShell automation script for manual Windows printer mapping |

---

## Roadmap & Next Steps

1. **Color Detection & Smart Queue Routing**
   - Integrate `src/color_detect.py` into the live job processing pipeline to inspect Ghostscript ink coverage (`inkcov`) per page.
   - Automatically route color documents to `husky-color` and black-and-white documents to `husky-bw` without requiring separate printer endpoints.

2. **Two-Sided (Duplex) Printing Support**
   - Pass through IPP sides attributes (`one-sided`, `two-sided-long-edge`, `two-sided-short-edge`) into the outbound Mobility Print IPP request payload.
   - Verify duplex alignment on physical MTU campus hardware.

3. **Better Naming & Multi-User Identity**
   - Refine printer naming conventions and dynamic display names across mDNS records to distinguish between distinct users and multi-user configurations cleanly.
   - Support multiple independent user queues running on dedicated ports with per-user authentication profiles.
