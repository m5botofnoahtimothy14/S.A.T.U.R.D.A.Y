import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from unittest.mock import MagicMock
from saturday.saturday_core import SATURDAYCore
from saturday.brain import OllamaBrain
from pathlib import Path
target = Path(r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM\saturday\verse.py")
original = target.read_text(encoding="utf-8")
brain = OllamaBrain(timeout=300)
print("brain available:", brain.available(), flush=True)
system = ("You output ONLY a unified diff (--- a/file, +++ b/file, @@ hunks). "
          "RULES: copy context lines CHARACTER-FOR-CHARACTER from the file, "
          "never retype or shorten them; use only 2 context lines before and "
          "2 after the change; small hunk only. No explanations.")
prompt = ("FILE: verse.py (FULL file, use its REAL line numbers):\n```python\n" + original + "\n```\n"
          "CHANGE: add this verse tuple right after the John 3:16 entry: "
          '("John 14:6", "I am the way, the truth, and the life.")\nUnified diff only, real line numbers:')
prompt = ("FILE: verse.py (FULL file, use its REAL line numbers):\n```python\n" + original + "\n```\n"
          "CHANGE: add this verse tuple right after the John 3:16 entry: "
          '("John 14:6", "I am the way, the truth, and the life.")\nUnified diff only, real line numbers:')
raw = brain._generate(brain.model, prompt, system=system, json_mode=False, num_ctx=2048)
diff = SATURDAYCore._extract_diff(raw)
print("DIFF chars:", len(diff), flush=True)
print(diff[:800], flush=True)
patched = SATURDAYCore._apply_diff(original, diff)
print("APPLIES CLEANLY:", "John 14:6" in patched, flush=True)
import py_compile
py_compile.compile("/dev/null", doraise=True) if False else None
open(r"D:\SATURDAY_TEMP\evolve_draft.py", "w", encoding="utf-8").write(patched)
print("draft written, NOT applied to repo", flush=True)
print("DONE", flush=True)
