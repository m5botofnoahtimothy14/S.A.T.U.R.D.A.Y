# AEGIS 3.0

Advanced Engine for Global Integrated Systems.

AEGIS is a local-first AI operating platform with:
- Core runtime dashboard and automation (`core/main.py`, `run_production.py`)
- Dual-access secure control panel stack (Firebase dashboard + local HTTPS gateway)
- Agentic command pipeline (LangGraph), role-based control, telemetry sync, and ROS2 safety enforcement

## What Is Current

The repository now has two web surfaces:

1. Core AEGIS UI on port `8000` (existing FastAPI dashboard from `core/main.py`)
2. Secure API Gateway on port `8443` (`api_gateway.py`) for authenticated control and remote-safe access

The control panel is read-only from the browser side and uses Firebase Auth + Firestore real-time telemetry.
You can also mount the secure gateway directly into the core app path by setting:
- `AEGIS_ENABLE_SECURE_GATEWAY_MOUNT=true`
- `AEGIS_SECURE_GATEWAY_MOUNT_PATH=/api/secure`

## Key Components

- `core/main.py`: Main AEGIS runtime, local UI, media/voice/vision/homebot orchestration
- `api_gateway.py`: HTTPS gateway with Firebase JWT verification and role enforcement
- `auth_validator.py`: Firebase token validation and role extraction
- `command_policy.py`: Strict command schema validation and safety policy checks
- `ros_safety_bridge.py`: ROS2 motion/safety bridge with emergency stop
- `telemetry_sync.py`: Firestore telemetry push/pull service
- `aegis-control-panel/`: React Firebase dashboard for live telemetry
- `ops/secure_access/`: LAN and remote overlay access scripts (Tailscale, Cloudflare Tunnel, ZeroTier)

🔹 Pre-trained Models & Dependencies

AEGIS relies on some large models, node packages, and other resources that are **not included in this repo** to keep it lightweight.  

You can download these manually as needed:  

- **Core AI Models** → download from your preferred source  
- **Node Packages / Dependencies** → download from your preferred source  
- **Datasets / Embeddings** → download from your preferred source  

> ⚠️ Make sure to place downloaded models and packages in the appropriate directories under `core/` or `data/` before running AEGIS.

## Repository Hygiene

To keep the GitHub project page clean, local/generated artifacts are intentionally ignored in `.gitignore`.

Code style normalization:
- Comments and annotation-style note lines were removed from project source files (`.py` and other code/script files) to keep the codebase minimal and uniform.
- Dependency/vendor trees are excluded from this normalization pass (`.venv/`, `pip_packages/`, `node_modules/`, and third-party bundles).

Ignored examples:
- backup folders/files: `backup/`, `backups/`, `*.bak`, `*.backup`, `*.old`, `*.orig`
- packaging leftovers: `*.whl`, `pip-wheel-metadata/`, `*.egg-info/`
- local temp/cache/editor artifacts: `tmp/`, `temp/`, `.cache/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.vscode/`, `.idea/`
- runtime/build outputs: `logs/`, `build/`, `dist/`, `coverage/`, `node_modules/`, `models/`

If any of these were committed before ignore rules were added, remove them from tracking once:

```powershell
git rm -r --cached backup backups logs build dist node_modules models tmp temp
git rm --cached *.whl
git commit -m "chore: stop tracking generated artifacts"
```

## Quick Start (Core Runtime)

### Prerequisites

- Python `3.12+`
- Virtual environment at `.\.venv`

### Run Core AEGIS

```powershell
.\.venv\Scripts\python -m pip install -U -r requirements.txt
.\.venv\Scripts\python run_production.py
```

Open: `http://localhost:8000`

If secure gateway mount is enabled, mounted endpoint root is available at:
`http://localhost:8000/api/secure`

## Dual-Access Control Panel Setup

### 1) Install gateway dependencies

```powershell
.\.venv\Scripts\python -m pip install -U -r requirements.gateway.txt
```

### 2) Configure gateway environment

```powershell
copy gateway.env.example gateway.env
```

Set values in `gateway.env`:
- `FIREBASE_PROJECT_ID`
- `FIREBASE_SERVICE_ACCOUNT` (service account json path)
- `AEGIS_SSL_CERT_FILE`
- `AEGIS_SSL_KEY_FILE`
- `AEGIS_CORE_CONTROL_URL` (where core runtime is reachable, default `http://127.0.0.1:8000`)
- safety limits if you need custom thresholds

### 3) Generate local TLS cert (if needed)

```powershell
.\ops\secure_access\generate-local-cert.ps1 -OutputDirectory certs -CommonName aegis.local
```

### 4) Start HTTPS API gateway

```powershell
.\ops\secure_access\start-api-gateway.ps1 -EnvFile .\gateway.env -Host 127.0.0.1 -Port 8443
```

Health check:

```powershell
curl -k https://127.0.0.1:8443/healthz
```

### 5) Start telemetry feed to Firestore

Example one-shot snapshot:

```powershell
.\.venv\Scripts\python telemetry_sync.py --node-id aegis-node-1 --service-account "<path-to-service-account.json>" --project-id "<firebase-project-id>" --example
```

Continuous telemetry loop:

```powershell
.\.venv\Scripts\python telemetry_sync.py --node-id aegis-node-1 --service-account "<path-to-service-account.json>" --project-id "<firebase-project-id>" --interval 2.0
```

### 6) Build and deploy Firebase dashboard

```powershell
cd aegis-control-panel
copy .env.example .env
# fill VITE_FIREBASE_* values
npm install
npm run build
cd ..
firebase deploy --only hosting,firestore:rules
```

Dashboard:
- Supports email/password + Google login
- Subscribes to Firestore telemetry in real time
- Supports remote wake (`Wake AEGIS` / `Wake EDITH`) for Operator/Admin roles through the secure gateway

## Tailscale Connection (Recommended Remote Access)

Use Tailscale to access the local HTTPS gateway without opening public inbound ports.

### Prerequisites

- Tailscale installed and logged in on the AEGIS host
- Tailscale installed on client devices that need access
- API gateway running locally on `https://127.0.0.1:8443`

### Start Tailscale serve mapping

```powershell
.\ops\secure_access\start-tailscale-access.ps1 -LocalPort 8443 -ServePort 443
```

What this does:
- Runs `tailscale up --accept-dns=false --accept-routes`
- Exposes local gateway `https://127.0.0.1:8443` as Tailscale HTTPS on port `443`

### Access from another Tailscale device

Use the host's MagicDNS name or Tailscale IP:

```text
https://<aegis-hostname>.tailnet-name.ts.net
```

or

```text
https://<tailscale-ip>
```

### Optional public tunnel via Tailscale Funnel

```powershell
.\ops\secure_access\start-tailscale-access.ps1 -LocalPort 8443 -ServePort 443 -EnableFunnel
```

Only enable Funnel if you explicitly need internet-reachable access.

### Restrict LAN at firewall level

```powershell
.\ops\secure_access\configure-lan-firewall.ps1 -GatewayPort 8443 -AllowedSubnet 192.168.0.0/24
```

This keeps local API ingress limited while overlay access handles remote clients.

## Roles and Access Model

Roles:
- `viewer`: telemetry and read-only endpoints
- `operator`: `MOVE`, `STOP`, `SET_MODE`
- `admin`: `MOVE`, `STOP`, `SET_MODE`, `EMERGENCY_STOP`, `CLEAR_ESTOP`

Set Firebase custom role claims:

```powershell
.\.venv\Scripts\python .\scripts\set_firebase_role.py --uid "<firebase-uid>" --role operator --service-account "<service-account.json>" --project-id "<firebase-project-id>"
```

## Command API Examples

Use Firebase ID token:

```powershell
$token = "<firebase-id-token>"
```

List command examples:

```powershell
curl -k https://127.0.0.1:8443/v1/commands/examples -H "Authorization: Bearer $token"
```

Execute MOVE:

```powershell
curl -k https://127.0.0.1:8443/v1/commands/execute `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d "{\"intent\":\"MOVE\",\"parameters\":{\"direction\":\"FORWARD\",\"duration\":1.5,\"speed\":0.4,\"torque\":20}}"
```

Emergency stop:

```powershell
curl -k https://127.0.0.1:8443/v1/commands/execute `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d "{\"intent\":\"EMERGENCY_STOP\",\"parameters\":{\"reason\":\"manual safety test\"}}"
```

## Project Layout

```text
AEGIS/
  core/
  ui/
  api_gateway.py
  auth_validator.py
  command_policy.py
  ros_safety_bridge.py
  telemetry_sync.py
  requirements.gateway.txt
  gateway.env.example
  aegis-control-panel/
  ops/secure_access/
  firebase.json
  firestore.rules
```

## Production Notes

- Keep `SECRET_KEY` and all cloud credentials out of source control.
- Use TLS cert/key for gateway; HTTP is intentionally not enabled in `api_gateway.py`.
- Keep direct internet exposure disabled unless you intentionally enable a tunnel.
- For full production hardening checklist, see `PRODUCTION.md`.

## Additional Docs

- `DUAL_ACCESS_CONTROL_PANEL.md`: detailed gateway + Firebase + secure overlay workflow
- `PRODUCTION.md`: production deployment checklist
- `VISUAL_CORE.md`: startup visual core build/run flow

## License

Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

   "License" shall mean the terms and conditions for use, reproduction,
   and distribution as defined by Sections 1 through 9 of this document.

   "Licensor" shall mean the copyright owner or entity authorized by
   the copyright owner that is granting the License.

   "Legal Entity" shall mean the union of the acting entity and all
   other entities that control, are controlled by, or are under common
   control with that entity. For the purposes of this definition,
   "control" means (i) the power, direct or indirect, to cause the
   direction or management of such entity, whether by contract or
   otherwise, or (ii) ownership of fifty percent (50%) or more of the
   outstanding shares, or (iii) beneficial ownership of such entity.

   "You" (or "Your") shall mean an individual or Legal Entity
   exercising permissions granted by this License.

   "Source" form shall mean the preferred form for making modifications,
   including but not limited to software source code, documentation
   source, and configuration files.

   "Object" form shall mean any form resulting from mechanical
   transformation or translation of a Source form, including but not
   limited to compiled object code, generated documentation,
   and conversions to other media types.

   "Work" shall mean the work of authorship, whether in Source or
   Object form, made available under the License, as indicated by a
   copyright notice that is included in or attached to the work.

   "Derivative Works" shall mean any work, whether in Source or Object
   form, that is based on (or derived from) the Work and for which the
   editorial revisions, annotations, elaborations, or other
   modifications represent, as a whole, an original work of authorship.

   "Contribution" shall mean any work of authorship, including
   the original version of the Work and any modifications or additions
   to that Work or Derivative Works thereof, that is intentionally
   submitted to Licensor for inclusion in the Work by the copyright
   owner or by an individual or Legal Entity authorized to submit on
   behalf of the copyright owner.

   "Contributor" shall mean Licensor and any individual or Legal Entity
   on behalf of whom a Contribution has been received by Licensor and
   subsequently incorporated within the Work.

2. Grant of Copyright License. Subject to the terms and conditions of
   this License, each Contributor hereby grants to You a perpetual,
   worldwide, non-exclusive, no-charge, royalty-free, irrevocable
   copyright license to reproduce, prepare Derivative Works of,
   publicly display, publicly perform, sublicense, and distribute the
   Work and such Derivative Works in Source or Object form.

3. Grant of Patent License. Subject to the terms and conditions of
   this License, each Contributor hereby grants to You a perpetual,
   worldwide, non-exclusive, no-charge, royalty-free, irrevocable
   (except as stated in this section) patent license to make, have made,
   use, offer to sell, sell, import, and otherwise transfer the Work,
   where such license applies only to those patent claims licensable
   by such Contributor that are necessarily infringed by their
   Contribution(s) alone or by combination of their Contribution(s)
   with the Work.

4. Redistribution. You may reproduce and distribute copies of the
   Work or Derivative Works thereof in any medium, with or without
   modifications, and in Source or Object form, provided that You
   meet the following conditions:

   (a) You must give any other recipients of the Work or
       Derivative Works a copy of this License; and

   (b) You must cause any modified files to carry prominent notices
       stating that You changed the files; and

   (c) You must retain, in the Source form of any Derivative Works
       that You distribute, all copyright, patent, trademark, and
       attribution notices from the Source form of the Work.

5. Submission of Contributions. Unless You explicitly state otherwise,
   any Contribution intentionally submitted for inclusion in the Work
   by You to the Licensor shall be under the terms and conditions of
   this License.

6. Trademarks. This License does not grant permission to use the trade
   names, trademarks, service marks, or product names of the Licensor.

7. Disclaimer of Warranty. Unless required by applicable law or
   agreed to in writing, Licensor provides the Work (and each
   Contributor provides its Contributions) on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
   implied, including, without limitation, any warranties or conditions
   of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
   PARTICULAR PURPOSE.

8. Limitation of Liability. In no event and under no legal theory,
   whether in tort, contract, or otherwise, shall any Contributor
   be liable to You for damages arising from the use of the Work.

9. Accepting Warranty or Additional Liability. While redistributing
   the Work or Derivative Works thereof, You may choose to offer,
   and charge a fee for, acceptance of support, warranty, indemnity,
   or other liability obligations and/or rights consistent with this
   License. However, You may act only on Your own behalf and
   on Your sole responsibility.

Copyright 2026 Noah Timothy Keba

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
