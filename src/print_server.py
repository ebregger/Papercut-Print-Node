"""TCP listener that accepts either IPP-over-HTTP or raw PDF (Windows TCP port)."""

from __future__ import annotations

import logging
import socket
import socketserver
import threading
from typing import Any, Callable

from ippserver.server import IPPRequestHandler

logger = logging.getLogger(__name__)

CHUNK = 65536
RawJobHandler = Callable[[bytes], None]


def _read_all(sock: socket.socket, initial: bytes = b"") -> bytes:
  chunks = [initial]
  while True:
    block = sock.recv(CHUNK)
    if not block:
      break
    chunks.append(block)
  return b"".join(chunks)


class MultiplexPrintServer(socketserver.ThreadingTCPServer):
  """Accept IPP HTTP or raw PDF on the same port."""

  allow_reuse_address = True
  daemon_threads = True

  def __init__(
    self,
    address: tuple[str, int],
    behaviour: Any,
    raw_handler: RawJobHandler,
  ) -> None:
    self.behaviour = behaviour
    self.raw_handler = raw_handler
    super().__init__(address, _MultiplexHandler)


class _MultiplexHandler(socketserver.BaseRequestHandler):
  def handle(self) -> None:
    sock: socket.socket = self.request
    try:
      peek = sock.recv(8, socket.MSG_PEEK)
      if not peek:
        return
      if peek.startswith(b"%PDF"):
        sock.recv(len(peek))
        pdf = _read_all(sock)
        logger.info("Raw PDF job (%d bytes) from %s", len(pdf), self.client_address)
        self.server.raw_handler(pdf)
        return
      logger.debug("IPP/HTTP request from %s prefix=%r", self.client_address, peek[:8])
      IPPRequestHandler(sock, self.client_address, self.server)
    except Exception:
      logger.exception("Request failed from %s", self.client_address)


def start_multiplex_server(
    address: tuple[str, int],
    behaviour: Any,
    raw_handler: RawJobHandler,
) -> MultiplexPrintServer:
  server = MultiplexPrintServer(address, behaviour, raw_handler)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  return server
