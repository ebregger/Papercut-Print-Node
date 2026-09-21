import uuid

import requests

mid = f"urn:uuid:{uuid.uuid4()}"
body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">
<soap:Header>
<wsa:Action>http://schemas.xmlsoap.org/ws/2004/09/transfer/Get</wsa:Action>
<wsa:MessageID>{mid}</wsa:MessageID>
<wsa:ReplyTo><wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address></wsa:ReplyTo>
</soap:Header>
<soap:Body/>
</soap:Envelope>"""

response = requests.post(
    "http://192.168.0.63:5357/wsd",
    data=body.encode(),
    headers={"Content-Type": "application/soap+xml"},
    timeout=10,
)
print("status", response.status_code)
print("has printer name", "Edison" in response.text)
print("has printer service", "PrinterServiceType" in response.text)
print(response.text[:700])
