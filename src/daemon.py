#!/usr/bin/env python3
"""Multi-user IPP print node for MTU Mobility Print."""

from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
import time
from pathlib import Path

# Allow `python src/daemon.py` from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from print_server import MultiplexPrintServer, start_multiplex_server

from credentials import CredentialsError, merge_user_credentials
from ipp_behaviour import MtuUserPrinter
from mobility_print_client import MobilityPrintClient
from wsd_service import WsdPrintAdvertiser

logger = logging.getLogger(__name__)


def expand_path(value: str) -> str:
  return str(Path(value).expanduser())


def load_config(path: Path) -> dict:
  with path.open(encoding="utf-8") as handle:
    return json.load(handle)


def local_ip() -> str:
  """Best-effort LAN address for WSD advertisements."""
  probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  try:
    probe.connect(("8.8.8.8", 80))
    return probe.getsockname()[0]
  except OSError:
    return "127.0.0.1"
  finally:
    probe.close()


def start_printer(
    user: dict,
    settings: dict,
    port: int,
    host: str,
) -> tuple[MultiplexPrintServer, MtuUserPrinter]:
  base_uri = f"ipp://{host}:{port}/".encode()
  printer_uri = f"ipp://{host}:{port}/printer".encode()
  spool_dir = expand_path(settings.get("spool_dir", "~/mtu-print-node/spool"))
  user_spool = str(Path(spool_dir) / user["id"])
  mobility_client = MobilityPrintClient.from_settings(settings)

  behaviour = MtuUserPrinter(
    user_id=user["id"],
    display_name=user.get("display_name", f"MTU Print - {user['id']}"),
    username=user["username"],
    password=user["password"],
    queue_bw=user["queues"]["bw"],
    queue_color=user["queues"]["color"],
    spool_dir=user_spool,
    base_uri=base_uri,
    printer_uri=printer_uri,
    mobility_client=mobility_client,
    color_threshold=settings.get("color_threshold", 0.0001),
    default_bw_on_error=settings.get("default_bw_on_error", True),
    default_sides=user.get(
      "default_sides", settings.get("default_sides", "one-sided")
    ),
  )
  behaviour.base_uri = base_uri
  behaviour.printer_uri = printer_uri

  server = start_multiplex_server(
    (host, port),
    behaviour,
    behaviour.process_pdf_bytes,
  )
  logger.info(
    "IPP listening for %s at ipp://%s:%s/printer",
    user["id"],
    host,
    port,
  )
  return server, behaviour


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="MTU headless print node")
  parser.add_argument(
    "-c",
    "--config",
    default="~/mtu-print-node/config/users.json",
    help="Path to users/settings JSON",
  )
  parser.add_argument(
    "-H",
    "--host",
    default="0.0.0.0",
    help="Address to bind (0.0.0.0 listens on all interfaces)",
  )
  parser.add_argument(
    "--no-wsd",
    action="store_true",
    help="Disable WS-Discovery advertisement",
  )
  parser.add_argument("-v", "--verbose", action="count", default=0)
  args = parser.parse_args(argv)

  logging.basicConfig(
    level=logging.DEBUG if args.verbose else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
  )

  config_path = Path(expand_path(args.config))
  if not config_path.is_file():
    logger.error("Config not found: %s", config_path)
    return 1

  config = load_config(config_path)
  settings = config.get("settings", {})
  users = config.get("users", [])
  if not users:
    logger.error("No users defined in config")
    return 1

  try:
    users = merge_user_credentials(users, settings=settings)
  except CredentialsError as exc:
    logger.error("%s", exc)
    return 1

  bind_host = args.host
  base_port = int(settings.get("base_port", 8631))
  wsd_settings = settings.get("wsd", {})
  wsd_enabled = not args.no_wsd and wsd_settings.get("enabled", False)
  wsd_ip = wsd_settings.get("host_ip") or local_ip()
  wsd_port = int(wsd_settings.get("port", 5357))

  servers: list[MultiplexPrintServer] = []
  wsd_advertisers: list[WsdPrintAdvertiser] = []

  try:
    for index, user in enumerate(users):
      port = base_port + index
      server, behaviour = start_printer(user, settings, port, bind_host)
      servers.append(server)
      if wsd_enabled and index == 0:
        advertiser = WsdPrintAdvertiser(
          host_ip=wsd_ip,
          printer_name=user.get("display_name", f"MTU Print - {user['id']}"),
          ipp_port=port,
          http_port=wsd_port,
          on_print_job=lambda data, _fmt, b=behaviour: b.process_pdf_bytes(data),
        )
        advertiser.start()
        wsd_advertisers.append(advertiser)

    logger.info(
      "MTU print node ready (%d printer(s)). WSD=helper APK mDNS=helper APK.",
      len(users),
    )
    while True:
      time.sleep(300)
  except KeyboardInterrupt:
    logger.info("Shutting down...")
  finally:
    for advertiser in wsd_advertisers:
      advertiser.stop()
    for server in servers:
      server.shutdown()
  return 0


if __name__ == "__main__":
  sys.exit(main())
