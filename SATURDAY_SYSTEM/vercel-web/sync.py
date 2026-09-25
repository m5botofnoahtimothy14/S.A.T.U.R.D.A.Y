"""Sync the Vercel HUD from the single source: ../dashboard/index.html.

Run before every `vercel deploy` (and after any HUD change):
    python vercel-web/sync.py
Commit the synced copy too, so GitHub-connected Vercel projects deploy
without running this script.
"""
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE.parent / "dashboard" / "index.html"
DST = HERE / "index.html"

data = SRC.read_bytes()
DST.write_bytes(data)
print(f"synced {len(data)} bytes dashboard/index.html -> vercel-web/index.html")
