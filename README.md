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

MIT
