"""Listen for WSD Hello/ProbeMatch multicast from the Pixel."""

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

print(f"Listening for WSD multicast on {MCAST}:{PORT} for 45s...")
end = time.time() + 45
found = 0
while time.time() < end:
    try:
        data, addr = sock.recvfrom(65535)
        text = data.decode("utf-8", errors="replace")
        if "MTU Print" in text or "192.168.0.63" in text or "PrintDeviceType" in text:
            found += 1
            action = "Hello" if "/Hello" in text else "ProbeMatch" if "ProbeMatch" in text else "other"
            print(f"[{action}] from {addr[0]}:{addr[1]} ({len(data)} bytes)")
            if "XAddrs" in text:
                start = text.find("<wsd:XAddrs>")
                stop = text.find("</wsd:XAddrs>")
                if start != -1 and stop != -1:
                    print("  XAddrs:", text[start + 12 : stop])
    except TimeoutError:
        pass

print(f"done, relevant packets={found}")
