"""Quarantine vault blobs not readable under the CURRENT passphrase.
Saves bytes to vault/quarantine/ (never deletes), reports ids+tags only.
Passphrase via VAULTPW env only — never on disk."""
import os as _os
import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from pathlib import Path
from pmv.file_crypto import FileCrypto
import json, time, shutil

pw = _os.environ.get("VAULTPW", "")
assert len(pw) >= 8, "VAULTPW required"
root = Path(r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
qdir = root / "vault" / "quarantine"
qdir.mkdir(parents=True, exist_ok=True)
crypto = FileCrypto(pw, salt_path=str(root / "config" / "salt.dat"))
smoke = FileCrypto("SmokeTestPass123!", salt_path=str(root / "config" / "salt.dat"))
kept, moved, unknown = 0, [], []
for f in sorted((root / "vault").rglob("*.enc")):
    if qdir in f.parents:
        continue
    raw = f.read_bytes()
    try:
        json.loads(crypto.decrypt_data(raw).decode())
        kept += 1
        continue
    except Exception:
        pass
    try:
        d = json.loads(smoke.decrypt_data(raw).decode())
        tag = (d.get("tags") if isinstance(d, dict) else "?")
        kind = "demo-boot junk"
    except Exception:
        tag, kind = "?", "unknown key"
    dst = qdir / f.name
    shutil.move(str(f), str(dst))
    moved.append((f.name, kind, tag))
print(f"kept={kept} quarantined={len(moved)}", flush=True)
for n, k, t in moved:
    print(f"  Q {n} [{k}] tags={t}", flush=True)
print("DONE", flush=True)
