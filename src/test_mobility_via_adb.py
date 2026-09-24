"""Run Mobility Print IPP test via Pixel adb curl (VPN required on phone)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from credentials import get_credentials
from mobility_print_client import build_print_job_request, parse_ipp_status
from probe_mobility_print import MINIMAL_PDF

IPP_STATUS_SUCCESSFUL_OK = 0x0000


def main() -> int:
  creds = get_credentials("Edison")
  body = build_print_job_request(
    printer_uri="ipp://print.mtu.edu:9163/printers/husky-bw",
    pdf_data=MINIMAL_PDF,
    requesting_user_name=creds.username,
    job_name="papercut-probe-test",
  )
  root = Path(__file__).resolve().parent.parent
  ipp_path = root / "logs" / "test.ipp"
  resp_path = root / "logs" / "ipp-response.bin"
  ipp_path.parent.mkdir(parents=True, exist_ok=True)
  ipp_path.write_bytes(body)

  subprocess.run(["adb", "push", str(ipp_path), "/sdcard/test.ipp"], check=True)
  curl_cmd = (
    "curl -m 30 -sS "
    f"-u {creds.username}:{creds.password} "
    "-H 'Content-Type: application/ipp' "
    "--data-binary @/sdcard/test.ipp "
    "-o /sdcard/ipp-response.bin -w HTTP_CODE:%{http_code} "
    "http://print.mtu.edu:9163/printers/husky-bw"
  )
  result = subprocess.run(
    ["adb", "shell", curl_cmd], capture_output=True, text=True, check=False
  )
  print(result.stdout.strip() or result.stderr.strip())
  subprocess.run(
    ["adb", "pull", "/sdcard/ipp-response.bin", str(resp_path)], check=False
  )
  if not resp_path.is_file():
    print("No response file pulled")
    return 1
  data = resp_path.read_bytes()
  if not data:
    print("Empty IPP response")
    return 1
  status, req_id = parse_ipp_status(data)
  print(f"IPP status: 0x{status:04x}, request-id: {req_id}")
  return 0 if status == IPP_STATUS_SUCCESSFUL_OK else 1


if __name__ == "__main__":
  sys.exit(main())
