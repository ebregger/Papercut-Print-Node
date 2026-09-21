"""PaperCut Mobility Print client — submits jobs via IPP Print-Job over HTTP."""

from __future__ import annotations

import logging
import struct
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# IPP version 1.1, operation Print-Job (RFC 8011).
IPP_VERSION_MAJOR = 1
IPP_VERSION_MINOR = 1
OPERATION_PRINT_JOB = 0x0002

# Attribute group / value tags.
TAG_OPERATION_ATTRIBUTES = 0x01
TAG_END_OF_ATTRIBUTES = 0x03
TAG_CHARSET = 0x47
TAG_NATURAL_LANGUAGE = 0x48
TAG_URI = 0x45
TAG_MIME_MEDIA_TYPE = 0x49
TAG_NAME_WITHOUT_LANGUAGE = 0x42
TAG_KEYWORD = 0x44

IPP_STATUS_SUCCESSFUL_OK = 0x0000


class MobilityPrintError(Exception):
  """Raised when Mobility Print rejects or cannot accept a job."""


def _ipp_attribute(tag: int, name: str, value: str) -> bytes:
  name_bytes = name.encode("utf-8")
  value_bytes = value.encode("utf-8")
  return (
    struct.pack(">B", tag)
    + struct.pack(">H", len(name_bytes))
    + name_bytes
    + struct.pack(">H", len(value_bytes))
    + value_bytes
  )


def build_print_job_request(
    *,
    printer_uri: str,
    pdf_data: bytes,
    requesting_user_name: str | None = None,
    job_name: str | None = None,
    sides: str | None = None,
    request_id: int = 1,
) -> bytes:
  """
  Build a binary IPP Print-Job request (operation 0x0002).

  Layout: IPP header + operation attributes + end tag + raw document bytes.
  """
  message = bytearray()
  message += struct.pack(">BB", IPP_VERSION_MAJOR, IPP_VERSION_MINOR)
  message += struct.pack(">H", OPERATION_PRINT_JOB)
  message += struct.pack(">I", request_id)

  message += struct.pack(">B", TAG_OPERATION_ATTRIBUTES)
  message += _ipp_attribute(TAG_CHARSET, "attributes-charset", "utf-8")
  message += _ipp_attribute(TAG_NATURAL_LANGUAGE, "attributes-natural-language", "en")
  message += _ipp_attribute(TAG_URI, "printer-uri", printer_uri)
  message += _ipp_attribute(TAG_MIME_MEDIA_TYPE, "document-format", "application/pdf")
  if requesting_user_name:
    message += _ipp_attribute(
      TAG_NAME_WITHOUT_LANGUAGE, "requesting-user-name", requesting_user_name
    )
  if job_name:
    message += _ipp_attribute(TAG_NAME_WITHOUT_LANGUAGE, "job-name", job_name)
  if sides:
    message += _ipp_attribute(TAG_KEYWORD, "sides", sides)
  message += struct.pack(">B", TAG_END_OF_ATTRIBUTES)
  message += pdf_data
  return bytes(message)


def parse_ipp_status(response_body: bytes) -> tuple[int, int]:
  """Return (status_code, request_id) from an IPP response envelope."""
  if len(response_body) < 8:
    raise MobilityPrintError(
      f"IPP response too short ({len(response_body)} bytes)"
    )
  status_code = struct.unpack(">H", response_body[2:4])[0]
  request_id = struct.unpack(">I", response_body[4:8])[0]
  return status_code, request_id


class MobilityPrintClient:
  """
  Submit PDF print jobs to PaperCut Mobility Print.

  Mobility Print exposes each queue at:
    POST http://<host>:9163/printers/<queue_name>
  with Content-Type: application/ipp and HTTP Basic Authentication.
  """

  def __init__(
    self,
    host: str = "print.mtu.edu",
    port: int = 9163,
    *,
    use_tls: bool = False,
    timeout: int = 120,
    verify_ssl: bool = True,
  ) -> None:
    self.host = host
    self.port = port
    self.use_tls = use_tls
    self.timeout = timeout
    self.verify_ssl = verify_ssl
    scheme = "https" if use_tls else "http"
    self.base_url = f"{scheme}://{host}:{port}"

  def printer_uri(self, queue_name: str) -> str:
    safe_queue = quote(queue_name, safe="")
    return f"ipp://{self.host}:{self.port}/printers/{safe_queue}"

  def print_url(self, queue_name: str) -> str:
    safe_queue = quote(queue_name, safe="")
    return f"{self.base_url}/printers/{safe_queue}"

  def _read_pdf(self, pdf_path: str | Path | bytes | BinaryIO) -> bytes:
    if isinstance(pdf_path, bytes):
      return pdf_path
    if isinstance(pdf_path, (str, Path)):
      path = Path(pdf_path)
      if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")
      return path.read_bytes()
    return pdf_path.read()

  def print_pdf(
    self,
    pdf_path: str | Path | bytes | BinaryIO,
    queue_name: str,
    username: str,
    password: str,
    *,
    job_name: str | None = None,
    sides: str | None = None,
  ) -> int:
    """
    Send a PDF to a Mobility Print queue via IPP Print-Job.

    Returns the IPP job-id when present in the response, otherwise 0.
    """
    pdf_data = self._read_pdf(pdf_path)
    if not pdf_data:
      raise MobilityPrintError("Refusing to submit an empty PDF")

    printer_uri = self.printer_uri(queue_name)
    ipp_body = build_print_job_request(
      printer_uri=printer_uri,
      pdf_data=pdf_data,
      requesting_user_name=username,
      job_name=job_name or f"mtu-print-node-{queue_name}",
      sides=sides,
    )
    url = self.print_url(queue_name)

    logger.info(
      "Submitting IPP Print-Job to %s (%d bytes)", url, len(pdf_data)
    )
    try:
      response = requests.post(
        url,
        data=ipp_body,
        auth=(username, password),
        headers={"Content-Type": "application/ipp"},
        timeout=self.timeout,
        verify=self.verify_ssl,
      )
    except requests.RequestException as exc:
      raise MobilityPrintError(f"Mobility Print request failed: {exc}") from exc

    if not response.content:
      raise MobilityPrintError(
        f"Empty IPP response from Mobility Print (HTTP {response.status_code})"
      )

    status_code, request_id = parse_ipp_status(response.content)
    if response.status_code != 200:
      raise MobilityPrintError(
        f"HTTP {response.status_code} from Mobility Print "
        f"(IPP status 0x{status_code:04x})"
      )
    if status_code != IPP_STATUS_SUCCESSFUL_OK:
      raise MobilityPrintError(
        f"Mobility Print rejected job: IPP status 0x{status_code:04x}"
      )

    logger.info(
      "Mobility Print accepted job on %s (request-id %s)",
      queue_name,
      request_id,
    )
    return request_id

  @classmethod
  def from_settings(cls, settings: dict) -> MobilityPrintClient:
    mobility = settings.get("mobility_print", {})
    return cls(
      host=mobility.get("host", "print.mtu.edu"),
      port=int(mobility.get("port", 9163)),
      use_tls=bool(mobility.get("use_tls", False)),
      timeout=int(mobility.get("timeout", 120)),
      verify_ssl=bool(mobility.get("verify_ssl", True)),
    )
