# SATURDAY Intelligence System: Setup & Production Guide

This document outlines how to deploy and configure the **SATURDAY + PMV** Unified System.

## 🛠️ Prerequisites

1.  **Python 3.10+**
2.  **VeraCrypt** (Optional for simulation, Required for hard drive level encryption).
3.  **Syncthing** (Required for multi-device P2P sync).

## 🚀 Installation

1.  **Clone / Copy the system:**
    Ensure the directory structure is preserved as defined in the Architecture Guide.

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **VeraCrypt Configuration (Production):**
    To use real VeraCrypt containers instead of simulated folders:
    - Create a VeraCrypt container named `vault.hc` and `blackbox.hc`.
    - Update `saturday/controller.py` with the path to your VeraCrypt executable.
    - Example CLI command for mounting:
      `VeraCrypt.exe /v vault.hc /l V /p your_passphrase /q /s`

## 🏃 Running SATURDAY

To start the system, run the main entry point:

```bash
python main.py
```

### Initial Startup
- You will be prompted for a **Session Passphrase**.
- This passphrase is used to derive encryption keys in memory.
- It is **NEVER** stored to disk. If you lose it, the PMV data is unrecoverable.

## 🧪 Testing

Run the automated test suite to verify the security and logic layers:

```bash
python tests/system_test.py
```

All 10 tests (crypto round-trip, wrong-passphrase rejection, memory E2E,
deadman, lock enforcement, error-path regression, corrupt-config recovery)
must pass. Isolated temp dirs/salts are used — tests never touch your real
`config/salt.dat` or vault.

```bash
python healthcheck.py   # production smoke check (temp dirs only)
```

## 🖥️ Screen Operator (use Gmail/socials with zero credentials)

No integrations needed: SATURDAY sees your screen and drives real apps.
Loop: `open gmail` → `see` (screenshot) → `click`/`type`/`press` → `see` to verify.

- Fully offline (`pyautogui` + `pillow` + Tesseract OCR, all local). Failsafe ON.
- Typed text is never logged or stored (char counts only).
- Remote (Firebase) callers **cannot** drive the screen — local CLI/voice only.

## 🤖 Autonomy (SATURDAY acts by itself)

- `research [topic]` — searches the web, screenshots, **reads the screen**,
  and vaults findings, all alone. Needs the Tesseract binary:
  `winget install UB-Mannheim.TesseractOCR` (or `read`/`clicktext` degrade
  gracefully without it).
- `do [goal]` — works any goal alone; asks you mid-run when it has no
  template (supervised mode: you command, it does the hands work).
- `tasks` — recent autonomous runs with transcripts.
- `read` / `clicktext [word]` — self-reading primitives (`clicktext Compose`
  finds the word and clicks it, no coordinates needed).

## 🧠 Own Brain (unsupervised arbitrary goals, local LLM)

- `brain [goal]` — llama3.2 (Ollama, localhost) reasons step-by-step and drives
  the screen with zero templates; `moondream` gives it vision (`describe`,
  element grounding). No cloud, no keys. Needs 8GB RAM breathing room —
  vision unloads after each look so reasoning gets full memory.
- If Ollama/a model is missing, `brain` says so with install hints instead
  of pretending.

## ❤️ Senses (real local body sensing, camera + signal processing)

- `sense` — people count (HOG), faces (Haar), mood (FER+ ONNX) snapshot.
- `mood` / `hr [sec]` / `wellness` — expression scores, rPPG heart rate
  (green-channel pulsatility → BPM, sit still 10–60s), composite
  anxiety/sadness estimate. **Estimates only — not medical devices.**
- `drink [ml]` / `water` — hydration log + daily level, stored in the vault.
- Models: `ollama pull llama3.2 moondream`; FER+ ONNX auto-explained if absent.

## 👂 Ears + orchestration (hear → act → speak, all local)

- `hear [sec]` — offline whisper (tiny, CPU/int8) transcription; silence
  honestly reported, never hallucinated.
- `say [text]` — speaks via system voice (David/Zira present).
- `listen` — continuous Jarvis loop: hears a command, executes it
  (vault, screen, senses, brain — full orchestration), speaks the result,
  until `goodbye` or Ctrl+C. Failsafe + step limits active.
- Console is forced to UTF-8 so voice/screen output never crashes on Windows.

## 🖥️ HUD + HomeBot Core2 (v1.6.0)

- `dashboard` — serves `dashboard/index.html`: arc-reactor core, subsystem
  cards, command console, task feed, Core2 D-pad, event log. Stdlib only,
  127.0.0.1 only, 2s polling with auto-reconnect, JSON error envelopes.
- `bot forward 2 80` / `botstatus` — MQTT (`saturday/saturday_homebot_01/#`,
  same protocol as `core/homebot/firmware/flash`) with unlimited backoff
  retry, or USB serial auto-detect. Own MQTT echoes never fake a live bot;
  link tiers: live / stale / never.
- Needs a broker: Mosquitto installed + running on :1883. Core2 not
  plugged in → honest "no link", everything else keeps running.
- `python syscheck.py` — 15-point wiring/hardware/math/protocol check.
  Re-run anytime; exit 0 = green.

## 🔁 Always-on session (v1.7.0 — SATURDAY starts everything)

One unlock boots the whole autonomous system and keeps it warm:
- 📷 Camera opens **once** (~9s, in background) and stays live — `sense`,
  `mood`, `cam` read instantly; `hr` measures from the ring buffer.
- 👂 Whisper preloads (ears hot), 🧠 Ollama probed, 🤖 HomeBot
  supervisor + 🌐 HUD auto-start (127.0.0.1:8099).
- `services` — live status of everything. `queue [goal]` — background
  unsupervised tasks. `cam` — snapshot. `docker`, `maps`, `route` included.

## ✨ Identity, claps, mind, glow, self-heal (v1.8.0)

- `enroll [name]` / `who` — LBPH face recognition, crops encrypted in vault.
- `enrollvoice` / `voiceid` — MFCC voiceprint with auto-calibrated threshold.
- `claps on` — 1 clap = attention + hear/execute, 2 = quiet mode.
- `mind` / `learn` — prefs, sightings, episodes; Hydration/morning self-tasks.
- `glow` — Gemini-style screen-edge living glow (idle/listen/think/speak).
- `heal` — watchdog: restarts camera/HUD, reports ollama/disk/memory/vault.
- `assign` / `inbox` / `briefing` / `announce` — priority self-tasking + voice.
- HUD: boot sequence, particles, live camera eye, identity + mind cards.

## 🏭 Production Deployment

1. `pip install -r requirements.txt` (Python 3.10+)
2. Copy `.env.example` to `.env` only if you use Firebase realtime or custom TTS.
3. `python main.py` → set a strong vault passphrase (min 8 chars, 20+ recommended).
4. **Back up `config/salt.dat` offline.** Losing it = losing the vault permanently,
   even with the correct passphrase. Never commit it (see `.gitignore`).
5. Optional Docker: `docker build -t saturday .` with `/app/vault /app/blackbox
   /app/staging /app/config` as persistent volumes.
6. New command: `delete [id]` permanently removes an entry.

### Reality-check notes (v1.1.0 hardening)
- Fixed: any command-handler exception previously re-crashed inside
  `logger.exception(error=...)` with `TypeError`; error path now returns a clean message.
- Fixed: `tags=False` default, path-traversal IDs (`../`), undecryptable entries
  crashing search, silent settings/JSON failures, double-shutdown, `SIGTERM` crash
  on Windows, TTS fallback chain on Windows (now uses System.Speech), realtime
  listener/publish thread leaks.
- KDF remains PBKDF2-HMAC-SHA256 @ 100k iterations for backward compatibility
  with existing vaults. Do not raise it on an existing vault or old entries
  become unreadable.

## 📖 Command Guide

Once active, the SATURDAY CLI accepts the following:

| Command | Action |
| :--- | :--- |
| `store [content] tag:[tags]` | Encrypts and stores data in PMV. |
| `retrieve [id]` | Decrypts and retrieves a specific memory. |
| `search tag:[tag]` | Finds all memories matching a tag. |
| `status` | Checks Node, Vault, and Deadman status. |
| `heartbeat` | Updates the deadman switch to prevent trigger. |
| `sync` | Manages P2P container synchronization. |
| `open [app\|url]` | Opens an app or site via the screen (e.g. `open gmail`). No credentials. |
| `see` | Screenshots the screen for review. |
| `click [x] [y]` | Clicks screen coordinates (run `see` first). |
| `type [text]` | Types into the focused window (content never logged). |
| `press / hotkey / scroll` | Keys and scrolling. |
| `brain [goal]` | Unsupervised arbitrary goal via local LLM brain. |
| `sense` / `mood` / `hr` / `wellness` | People, mood, heart rate, composite. |
| `drink [ml]` / `water` | Hydration log and daily level. |
| `hear [sec]` / `say [text]` / `listen` | Local STT, speech, Jarvis loop. |
| `dashboard [port]` | Local high-tech HUD (default 8099, 127.0.0.1 only). |
| `bot [cmd]` / `botstatus` | Drive Core2 / link + telemetry + COM ports. |
| `services` / `cam` / `queue` | Session status, snapshot, background tasks. |
| `docker` / `maps` / `route` | Containers, OSM place search + driving route. |
| `enroll` / `who` / `enrollvoice` / `voiceid` | Face + voice identity. |
| `claps` / `mind` / `learn` / `glow` / `heal` | Claps, mind, glow, watchdog. |
| `assign` / `inbox` / `briefing` / `announce` | Self-tasking + voice comms. |
| `share` / `cloudsetup` / `cloudbackup` | Free tunnel online + encrypted cloud DB. |

## 🌐 Online server + cloud DB + deployment (v1.9.0, all free)

**Phone access (now):** in SATURDAY run `share on` → open the printed
`https://*.trycloudflare.com/?token=TOKEN` on your phone. Token auth is
enforced on every route. `share persist` re-opens drops for months;
`share off` kills everything. No account, no card, outbound-only tunnel.

**Stable address:** `cloudflared tunnel login` (one browser click, free
account) → `share on mybot.cfargotunnel.com`. No more rotating URLs.

**Vercel HUD:** `cd vercel-web && python sync.py && npx vercel --prod`
(free hobby, no card). Set `SATURDAY_CORS_ORIGIN=https://<you>.vercel.app`,
then open `https://<you>.vercel.app/?api=TUNNEL_URL&token=TOKEN`.

**Firebase cloud DB (project aegis-os-75256, region asia-southeast1):**
DB URL: `https://aegis-os-75256-default-rtdb.asia-southeast1.firebasedatabase.app`
1. Console → Realtime Database → Rules → locked mode (your DB currently
   answers the whole internet — lock it BEFORE backing up).
2. Project settings → Service accounts → Generate key → save the .json
   privately (NEVER paste the private key anywhere).
3. In SATURDAY: `cloudsetup <path-to.json> <db-url-above>` →
   `cloudbackup` (ciphertext only) / `cloudrestore` (fills gaps only).

**Full cloud VM (later):** Oracle free tier (4 OCPU/24GB ARM, forever free,
card verified at signup only) → install Python + Ollama + this repo.
Nothing here assumes a cloud — the PC remains the primary brain.

## 🛰️ Architecture: server vs humanoid (v2.0.0)

- **Always-on server** (`saturday/server.py`): tunnel + persist watchdog,
  RTDB presence heartbeat + untrusted command inbox. Carries bytes only —
  never holds the passphrase, never decides. `server` shows its truth.
- **Humanoid** (brain, voice, hands, mind, presence): lives on this PC,
  thinks and acts, speaks like a person.
- **Website/HUD**: pure CONTROL plane — reports, checks, health,
  maintenance. No AI chat lives there; commands are control inputs.

## 🛡️ Security Best Practices

1.  **Memory Wiping:** CPython doesn't guarantee immediate memory clearing, but the system uses `ctypes` as a best-effort to wipe passphrase strings.
2.  **Auto-Lock:** The system automatically "dismounts" the logical vault after 5 minutes of inactivity (configurable in `settings.json`).
3.  **Node Trust:** Only add trusted peer IDs in `config/node.json` to prevent malicious sync.
