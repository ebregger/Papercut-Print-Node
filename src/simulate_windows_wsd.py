"""Simulate the Windows WSD printer discovery handshake."""

from __future__ import annotations

import socket
import struct
import sys
import uuid

import requests

HOST = "192.168.0.63"
HTTP_PORT = 5357
PRINTER_URL = f"http://{HOST}:{HTTP_PORT}/Printer1/WebServices"


def probe(host: str = "239.255.255.250") -> tuple[str, str]:
    message_id = f"urn:uuid:{uuid.uuid4()}"
    probe_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
  xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
  xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery"
  xmlns:pnpx="http://schemas.microsoft.com/windows/pnpx/2005/10"
  xmlns:print="http://schemas.microsoft.com/windows/2006/08/wdp/print">
  <soap:Header>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>
    <wsa:MessageID>{message_id}</wsa:MessageID>
    <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
  </soap:Header>
  <soap:Body>
    <wsd:Probe>
      <wsd:Types>print:PrintDeviceType</wsd:Types>
    </wsd:Probe>
  </soap:Body>
</soap:Envelope>"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 0))
    sock.settimeout(5)
    sock.sendto(probe_xml.encode(), (host, 3702))
    data, _addr = sock.recvfrom(65535)
    text = data.decode("utf-8", errors="replace")
    start = text.find("<wsd:XAddrs>")
    end = text.find("</wsd:XAddrs>")
    xaddr = text[start + 12 : end].strip().split()[0] if start != -1 and end != -1 else ""
    return xaddr, text


def soap_post(url: str, action: str, body: str = "") -> requests.Response:
    message_id = f"urn:uuid:{uuid.uuid4()}"
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
  xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
  xmlns:UNS1="http://www.microsoft.com/windows/test/testdevice/11/2005"
  xmlns:wprt="http://schemas.microsoft.com/windows/2006/08/wdp/print">
  <soap:Header>
    <wsa:Action>{action}</wsa:Action>
    <wsa:MessageID>{message_id}</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <UNS1:ServiceIdentifier>uri:prn</UNS1:ServiceIdentifier>
  </soap:Header>
  <soap:Body>{body}</soap:Body>
</soap:Envelope>"""
    return requests.post(
        url,
        data=envelope.encode(),
        headers={"Content-Type": "application/soap+xml; charset=utf-8"},
        timeout=10,
    )


def main() -> int:
    print("1) WSD Probe")
    xaddr, probe_reply = probe(HOST if "--unicast" in sys.argv else "239.255.255.250")
    print("   XAddrs:", xaddr or "(missing)")
    if not xaddr:
        print(probe_reply[:500])
        return 1

    print("2) Metadata Get")
    metadata = soap_post(
        xaddr,
        "http://schemas.xmlsoap.org/ws/2004/09/transfer/Get",
    )
    print("   status:", metadata.status_code)
    checks = [
        "PrinterServiceType" in metadata.text,
        "Edison" in metadata.text,
        "Printer1/WebServices" in metadata.text,
    ]
    print("   metadata ok:", all(checks), checks)

    print("3) GetPrinterElements")
    elements_body = """
    <wprt:GetPrinterElementsRequest>
      <wprt:RequestedElements>
        <wprt:Name>wprt:PrinterDescription</wprt:Name>
        <wprt:Name>wprt:PrinterConfiguration</wprt:Name>
        <wprt:Name>wprt:PrinterCapabilities</wprt:Name>
        <wprt:Name>wprt:DefaultPrintTicket</wprt:Name>
        <wprt:Name>wprt:PrinterStatus</wprt:Name>
      </wprt:RequestedElements>
    </wprt:GetPrinterElementsRequest>"""
    elements = soap_post(
        PRINTER_URL,
        "http://schemas.microsoft.com/windows/2006/08/wdp/print/GetPrinterElements",
        elements_body,
    )
    print("   status:", elements.status_code)
    required = [
        "PrinterDescription",
        "PrinterConfiguration",
        "PrinterCapabilities",
        "DefaultPrintTicket",
        "PrinterStatus",
        "SupportsWSPrintv11",
        "DuplexerInstalled",
    ]
    missing = [name for name in required if name not in elements.text]
    print("   missing:", missing or "none")
    if missing:
        return 1

    print("WINDOWS_FLOW_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
