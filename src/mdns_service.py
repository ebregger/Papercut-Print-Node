"""Advertise reachable IPP queues on the phone's Wi-Fi network."""

from __future__ import annotations

import logging
import socket
import struct
import uuid

from zeroconf import ServiceInfo, Zeroconf

logger = logging.getLogger(__name__)


def interface_ipv4(interface: str) -> str:
  """Get an IPv4 address from a named interface, avoiding VPN routes."""
  import fcntl

  with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    request = struct.pack("256s", interface[:15].encode("ascii"))
    response = fcntl.ioctl(sock.fileno(), 0x8915, request)  # SIOCGIFADDR
  return socket.inet_ntoa(response[20:24])


class IppAdvertiser:
  def __init__(self, *, address: str, hostname: str) -> None:
    self.address = address
    self.hostname = hostname.rstrip(".").removesuffix(".local")
    self._zeroconf: Zeroconf | None = None
    self._services: list[ServiceInfo] = []

  def start(self) -> None:
    if self._zeroconf is None:
      self._zeroconf = Zeroconf(interfaces=[self.address])

  def register(self, *, name: str, user_id: str, port: int,
               resource_path: str = "printer",
               printer_uuid: str | None = None) -> None:
    if self._zeroconf is None:
      raise RuntimeError("mDNS advertiser is not started")
    # Only advertise the PDF format that the IPP endpoint actually accepts.
    info = ServiceInfo(
      "_ipp._tcp.local.",
      f"{name}._ipp._tcp.local.",
      addresses=[socket.inet_aton(self.address)],
      port=port,
      server=f"{self.hostname}.local.",
      properties={
        "txtvers": "1",
        "qtotal": "1",
        "rp": resource_path.lstrip("/"),
        "ty": name,
        "product": "(PaperCut Print Node)",
        "pdl": "application/pdf",
        "UUID": printer_uuid or str(uuid.uuid5(uuid.NAMESPACE_DNS, f"mtu-print-node:{user_id}")),
      },
    )
    self._zeroconf.register_service(info)
    self._services.append(info)
    logger.info("mDNS advertising %s at ipp://%s:%d/%s",
                name, self.address, port, resource_path.lstrip("/"))

  def stop(self) -> None:
    if self._zeroconf is not None:
      for info in reversed(self._services):
        self._zeroconf.unregister_service(info)
      self._zeroconf.close()
      self._zeroconf = None
      self._services.clear()
