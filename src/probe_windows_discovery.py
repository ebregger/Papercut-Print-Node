"""Trigger Windows device discovery and look for the MTU WSD printer."""

import subprocess
import sys
import time


def run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    return (result.stdout or "") + (result.stderr or "")


def main() -> int:
    print("Restarting Function Discovery services...")
    print(
        run_ps(
            "Restart-Service FDResPub,fdPHost -Force -ErrorAction SilentlyContinue; "
            "'services restarted'"
        )
    )

    print("Scanning for PnP devices (may need admin for pnputil)...")
    print(run_ps("pnputil /scan-devices 2>&1 | Select-Object -First 3"))

    time.sleep(5)

    query = (
        "Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | "
        "Where-Object { $_.FriendlyName -like '*MTU*' -or $_.FriendlyName -like '*Edison*' "
        "-or $_.InstanceId -like '*PRINTENUM*' -or $_.InstanceId -like '*WSD*' } | "
        "Select-Object FriendlyName,Class,InstanceId,Status | Format-Table -AutoSize | Out-String -Width 200"
    )
    devices = run_ps(query)
    print("Matching PnP devices:")
    print(devices.strip() or "(none)")

    printers = run_ps(
        "Get-Printer -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Name -like '*MTU*' -or $_.Name -like '*Edison*' } | "
        "Select-Object Name,PortName,DriverName | Format-Table -AutoSize | Out-String -Width 200"
    )
    print("Installed printers:")
    print(printers.strip() or "(none)")

    if "MTU" in devices or "Edison" in devices:
        print("WINDOWS_PNP_OK")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
