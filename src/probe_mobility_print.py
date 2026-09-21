#!/usr/bin/env python3
"""Submit a test PDF to Mobility Print via IPP Print-Job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from credentials import CredentialsError, get_credentials, resolve_credentials_path
from mobility_print_client import MobilityPrintClient, MobilityPrintError

MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj
xref
0 4
trailer<</Size 4/Root 1 0 R>>
startxref
0
%%EOF"""


def load_settings(config_path: Path) -> dict:
  if not config_path.is_file():
    return {}
  with config_path.open(encoding="utf-8") as handle:
    return json.load(handle).get("settings", {})


def main() -> int:
  parser = argparse.ArgumentParser(description="Test Mobility Print IPP submission")
  parser.add_argument("--account", default="default")
  parser.add_argument("--queue", default="husky-bw")
  parser.add_argument("--pdf", type=Path, help="PDF to print (default: minimal test page)")
  parser.add_argument(
    "--sides",
    choices=["one-sided", "two-sided-long-edge", "two-sided-short-edge"],
    help="IPP sides attribute (duplex)",
  )
  parser.add_argument("-c", "--config", default="~/mtu-print-node/config/users.json")
  args = parser.parse_args()

  settings = load_settings(Path(args.config).expanduser())
  try:
    creds = get_credentials(args.account, settings=settings)
  except CredentialsError as exc:
    print(f"error: {exc}", file=sys.stderr)
    return 2

  client = MobilityPrintClient.from_settings(settings)
  pdf = args.pdf.read_bytes() if args.pdf else MINIMAL_PDF

  print(f"Credentials: {resolve_credentials_path(settings)}")
  print(f"Account:     {args.account}")
  print(f"Queue:       {args.queue}")
  print(f"Target:      {client.print_url(args.queue)}")

  try:
    client.print_pdf(
      pdf,
      args.queue,
      creds.username,
      creds.password,
      sides=args.sides,
    )
  except MobilityPrintError as exc:
    print(f"FAILED: {exc}", file=sys.stderr)
    return 1

  print("SUCCESS: Mobility Print accepted the IPP Print-Job.")
  return 0


if __name__ == "__main__":
  sys.exit(main())
