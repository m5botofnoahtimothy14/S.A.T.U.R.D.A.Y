import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from unittest.mock import MagicMock
import saturday.dashboard as dash
import saturday.saturday_core as core_mod

core = MagicMock()
# enroll_photo real logic needs vault; use real core methods with mock pmv
real = SATURDAYCore.__new__ if False else None
from saturday.saturday_core import SATURDAYCore
c = SATURDAYCore.__new__(SATURDAYCore)
c.pmv = MagicMock()
c.pmv.secure_search.return_value = []
c._gallery_cache = None
print("bad name:", SATURDAYCore.enroll_photo(c, "", b"xx"), flush=True)
print("bad bytes:", SATURDAYCore.enroll_photo(c, "noah", b"not-an-image"), flush=True)
import numpy as np, cv2
blank = cv2.imencode(".jpg", np.full((200, 200, 3), 128, np.uint8))[1].tobytes()
print("no face:", SATURDAYCore.enroll_photo(c, "noah", blank), flush=True)
print("roster empty:", SATURDAYCore.gallery_roster(c), flush=True)
print("forget empty:", SATURDAYCore.forget_person(c, "nobody"), flush=True)
c.pmv.secure_search.return_value = [
    {"id": "a1", "content": "xx", "tags": ["identity", "person:noah"]},
    {"id": "a2", "content": "yy", "tags": ["identity", "person:noah"]},
    {"id": "b1", "content": "zz", "tags": ["identity", "person:khadija"]}]
print("roster full:", SATURDAYCore.gallery_roster(c), flush=True)
c.pmv.secure_delete.return_value = True
print("forget noah:", SATURDAYCore.forget_person(c, "Noah"), flush=True)
import re
src = open(r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM\saturday\dashboard.py", encoding="utf-8").read()
print("routes:", [r for r in ("/api/enroll_photo", "/api/gallery", "/api/forget_person",
                              "/api/command", "/api/mood") if r in src], flush=True)
html = open(r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM\dashboard\index.html", encoding="utf-8").read()
print("hud:", [k for k in ("tenroll", "troster", "data-forget", "tname") if k in html], flush=True)
print("DONE", flush=True)
