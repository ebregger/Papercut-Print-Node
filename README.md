# PaperCut Print Node

> **Status: experimental.** This project receives local IPP print jobs on a Pixel 3 running Termux and forwards PDF jobs to PaperCut Mobility Print. On September 23, 2026, Windows installed the printer with Microsoft IPP Class Driver and sent a test page through the Pixel; PaperCut accepted the job. Phone client setup and restart recovery remain unverified.

The current code targets Mobility Print, not PaperCut Web Print. It includes an IPP server, print routing, configuration examples, and discovery probes.

## Local discovery on the Pixel 3

The startup script runs the Python PaperCut backend and a CUPS `ippeveprinter` IPP 2.0 front end. The front end accepts PDF and passes it to the backend over a localhost socket. A separate DNS-SD beacon advertises the front end on the phone's `wlan0` address while the phone keeps its VPN for PaperCut. WSD is disabled because its Windows device listing did not produce a usable print queue. The front end has not been certified for AirPrint, Mopria, or IPP Everywhere.

Android filters incoming Wi-Fi multicast packets unless an app holds a multicast lock. Build and install the small foreground helper once from a Windows computer with Android SDK build tools and Android Studio's JDK:

```powershell
powershell -File scripts/build_multicast_helper.ps1
adb install -r android/multicast-helper/build/multicast-helper.apk
adb shell am start -n edu.mtu.printnode.multicast/.MainActivity
```

The helper shows a persistent notification and includes a boot receiver; its boot behavior has not yet been tested. Start the Python daemon in Termux with `bash scripts/run_daemon.sh`. The Termux:Boot app is needed if you want the existing boot script to start the Python daemon after a phone restart.

On a computer on the same LAN, browse `_ipp._tcp.local.` and confirm that the configured display name (for example, `Papercut - Edison`) resolves to the Pixel's Wi-Fi IP. The IPP endpoint is `ipp://<wifi-ip>:<frontend-port>/ipp/print` (default frontend port 8632 for one configured user). On Windows, use Settings > Printers & scanners > Add device > Add manually > Add a printer using an IP address or hostname, choose **IPP Device**, and enter the full URL if automatic discovery does not install it. The network must allow mDNS multicast (UDP 5353) and IPP TCP; isolated guest Wi-Fi will prevent discovery.

## Before using it

- `config/credentials.json.example` contains placeholders. The real `config/credentials.json` is gitignored.
- The example configuration currently uses HTTP for Mobility Print and the client sends credentials with Basic authentication. Do not use real credentials until a secure connection is confirmed.
- Native setup on iOS, Android, and macOS and restart recovery still need testing. Windows setup and a test job through PaperCut succeeded.

This repository records an in-progress prototype and is not a ready-to-install printing service.
