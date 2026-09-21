import socket
import struct
import time
import uuid

mid = str(uuid.uuid4())
probe = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing" xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery">
<soap:Header>
<wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>
<wsa:MessageID>urn:uuid:{mid}</wsa:MessageID>
<wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
</soap:Header>
<soap:Body><wsd:Probe><wsd:Types>nprt:PrintDeviceType</wsd:Types></wsd:Probe></soap:Body>
</soap:Envelope>"""

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("", 0))
local_port = sock.getsockname()[1]
sock.settimeout(1)
sock.sendto(probe.encode(), ("239.255.255.250", 3702))

found = []
end = time.time() + 5
while time.time() < end:
    try:
        data, addr = sock.recvfrom(65535)
        text = data.decode("utf-8", errors="replace")
        if "ProbeMatch" in text:
            found.append((addr, text))
    except TimeoutError:
        pass

print(f"matches={len(found)}")
for addr, text in found:
    print(f"from {addr}")
    if "MTU Print" in text or "192.168.0.63" in text:
        print("  -> MTU printer found")
    if "XAddrs" in text:
        start = text.find("<wsd:XAddrs>")
        end_idx = text.find("</wsd:XAddrs>")
        if start != -1 and end_idx != -1:
            print("  xaddr:", text[start + 12 : end_idx])

print("unicast probe to pixel...")
unicast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
unicast.settimeout(3)
unicast.bind(("", 0))
unicast.sendto(probe.encode(), ("192.168.0.63", 3702))
try:
    data, addr = unicast.recvfrom(65535)
    text = data.decode("utf-8", errors="replace")
    print("unicast reply from", addr)
    print(text[:500])
except TimeoutError:
    print("no unicast reply")
