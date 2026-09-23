# Michigan Tech Print Node

> **Status: experimental.** This project is a prototype for receiving local IPP print jobs on a Pixel 3 running Termux and forwarding PDF jobs to Michigan Tech PaperCut Mobility Print. An end-to-end working deployment has not been verified.

The current code targets Mobility Print, not PaperCut Web Print. It includes an IPP server, print routing, configuration examples, and discovery probes.

## Before using it

- `config/credentials.json.example` contains placeholders. The real `config/credentials.json` is gitignored.
- The example configuration currently uses HTTP for Mobility Print and the client sends credentials with Basic authentication. Do not use real credentials until a secure connection is confirmed.
- Printer discovery, account access, and successful job submission still need testing on the target network.

This repository records an in-progress prototype and is not a ready-to-install printing service.
