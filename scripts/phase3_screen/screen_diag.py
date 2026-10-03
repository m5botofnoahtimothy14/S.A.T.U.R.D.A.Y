"""Part 3 Step 1: standalone screen-stack diagnostics (no SATURDAY imports)."""
import ctypes, sys, time

u32 = ctypes.windll.user32
print(f"REAL SCREEN: {u32.GetSystemMetrics(0)}x{u32.GetSystemMetrics(1)}", flush=True)

# -- display scaling + DPI awareness
try:
    shcore = ctypes.windll.shcore
    print("DPI awareness BEFORE:", ctypes.c_int(), flush=True)
    aware = ctypes.c_int()
    try:
        shcore.GetProcessDpiAwareness(None, ctypes.byref(aware))
        print("GetProcessDpiAwareness =", aware.value, "(0=unaware 1=system 2=per-monitor)", flush=True)
    except Exception as e:
        print("GetProcessDpiAwareness query failed:", str(e)[:100], flush=True)
    try:
        shcore.SetProcessDpiAwareness(2)
        print("SetProcessDpiAwareness(2) OK", flush=True)
    except Exception as e:
        print("SetProcessDpiAwareness failed:", str(e)[:120], flush=True)
    try:
        mon = u32.MonitorFromWindow(u32.GetDesktopWindow(), 2)
        scale = ctypes.c_uint()
        shcore.GetScaleFactorForMonitor(mon, ctypes.byref(scale))
        print(f"DISPLAY SCALE = {scale.value}%", flush=True)
    except Exception as e:
        print("scale query failed:", str(e)[:100], flush=True)
except Exception as e:
    print("shcore unavailable:", str(e)[:100], flush=True)

# -- screenshot
import pyautogui
pyautogui.FAILSAFE = True
print("pyautogui", pyautogui.__version__, "FAILSAFE=", pyautogui.FAILSAFE, flush=True)
shot = pyautogui.screenshot()
shot.save(r"D:\screen_diag.png")
from PIL import ImageStat
st = ImageStat.Stat(shot.convert("L"))
print(f"SHOT: {shot.size[0]}x{shot.size[1]} mean={st.mean[0]:.1f} extrema={st.extrema[0]} "
      f"{'NON-BLACK' if st.mean[0] > 3 else 'BLACK'}", flush=True)

# -- move (safe) + position
x0, y0 = pyautogui.position()
w, h = pyautogui.size()
pyautogui.moveTo(w // 2, h // 2, duration=0.3)
x1, y1 = pyautogui.position()
pyautogui.moveTo(x0, y0, duration=0.2)
print(f"MOVE: ({x0},{y0}) -> ({x1},{y1}) -> back; target=({w//2},{h//2}) "
      f"landed={'OK' if (x1, y1) == (w//2, h//2) else 'OFF'}", flush=True)

# -- harmless key roundtrip (capslock x2 = net no-op)
try:
    pyautogui.press("capslock"); pyautogui.press("capslock")
    print("PRESS capslock x2 OK", flush=True)
except Exception as e:
    print("PRESS FAILED:", str(e)[:150], flush=True)

# -- pygetwindow
import pygetwindow as gw
titles = gw.getAllTitles()
print(f"WINDOWS: {len(titles)} listed; sample={[t for t in titles if t][:5]}", flush=True)
try:
    wins = [t for t in titles if t]
    print("ACTIVE:", gw.getActiveWindowTitle(), flush=True)
except Exception as e:
    print("active window query failed:", str(e)[:120], flush=True)

# -- tesseract
import shutil
tb = shutil.which("tesseract")
print("tesseract on PATH:", tb, flush=True)
import subprocess
for cand in ([tb] if tb else []) + [r"C:\Program Files\Tesseract-OCR\tesseract.exe"]:
    try:
        r = subprocess.run([cand, "--version"], capture_output=True, text=True, timeout=20)
        print(f"TESSERACT {cand}: {r.stdout.splitlines()[0] if r.stdout else r.stderr[:100]}", flush=True)
    except Exception as e:
        print(f"TESSERACT {cand}: FAILED {str(e)[:100]}", flush=True)
print("DONE", flush=True)
