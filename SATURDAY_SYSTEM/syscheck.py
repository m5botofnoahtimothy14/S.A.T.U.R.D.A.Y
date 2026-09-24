"""SATURDAY full system check — wiring, hardware, math, protocols. Read-only.

Temp dirs only (never touches the real vault). Exit 0 = all green,
exit 1 = something needs attention. Safe to run anytime, takes ~1 min.
"""
import socket
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

results = []


def check(name, fn):
    try:
        detail = fn()
        results.append((name, True, str(detail or "ok")))
    except Exception as e:
        results.append((name, False, str(e)[:160]))


def _import(name):
    __import__(name)
    mod = sys.modules[name]
    return getattr(mod, "__version__", "present")


check("imports: vault+core", lambda: [ _import(m) for m in
    ("saturday.controller", "saturday.saturday_core", "pmv.memory_engine",
     "pmv.file_crypto", "pmv.deadman", "pmv.node_manager")] and "6 mods")
check("imports: autonomy+web+bot", lambda: [_import(m) for m in
    ("saturday.screen_operator", "saturday.agent", "saturday.brain",
     "saturday.senses", "saturday.ears", "saturday.homebot",
     "saturday.dashboard", "interface.cli", "interface.voice",
     "realtime_bridge")] and "10 mods")
check("deps: crypto/stack", lambda: (
    f"crypt={_import('cryptography')} numpy={_import('numpy')} "
    f"scipy={_import('scipy')} ort={_import('onnxruntime')}"))
check("deps: io/stack", lambda: (
    f"cv={_import('cv2')} pa={_import('pyautogui')} pil={_import('PIL')} "
    f"tess={_import('pytesseract')} sd={_import('sounddevice')} "
    f"fw={_import('faster_whisper')} mqtt={_import('paho.mqtt.client')} "
    f"serial={_import('serial')}"))

def _camera():
    from saturday import senses
    f = senses.grab_frame()
    p, fa = senses.find_people(f), senses.find_faces(f)
    return f"frame {f.shape[1]}x{f.shape[0]}, people={p['count']}, faces={fa['count']}"
check("camera: capture+detect", _camera)

def _mic():
    from saturday import ears
    m = ears.list_mics()
    assert m["success"] and m["mics"], "no input devices"
    return f"{len(m['mics'])} input(s)"
check("mic: devices listed", _mic)

def _ollama():
    from saturday.brain import OllamaBrain
    b = OllamaBrain()
    assert b.available(), "llama3.2 not pulled or ollama down"
    return "llama3.2 ready"
check("brain: ollama model", _ollama)

def _tess():
    from saturday.screen_operator import ocr_available
    assert ocr_available(), "tesseract missing"
    return "ocr ready"
check("eyes: tesseract", _tess)

def _broker():
    s = socket.create_connection(("127.0.0.1", 1883), timeout=4)
    s.close()
    return "mqtt 1883 open"
check("homebot: mqtt broker", _broker)

def _ports():
    from saturday.homebot import scan_ports
    return f"{len(scan_ports())} COM port(s) seen"
check("homebot: com scan", _ports)

def _proto():
    from saturday.homebot import CMD_TOPIC, TELE_TOPIC, STATUS_TOPIC
    fw = (PROJECT_ROOT.parent / "core" / "homebot" / "firmware" / "flash" / "communication.py").read_text()
    assert CMD_TOPIC == "saturday/saturday_homebot_01/command", CMD_TOPIC
    for needle in ("saturday_homebot_01", "command_topic", "telemetry_topic",
                   TELE_TOPIC.split("/")[-1], STATUS_TOPIC.split("/")[-1]):
        assert needle in fw, f"firmware missing {needle}"
    return "topics match firmware"
check("homebot: protocol match", _proto)

def _dashport():
    try:
        s = socket.create_connection(("127.0.0.1", 8099), timeout=2)
        s.close()
        return "8099 in use (hud already running?)"
    except OSError:
        return "8099 free for hud"
check("hud: port 8099 check", _dashport)

def _crypto():
    import tempfile as t
    from pmv.file_crypto import FileCrypto
    salt = Path(t.mkdtemp()) / "s.dat"
    c = FileCrypto("SyscheckPass123!", salt_path=str(salt))
    assert c.decrypt_data(c.encrypt_data(b"ping")) == b"ping"
    return "roundtrip ok"
check("math: vault crypto", _crypto)

def _rppg():
    import numpy as np
    from saturday.senses import bpm_from_green_series
    fps, f0 = 30.0, 1.2
    t = np.arange(int(fps * 20)) / fps
    v = (128 + 4 * np.sin(2 * np.pi * f0 * t)).tolist()
    r = bpm_from_green_series(v, fps)
    assert r["success"] and 65 <= r["bpm"] <= 79, r
    return f"{r['bpm']} BPM synthetic"
check("math: rppg 72bpm", _rppg)

def _threads():
    import threading
    names = sorted(t.name for t in threading.enumerate())
    return f"{len(names)} alive: {', '.join(names[:6])}"
check("runtime: threads", _threads)

print("\n===== SATURDAY SYSTEM CHECK =====")
fails = 0
for name, ok, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    fails += 0 if ok else 1
print(f"===== {len(results) - fails}/{len(results)} green =====\n")
sys.exit(1 if fails else 0)
