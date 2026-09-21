"""Capture one WSD Hello from the Pixel and print key fields."""

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
sock.settimeout(35)

print("Waiting for Hello...")
data, addr = sock.recvfrom(65535)
text = data.decode("utf-8", errors="replace")
print(f"from {addr[0]}:{addr[1]} ({len(data)} bytes)\n")
print(text[:2500])

for tag in ("Address", "Types", "Scopes", "XAddrs", "MetadataVersion"):
    m = re.search(rf"<[^:>]*:{tag}[^>]*>(.*?)</[^:>]*:{tag}>", text, re.I | re.S)
    if m:
        print(f"\n{tag}: {m.group(1).strip()}")
