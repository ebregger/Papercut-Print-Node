"""WS-Discovery and minimal WS-Print advertisement for Windows auto-discovery."""

from __future__ import annotations

import logging
import re
import socket
import struct
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

MCAST_GRP = "239.255.255.250"
MCAST_PORT = 3702

NS_SOAP = "http://www.w3.org/2003/05/soap-envelope"
NS_WSA = "http://schemas.xmlsoap.org/ws/2004/08/addressing"
NS_WSD = "http://schemas.xmlsoap.org/ws/2005/04/discovery"
NS_WSDP = "http://schemas.xmlsoap.org/ws/2006/02/devprof"
NS_NPRT = "http://schemas.microsoft.com/windows/2006/08/wdp/print"
NS_WSX = "http://schemas.xmlsoap.org/ws/2004/09/mex"
NS_UNS1 = "http://www.microsoft.com/windows/test/testdevice/11/2005"
NS_PNPX = "http://schemas.microsoft.com/windows/pnpx/2005/10"

WSD_TYPES = "wsdp:Device nprt:PrintDeviceType"
PROBE_ACTION = "http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe"
RESOLVE_ACTION = "http://schemas.xmlsoap.org/ws/2005/04/discovery/Resolve"
GET_ACTION = "http://schemas.xmlsoap.org/ws/2004/09/transfer/Get"
GET_PRINTER_ELEMENTS = (
  "http://schemas.microsoft.com/windows/2006/08/wdp/print/GetPrinterElements"
)
CREATE_PRINT_JOB = (
  "http://schemas.microsoft.com/windows/2006/08/wdp/print/CreatePrintJob"
)
SEND_DOCUMENT = (
  "http://schemas.microsoft.com/windows/2006/08/wdp/print/SendDocument"
)

PrintJobHandler = Callable[[bytes, str], None]


def _extract_tag(xml: str, tag: str) -> str | None:
  pattern = rf"<[^:>]*:{re.escape(tag)}[^>]*>(.*?)</[^:>]*:{re.escape(tag)}>"
  match = re.search(pattern, xml, flags=re.DOTALL | re.IGNORECASE)
  if not match:
    pattern = rf"<{re.escape(tag)}[^>]*>(.*?)</{re.escape(tag)}>"
    match = re.search(pattern, xml, flags=re.DOTALL | re.IGNORECASE)
  return match.group(1).strip() if match else None


def _extract_message_id(xml: str) -> str | None:
  for tag in ("MessageID", "RelatesTo"):
    value = _extract_tag(xml, tag)
    if value:
      return value
  return None


def _probe_types(xml: str) -> list[str]:
  probe_xml = _extract_tag(xml, "Probe")
  if not probe_xml:
    return []
  types_xml = _extract_tag(probe_xml, "Types")
  if not types_xml:
    return []
  return types_xml.split()


def _resolve_address(xml: str) -> str | None:
  resolve_xml = _extract_tag(xml, "Resolve")
  if not resolve_xml:
    return None
  endpoint = _extract_tag(resolve_xml, "EndpointReference")
  if not endpoint:
    return None
  return _extract_tag(endpoint, "Address")


def _types_match(probe_types: list[str]) -> bool:
  if not probe_types:
    return True
  advertised = {WSD_TYPES, *WSD_TYPES.split()}
  return any(token in advertised for token in probe_types)


class WsdPrintAdvertiser:
  """Advertise an IPP-backed print queue to Windows via WS-Discovery."""

  def __init__(
    self,
    *,
    host_ip: str,
    printer_name: str,
    ipp_port: int = 8631,
    http_port: int = 5357,
    on_print_job: PrintJobHandler | None = None,
  ) -> None:
    self.host_ip = host_ip
    self.printer_name = printer_name
    self.ipp_port = ipp_port
    self.http_port = http_port
    self.on_print_job = on_print_job
    self.device_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, printer_name))
    self._instance_id = 1
    self._message_number = 0
    self._stop = threading.Event()
    self._discovery_thread: threading.Thread | None = None
    self._http_server: ThreadingHTTPServer | None = None
    self._http_thread: threading.Thread | None = None
    self._next_job_id = 1
    self._jobs: dict[int, bytearray] = {}

  @property
  def device_xaddr(self) -> str:
    return f"http://{self.host_ip}:{self.http_port}/wsd"

  @property
  def printer_xaddr(self) -> str:
    return f"http://{self.host_ip}:{self.http_port}/Printer1/WebServices"

  def start(self) -> None:
    if self._discovery_thread or self._http_thread:
      return
    self._stop.clear()
    self._http_server = self._build_http_server()
    self._http_thread = threading.Thread(
      target=self._http_server.serve_forever,
      name="wsd-http",
      daemon=True,
    )
    self._http_thread.start()
    self._discovery_thread = threading.Thread(
      target=self._discovery_loop,
      name="wsd-discovery",
      daemon=True,
    )
    self._discovery_thread.start()
    self._send_hello()
    logger.info(
      "WSD advertising %s at %s (IPP ipp://%s:%s/printer)",
      self.printer_name,
      self.device_xaddr,
      self.host_ip,
      self.ipp_port,
    )

  def stop(self) -> None:
    self._stop.set()
    if self._http_server:
      self._http_server.shutdown()
      self._http_server.server_close()
      self._http_server = None
    if self._discovery_thread:
      self._discovery_thread.join(timeout=2)
      self._discovery_thread = None
    if self._http_thread:
      self._http_thread.join(timeout=2)
      self._http_thread = None

  def _build_http_server(self) -> ThreadingHTTPServer:
    advertiser = self

    class Handler(BaseHTTPRequestHandler):
      def log_message(self, fmt: str, *args) -> None:
        logger.debug("WSD HTTP " + fmt, *args)

      def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        action = _extract_tag(body, "Action") or ""
        relates_to = _extract_message_id(body) or f"urn:uuid:{uuid.uuid4()}"
        response = advertiser._handle_action(action, body, relates_to)
        payload = response.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/soap+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    return ThreadingHTTPServer(("0.0.0.0", self.http_port), Handler)

  def _handle_action(self, action: str, body: str, relates_to: str) -> str:
    if action == GET_ACTION:
      return self._metadata_response(relates_to)
    if action == GET_PRINTER_ELEMENTS:
      return self._printer_elements_response(relates_to)
    if action == CREATE_PRINT_JOB:
      job_id = self._next_job_id
      self._next_job_id += 1
      self._jobs[job_id] = bytearray()
      return self._create_print_job_response(relates_to, job_id)
    if action == SEND_DOCUMENT:
      job_id = self._extract_job_id(body)
      doc_data = self._extract_document_bytes(body)
      if job_id is not None and doc_data:
        self._jobs.setdefault(job_id, bytearray()).extend(doc_data)
        if self.on_print_job:
          try:
            self.on_print_job(bytes(self._jobs[job_id]), "application/pdf")
          except Exception:
            logger.exception("WSD print job handler failed")
          finally:
            self._jobs.pop(job_id, None)
      return self._send_document_response(relates_to)
    logger.warning("Unhandled WSD action: %s", action)
    return self._empty_soap_response(relates_to)

  def _extract_job_id(self, body: str) -> int | None:
    request = _extract_tag(body, "SendDocumentRequest") or body
    job_id_text = _extract_tag(request, "JobId")
    if not job_id_text or not job_id_text.isdigit():
      return None
    return int(job_id_text)

  def _extract_document_bytes(self, body: str) -> bytes:
    match = re.search(
      r"<[^:>]*:DocumentData[^>]*>(.*?)</[^:>]*:DocumentData>",
      body,
      flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
      return b""
    data = match.group(1).strip()
    if not data:
      return b""
    try:
      import base64

      return base64.b64decode(data)
    except Exception:
      return data.encode("utf-8", errors="ignore")

  def _next_sequence(self) -> tuple[int, int]:
    self._message_number += 1
    return self._instance_id, self._message_number

  def _discovery_loop(self) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
      sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      sock.bind(("", MCAST_PORT))
      mreq = struct.pack("=4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
      sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
      sock.settimeout(1.0)
      while not self._stop.is_set():
        try:
          data, addr = sock.recvfrom(65535)
        except TimeoutError:
          continue
        except OSError:
          if self._stop.is_set():
            break
          continue
        self._handle_discovery_packet(data.decode("utf-8", errors="replace"), addr, sock)
    finally:
      sock.close()

  def _handle_discovery_packet(
    self, xml: str, addr: tuple[str, int], sock: socket.socket
  ) -> None:
    action = _extract_tag(xml, "Action") or ""
    relates_to = _extract_message_id(xml) or f"urn:uuid:{uuid.uuid4()}"
    if action == PROBE_ACTION:
      if not _types_match(_probe_types(xml)):
        return
      payload = self._probe_match(relates_to)
    elif action == RESOLVE_ACTION:
      target = _resolve_address(xml)
      if target and target not in {self.device_uuid, f"uuid:{self.device_uuid}"}:
        return
      payload = self._resolve_match(relates_to)
    else:
      return
    logger.debug("WSD replying to %s action=%s", addr, action)
    sock.sendto(payload.encode("utf-8"), addr)

  def _send_hello(self) -> None:
    instance_id, message_number = self._next_sequence()
    payload = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="{NS_SOAP}" xmlns:wsd="{NS_WSD}" xmlns:wsa="{NS_WSA}" xmlns:wsdp="{NS_WSDP}" xmlns:nprt="{NS_NPRT}">
  <soap:Header>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Hello</wsa:Action>
    <wsa:MessageID>urn:uuid:{uuid.uuid4()}</wsa:MessageID>
    <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
    <wsd:AppSequence InstanceId="{instance_id}" MessageNumber="{message_number}"/>
  </soap:Header>
  <soap:Body>
    <wsd:Hello>
      <wsa:EndpointReference>
        <wsa:Address>uuid:{self.device_uuid}</wsa:Address>
      </wsa:EndpointReference>
      <wsd:Types>{WSD_TYPES}</wsd:Types>
      <wsd:XAddrs>{escape(self.device_xaddr)}</wsd:XAddrs>
      <wsd:MetadataVersion>1</wsd:MetadataVersion>
    </wsd:Hello>
  </soap:Body>
</soap:Envelope>"""
    self._multicast_send(payload)

  def _multicast_send(self, payload: str) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
      sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
      sock.sendto(payload.encode("utf-8"), (MCAST_GRP, MCAST_PORT))
    finally:
      sock.close()

  def _probe_match(self, relates_to: str) -> str:
    return self._discovery_match("ProbeMatches", "ProbeMatch", relates_to)

  def _resolve_match(self, relates_to: str) -> str:
    return self._discovery_match("ResolveMatches", "ResolveMatch", relates_to)

  def _discovery_match(
    self, wrapper: str, item: str, relates_to: str
  ) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="{NS_SOAP}" xmlns:wsd="{NS_WSD}" xmlns:wsa="{NS_WSA}">
  <soap:Header>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/{wrapper}</wsa:Action>
    <wsa:MessageID>urn:uuid:{uuid.uuid4()}</wsa:MessageID>
    <wsa:RelatesTo>{escape(relates_to)}</wsa:RelatesTo>
    <wsa:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:To>
  </soap:Header>
  <soap:Body>
    <wsd:{wrapper}>
      <wsd:{item}>
        <wsa:EndpointReference>
          <wsa:Address>uuid:{self.device_uuid}</wsa:Address>
        </wsa:EndpointReference>
        <wsd:Types>{WSD_TYPES}</wsd:Types>
        <wsd:XAddrs>{escape(self.device_xaddr)}</wsd:XAddrs>
        <wsd:MetadataVersion>1</wsd:MetadataVersion>
      </wsd:{item}>
    </wsd:{wrapper}>
  </soap:Body>
</soap:Envelope>"""

  def _metadata_response(self, relates_to: str) -> str:
    name = escape(self.printer_name)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="{NS_SOAP}" xmlns:wsa="{NS_WSA}" xmlns:wsx="{NS_WSX}" xmlns:wsdp="{NS_WSDP}" xmlns:nprt="{NS_NPRT}" xmlns:UNS1="{NS_UNS1}" xmlns:PNPX="{NS_PNPX}">
  <soap:Header>
    <wsa:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:To>
    <wsa:MessageID>urn:uuid:{uuid.uuid4()}</wsa:MessageID>
    <wsa:RelatesTo>{escape(relates_to)}</wsa:RelatesTo>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2004/09/transfer/GetResponse</wsa:Action>
  </soap:Header>
  <soap:Body>
    <wsx:Metadata>
      <wsx:MetadataSection Dialect="http://schemas.xmlsoap.org/ws/2006/02/devprof/ThisDevice">
        <wsdp:ThisDevice>
          <wsdp:FriendlyName xml:lang="en">{name}</wsdp:FriendlyName>
          <wsdp:FirmwareVersion>1.0</wsdp:FirmwareVersion>
          <wsdp:SerialNumber>mtu-print-node</wsdp:SerialNumber>
        </wsdp:ThisDevice>
      </wsx:MetadataSection>
      <wsx:MetadataSection Dialect="http://schemas.xmlsoap.org/ws/2006/02/devprof/ThisModel">
        <wsdp:ThisModel>
          <wsdp:Manufacturer xml:lang="en">MTU</wsdp:Manufacturer>
          <wsdp:ModelName xml:lang="en">{name}</wsdp:ModelName>
          <wsdp:ModelNumber>MTU Print Node</wsdp:ModelNumber>
          <wsdp:PresentationUrl>http://{escape(self.host_ip)}:{self.ipp_port}/</wsdp:PresentationUrl>
          <PNPX:DeviceCategory>Printers</PNPX:DeviceCategory>
        </wsdp:ThisModel>
      </wsx:MetadataSection>
      <wsx:MetadataSection Dialect="http://schemas.xmlsoap.org/ws/2006/02/devprof/Relationship">
        <wsdp:Relationship Type="http://schemas.xmlsoap.org/ws/2006/02/devprof/host">
          <wsdp:Hosted>
            <wsa:EndpointReference>
              <wsa:Address>{escape(self.printer_xaddr)}</wsa:Address>
              <wsa:ReferenceProperties>
                <UNS1:ServiceIdentifier>uri:prn</UNS1:ServiceIdentifier>
              </wsa:ReferenceProperties>
            </wsa:EndpointReference>
            <wsdp:Types>nprt:PrinterServiceType</wsdp:Types>
            <wsdp:ServiceId>uri:{self.device_uuid}/Printer1/WebServices</wsdp:ServiceId>
            <PNPX:CompatibleId>http://schemas.microsoft.com/windows/2006/08/wdp/print/PrinterServiceType</PNPX:CompatibleId>
          </wsdp:Hosted>
        </wsdp:Relationship>
      </wsx:MetadataSection>
    </wsx:Metadata>
  </soap:Body>
</soap:Envelope>"""

  def _printer_elements_response(self, relates_to: str) -> str:
    name = escape(self.printer_name)
    ipp_uri = escape(f"ipp://{self.host_ip}:{self.ipp_port}/printer")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="{NS_SOAP}" xmlns:wsa="{NS_WSA}" xmlns:wprt="{NS_NPRT}">
  <soap:Header>
    <wsa:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:To>
    <wsa:MessageID>urn:uuid:{uuid.uuid4()}</wsa:MessageID>
    <wsa:RelatesTo>{escape(relates_to)}</wsa:RelatesTo>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/print/GetPrinterElementsResponse</wsa:Action>
  </soap:Header>
  <soap:Body>
    <wprt:GetPrinterElementsResponse>
      <wprt:PrinterElements>
        <wprt:ElementData Name="wprt:PrinterDescription" Valid="true">
          <wprt:PrinterDescription>
            <wprt:ColorSupported>true</wprt:ColorSupported>
            <wprt:DeviceId>MANUFACTURER:MTU;MODEL:Print Node;CLS:PRINTER;DES:{name};</wprt:DeviceId>
            <wprt:MultipleDocumentJobsSupported>false</wprt:MultipleDocumentJobsSupported>
            <wprt:PagesPerMinute>20</wprt:PagesPerMinute>
            <wprt:PrinterName xml:lang="en">{name}</wprt:PrinterName>
            <wprt:PrinterInfo xml:lang="en">MTU Mobility Print Node</wprt:PrinterInfo>
            <wprt:PrinterLocation xml:lang="en">Pixel Print Node</wprt:PrinterLocation>
            <wprt:PrinterUri>{ipp_uri}</wprt:PrinterUri>
          </wprt:PrinterDescription>
        </wprt:ElementData>
        <wprt:ElementData Name="wprt:PrinterCapabilities" Valid="true">
          <wprt:PrinterCapabilities>
            <wprt:PageOutputCapabilities>
              <wprt:PageOutput>
                <wprt:DocumentFormat>application/pdf</wprt:DocumentFormat>
                <wprt:DocumentFormat>application/vnd.ms-xpsdocument</wprt:DocumentFormat>
                <wprt:MediaSizeName>iso_a4_210x297mm</wprt:MediaSizeName>
                <wprt:MediaSizeName>na_letter_8.5x11in</wprt:MediaSizeName>
                <wprt:Duplex>true</wprt:Duplex>
              </wprt:PageOutput>
            </wprt:PageOutputCapabilities>
          </wprt:PrinterCapabilities>
        </wprt:ElementData>
      </wprt:PrinterElements>
    </wprt:GetPrinterElementsResponse>
  </soap:Body>
</soap:Envelope>"""

  def _create_print_job_response(self, relates_to: str, job_id: int) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="{NS_SOAP}" xmlns:wsa="{NS_WSA}" xmlns:wprt="{NS_NPRT}">
  <soap:Header>
    <wsa:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:To>
    <wsa:MessageID>urn:uuid:{uuid.uuid4()}</wsa:MessageID>
    <wsa:RelatesTo>{escape(relates_to)}</wsa:RelatesTo>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/print/CreatePrintJobResponse</wsa:Action>
  </soap:Header>
  <soap:Body>
    <wprt:CreatePrintJobResponse>
      <wprt:JobId>{job_id}</wprt:JobId>
    </wprt:CreatePrintJobResponse>
  </soap:Body>
</soap:Envelope>"""

  def _send_document_response(self, relates_to: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="{NS_SOAP}" xmlns:wsa="{NS_WSA}" xmlns:wprt="{NS_NPRT}">
  <soap:Header>
    <wsa:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:To>
    <wsa:MessageID>urn:uuid:{uuid.uuid4()}</wsa:MessageID>
    <wsa:RelatesTo>{escape(relates_to)}</wsa:RelatesTo>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/print/SendDocumentResponse</wsa:Action>
  </soap:Header>
  <soap:Body>
    <wprt:SendDocumentResponse/>
  </soap:Body>
</soap:Envelope>"""

  def _empty_soap_response(self, relates_to: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="{NS_SOAP}" xmlns:wsa="{NS_WSA}">
  <soap:Header>
    <wsa:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:To>
    <wsa:MessageID>urn:uuid:{uuid.uuid4()}</wsa:MessageID>
    <wsa:RelatesTo>{escape(relates_to)}</wsa:RelatesTo>
  </soap:Header>
  <soap:Body/>
</soap:Envelope>"""
