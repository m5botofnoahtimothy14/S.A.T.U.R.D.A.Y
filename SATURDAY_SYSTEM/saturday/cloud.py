"""SATURDAY Cloud DB — free Firebase RTDB as encrypted off-site backup.

Zero-knowledge design: the vault stores Fernet-encrypted *.enc blobs.
Backup uploads those blobs VERBATIM (base64) plus the salt (needed to
re-derive your key on restore). Firebase never sees plaintext — but the
salt lets anyone attempt offline passphrase guessing, so: use Firebase
locked rules + a STRONG passphrase. Without your passphrase the backup
is random noise to everyone, including Google.

Needs (free Spark plan, no card):
  1. console.firebase.google.com → new project → Realtime Database → locked mode.
  2. Project settings → Service accounts → Generate new private key (.json).
  3. `cloudsetup <service.json path> <db url> [node]` once per session
     (memory only, never written to disk), then `cloudbackup`.

Paths: /saturday_backups/<node>/salt and .../entries/<entry_id>={blob,mtime}.
Restore never overwrites local files — it only fills gaps.
"""

import base64
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Cloud")

try:
    import firebase_admin
    from firebase_admin import credentials, db

    _FB_AVAILABLE = True
except Exception:
    firebase_admin = None
    credentials = db = None
    _FB_AVAILABLE = False


def _root(service_account: str, database_url: str, node: str):
    if not _FB_AVAILABLE:
        raise RuntimeError("firebase-admin missing; pip install firebase-admin")
    if not Path(service_account).exists():
        raise RuntimeError(f"Service account file not found: {service_account}")
    if not database_url:
        raise RuntimeError("Database URL required.")
    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(service_account)
        firebase_admin.initialize_app(cred, {"databaseURL": database_url})
    return db.reference(f"/saturday_backups/{node}")


def backup_vault(vault_memory_dir: str, salt_path: str, service_account: str,
                 database_url: str, node: str) -> Dict[str, Any]:
    root = _root(service_account, database_url, node)
    mem = Path(vault_memory_dir)
    files = sorted(mem.glob("*.enc")) if mem.exists() else []
    pushed = 0
    try:
        if Path(salt_path).exists():
            root.child("salt").set({"blob": base64.b64encode(Path(salt_path).read_bytes()).decode(),
                                    "at": time.time()})
        entries = root.child("entries")
        for f in files:
            entries.child(f.stem).set({"blob": base64.b64encode(f.read_bytes()).decode(),
                                       "mtime": f.stat().st_mtime})
            pushed += 1
        root.child("meta").set({"entries": pushed, "at": time.time()})
        return {"success": True, "entries": pushed}
    except Exception as e:
        logger.warning(f"Cloud backup failed: {e}")
        return {"success": False, "error": str(e)[:200]}


def restore_vault(vault_memory_dir: str, salt_path: str, service_account: str,
                  database_url: str, node: str) -> Dict[str, Any]:
    root = _root(service_account, database_url, node)
    mem = Path(vault_memory_dir)
    mem.mkdir(parents=True, exist_ok=True)
    restored, skipped = 0, 0
    try:
        data = root.get() or {}
        salt_blob = (data.get("salt") or {}).get("blob")
        if salt_blob and not Path(salt_path).exists():
            Path(salt_path).parent.mkdir(parents=True, exist_ok=True)
            Path(salt_path).write_bytes(base64.b64decode(salt_blob))
        for entry_id, item in (data.get("entries") or {}).items():
            safe = "".join(c for c in str(entry_id) if c.isalnum() or c in "-_")
            if not safe or safe != str(entry_id):
                continue
            dest = mem / f"{safe}.enc"
            if dest.exists():
                skipped += 1
                continue
            dest.write_bytes(base64.b64decode(item.get("blob", "")))
            restored += 1
        return {"success": True, "restored": restored, "skipped": skipped}
    except Exception as e:
        logger.warning(f"Cloud restore failed: {e}")
        return {"success": False, "error": str(e)[:200]}
