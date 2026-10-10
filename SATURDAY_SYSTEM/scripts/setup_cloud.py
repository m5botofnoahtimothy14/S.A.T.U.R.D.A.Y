#!/usr/bin/env python3
"""SATURDAY Firebase setup validator — the 10-minute playbook, enforced.

You (human) do this once in the Firebase console (free Spark plan, no card):
  1. console.firebase.google.com → Create project (any name, no Analytics needed)
  2. Build → Realtime Database → Create Database → Locked mode → copy the URL
     (looks like https://<project>-default-rtdb.<region>.firebasedatabase.app)
  3. Project settings (gear) → Service accounts → Generate new private key
  4. Save the .json OUTSIDE the repo, e.g. D:\\keys\\saturday-fb.json

Then run:  python scripts/setup_cloud.py D:\\keys\\saturday-fb.json <db-url>
This script validates everything it can WITHOUT your vault passphrase:
service JSON parses, firebase-admin imports, DB reachable, write+delete
of a _ping key works, locked rules recommended. On success it prints the
exact lines for your .env (never writes secrets itself).
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def fail(msg):
    print(f"❌ {msg}")
    return 1


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        print("Usage: python scripts/setup_cloud.py <service.json> <database-url>")
        return 2
    sa_path, db_url = argv[1], argv[2].strip().rstrip("/")
    p = Path(sa_path)
    if not p.exists():
        return fail(f"service file not found: {sa_path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        for k in ("type", "project_id", "private_key", "client_email"):
            assert k in data, f"service JSON missing key: {k}"
        assert data["type"] == "service_account", "not a service-account key"
        print(f"✅ service JSON OK (project {data['project_id']}, {data['client_email']})")
    except Exception as e:
        return fail(f"service JSON invalid: {e}")
    if "firebasedatabase.app" not in db_url and "firebaseio.com" not in db_url:
        return fail("database URL doesn't look like RTDB "
                    "(https://<project>-default-rtdb.<region>.firebasedatabase.app)")
    print(f"✅ database URL shape OK: {db_url}")
    try:
        import firebase_admin
        from firebase_admin import credentials, db
    except ImportError:
        return fail("firebase-admin missing: pip install firebase-admin")
    try:
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(credentials.Certificate(str(p)),
                                          {"databaseURL": db_url})
        ref = db.reference("/saturday_setup_ping")
        ref.set({"at": time.time(), "host": os.environ.get("COMPUTERNAME", "?")})
        back = ref.get()
        assert back and "at" in back, "write/read mismatch"
        ref.delete()
        print("✅ RTDB write+read+delete OK (full round trip)")
    except Exception as e:
        return fail(f"RTDB unreachable: {e}\n   Check: URL correct? service key matches THIS project? "
                    "Database created (not just Firestore)? Network allows googleapis?")
    print("\n🎉 Firebase is LIVE. Add to SATURDAY_SYSTEM/.env (create it; never commit):")
    print(f"FIREBASE_SERVICE_ACCOUNT={p}")
    print(f"FIREBASE_DATABASE_URL={db_url}")
    print("FIREBASE_NODE_ID=saturday-node")
    print("\nThen in SATURDAY: cloudsetup <same json> <same url> → cloudbackup → mailbox")
    print("Rules reminder: keep Realtime Database in LOCKED mode (your data is")
    print "encrypted blobs, but locked rules stop strangers listing your node).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
