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
