"""Listen for Windows WSD probes and log them for 30s."""

import re
import socket
import struct
import time

MCAST = "239.255.255.250"
PORT = 3702

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("", PORT))
mreq = struct.pack("=4sl", socket.inet_aton(MCAST), socket.INADDR_ANY)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
sock.settimeout(1)

print("Listening for probes/hello for 30s...")
end = time.time() + 30
while time.time() < end:
    try:
        data, addr = sock.recvfrom(65535)
    except TimeoutError:
        continue
    text = data.decode("utf-8", errors="replace")
    action = "Probe" if "/Probe" in text else "Hello" if "/Hello" in text else "ProbeMatch" if "ProbeMatch" in text else "other"
    types = re.search(r"<[^:>]*:Types[^>]*>(.*?)</[^:>]*:Types>", text, re.I | re.S)
    t = types.group(1).strip() if types else ""
    print(f"[{action}] {addr[0]}:{addr[1]} types={t!r} len={len(data)}")
