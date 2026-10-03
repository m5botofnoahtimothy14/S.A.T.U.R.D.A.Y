import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import screen_operator as so
op = so.ScreenOperator()

# ladder 2: dismiss the stale error dialog via UIA (control by name, no coords)
print("WINDOWS now:", [t for t in __import__("pygetwindow").getAllTitles() if "otepad" in t], flush=True)
r = op.uia_click("Notepad", "OK", confirm=True)
print("UIA dismiss:", r, flush=True)
time.sleep(0.5)
# fresh tab, then focus the Untitled one exactly
h = op.hotkey(["ctrl", "n"], confirm=True)
print("NEW TAB:", h, flush=True)
time.sleep(0.8)
print("WINDOWS:", [t for t in __import__("pygetwindow").getAllTitles() if "otepad" in t], flush=True)
f = op.focus_window("Untitled")
print("FOCUS untitled:", f, flush=True)
r2 = op.type_text("hello", confirm=True, window="Untitled")
print("TYPE:", r2, flush=True)
after = op.screenshot(r"D:\proof_after2.png")
rd = op.read_screen(after["path"])
print("OCR sees 'hello':", "hello" in rd.get("text", "").lower(), flush=True)
print("OCR tail:", repr(rd.get("text", "")[-150:]), flush=True)
print("DONE", flush=True)
