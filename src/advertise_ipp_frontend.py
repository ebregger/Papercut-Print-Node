"""Advertise a separate IPP front end during compatibility testing."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

import requests
from ippserver.constants import SectionEnum, TagEnum
from ippserver.request import IppRequest

from mdns_service import IppAdvertiser, interface_ipv4


def fetch_printer_uuid(port: int, resource_path: str, host: str = "127.0.0.1") -> str:
  uri = f"ipp://{host}:{port}/{resource_path.lstrip('/')}"
  request = IppRequest(
    (1, 1), 0x000B, 1,
    {
      (SectionEnum.operation, b"attributes-charset", TagEnum.charset): [b"utf-8"],
      (SectionEnum.operation, b"attributes-natural-language", TagEnum.natural_language): [b"en"],
      (SectionEnum.operation, b"printer-uri", TagEnum.uri): [uri.encode()],
      (SectionEnum.operation, b"requested-attributes", TagEnum.keyword): [b"printer-uuid"],
    },
  )
  response = requests.post(
    uri.replace("ipp://", "http://", 1),
    data=request.to_string(), headers={"Content-Type": "application/ipp"},
    timeout=5,
  )
  response.raise_for_status()
  reply = IppRequest.from_string(response.content)
  if reply.opid_or_status != 0:
    raise RuntimeError(f"Get-Printer-Attributes returned IPP status {reply.opid_or_status:#x}")
  value = reply.lookup(SectionEnum.printer, b"printer-uuid", TagEnum.uri)[0]
  return str(uuid.UUID(value.decode().removeprefix("urn:uuid:")))


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--name")
  parser.add_argument("--port", type=int, required=True)
  parser.add_argument("--path", required=True)
  parser.add_argument("--interface", default="wlan0")
  args = parser.parse_args()
  if not args.name:
    config = json.loads(Path("config/users.json").read_text(encoding="utf-8"))
    user = config["users"][0]
    args.name = user.get("display_name") or f"Papercut - {user['id']}"
  for attempt in range(30):
    try:
      printer_uuid = fetch_printer_uuid(args.port, args.path)
      break
    except (OSError, requests.RequestException, RuntimeError, KeyError, ValueError):
      if attempt == 29:
        raise
      time.sleep(1)
  advertiser = IppAdvertiser(
    address=interface_ipv4(args.interface), hostname="pixel-print-node"
  )
  try:
    advertiser.start()
    advertiser.register(
      name=args.name, user_id="cups-frontend-test",
      port=args.port, resource_path=args.path, printer_uuid=printer_uuid,
    )
    while True:
      time.sleep(60)
  except KeyboardInterrupt:
    pass
  finally:
    advertiser.stop()


if __name__ == "__main__":
  main()
