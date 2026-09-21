import uuid

import requests

mid = f"urn:uuid:{uuid.uuid4()}"
env = f"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">
  <soap:Header>
    <wsa:To>uuid:a3c78011-9dd0-3daf-ac42-516d1f798cb0</wsa:To>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2004/09/transfer/Get</wsa:Action>
    <wsa:MessageID>{mid}</wsa:MessageID>
  </soap:Header>
  <soap:Body/>
</soap:Envelope>"""
for url in [
    "http://192.168.0.63:5357/",
    "http://192.168.0.63:5357",
]:
    r = requests.post(
        url,
        data=env,
        headers={"Content-Type": "application/soap+xml"},
        timeout=10,
    )
    print(url, r.status_code, "Edison" in r.text)
