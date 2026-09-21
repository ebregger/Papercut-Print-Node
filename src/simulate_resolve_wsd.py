"""Simulate Windows Resolve + metadata fetch after Hello."""

import socket
import uuid

import requests

HOST = "192.168.0.63"
HTTP_PORT = 5357
DEVICE_UUID = "a3c78011-9dd0-3daf-ac42-516d1f798cb0"
PRINTER_URL = f"http://{HOST}:{HTTP_PORT}/Printer1/WebServices"


def resolve() -> str:
    message_id = f"urn:uuid:{uuid.uuid4()}"
    resolve_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
  xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
  xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <soap:Header>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Resolve</wsa:Action>
    <wsa:MessageID>{message_id}</wsa:MessageID>
    <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
  </soap:Header>
  <soap:Body>
    <wsd:Resolve>
      <wsa:EndpointReference>
        <wsa:Address>uuid:{DEVICE_UUID}</wsa:Address>
      </wsa:EndpointReference>
    </wsd:Resolve>
  </soap:Body>
</soap:Envelope>"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 0))
    sock.settimeout(5)
    sock.sendto(resolve_xml.encode(), ("239.255.255.250", 3702))
    data, addr = sock.recvfrom(65535)
    text = data.decode("utf-8", errors="replace")
    start = text.find("<wsd:XAddrs>")
    end = text.find("</wsd:XAddrs>")
    xaddr = text[start + 12 : end].strip().split()[0] if start != -1 and end != -1 else ""
    print("ResolveMatch from", addr, "xaddr=", xaddr)
    return xaddr or f"http://{HOST}:{HTTP_PORT}/{DEVICE_UUID}"


def soap_post(url: str, action: str, body: str = "", to: str | None = None) -> requests.Response:
    message_id = f"urn:uuid:{uuid.uuid4()}"
    to_header = to or "http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous"
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
  xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
  xmlns:UNS1="http://www.microsoft.com/windows/test/testdevice/11/2005"
  xmlns:wprt="http://schemas.microsoft.com/windows/2006/08/wdp/print">
  <soap:Header>
    <wsa:To>{to_header}</wsa:To>
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
    xaddr = resolve()
    metadata = soap_post(
        f"http://{HOST}:{HTTP_PORT}/wsd",
        "http://schemas.xmlsoap.org/ws/2004/09/transfer/Get",
        to=f"uuid:{DEVICE_UUID}",
    )
    print("metadata", metadata.status_code, "Edison" in metadata.text)
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
        to=PRINTER_URL,
    )
    print("elements", elements.status_code, "SupportsWSPrintv11" in elements.text)
    print("RESOLVE_FLOW_OK" if metadata.ok and elements.ok else "RESOLVE_FLOW_FAIL")
    return 0 if metadata.ok and elements.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
