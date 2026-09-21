"""Send a Windows-style WSD probe and print the ProbeMatch reply."""

import socket
import uuid

PROBE = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
  xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
  xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery"
  xmlns:print="http://schemas.microsoft.com/windows/2006/08/wdp/print">
  <soap:Header>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>
    <wsa:MessageID>urn:uuid:{mid}</wsa:MessageID>
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
local_port = sock.getsockname()[1]
sock.settimeout(5)
payload = PROBE.format(mid=uuid.uuid4())
sock.sendto(payload.encode(), ("239.255.255.250", 3702))
data, addr = sock.recvfrom(65535)
text = data.decode("utf-8", errors="replace")
print(f"reply from {addr[0]}:{addr[1]} (bound local port {local_port})")
print("urn:uuid in reply:", "urn:uuid:a3c78011" in text)
for tag in ("Address", "Types", "XAddrs"):
    start = text.find(f"<wsd:{tag}>")
    if start == -1:
        start = text.find(f":{tag}>")
    if start != -1:
        end = text.find(f"</", start)
        print(f"{tag}:", text[start:end].split(">", 1)[-1][:200])
