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

## 🛡️ Security Best Practices

1.  **Memory Wiping:** CPython doesn't guarantee immediate memory clearing, but the system uses `ctypes` as a best-effort to wipe passphrase strings.
2.  **Auto-Lock:** The system automatically "dismounts" the logical vault after 5 minutes of inactivity (configurable in `settings.json`).
3.  **Node Trust:** Only add trusted peer IDs in `config/node.json` to prevent malicious sync.
