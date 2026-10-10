"""JARVIS real-module tests — no camera/Blender-hardware needed for unit parts.
Real integration (Blender render, EEG synthetic) runs when deps present.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from saturday import hands as H, gaze as G, cognition as C, forge as F


def test_hand_geometry():
    open_palm = [(0.5, 0.9), (0.4, 0.7), (0.35, 0.5), (0.32, 0.35), (0.30, 0.2),
                 (0.45, 0.55), (0.45, 0.35), (0.45, 0.2), (0.45, 0.1),
                 (0.5, 0.55), (0.5, 0.33), (0.5, 0.18), (0.5, 0.08),
                 (0.55, 0.55), (0.57, 0.35), (0.58, 0.2), (0.59, 0.1),
                 (0.6, 0.57), (0.63, 0.4), (0.65, 0.28), (0.66, 0.18)]
    assert H.classify_hand(open_palm)["gesture"] == "open_palm"
    assert H.fingertip_to_screen(0.5, 0.5, 1920, 1080) == (960, 540)


def test_gaze_math():
    src = [(0.4, 0.5), (0.6, 0.5), (0.5, 0.4), (0.5, 0.6)]
    dst = [(0, 540), (1920, 540), (960, 0), (960, 1080)]
    M = G.fit_affine(src, dst)
    assert M is not None
    x, y = G.apply_affine(M, 0.5, 0.5)
    assert abs(x - 960) < 5 and abs(y - 540) < 5


def test_cognition_psychology():
    f = C.focus_from_signals(6, 0.9, 78, "neutral")
    assert f["focus"] > 60
    snap = C.cognitive_snapshot(6, 0.9, 78, "neutral",
                                ["forge building 10 floors"])
    assert snap["success"] and snap["intent"] == "create-3d"


def test_forge_parse_and_probe():
    s = F.parse_prompt("building 12 floors glass tower")
    assert s["floors"] == 12 and s["style"] == "glass"
    p = F.system_probe()
    assert p["blender_ok"] and p["engine"] in ("CYCLES", "BLENDER_EEVEE_NEXT")


def test_models_installed():
    assert H.hand_model_path().exists()
    assert G.face_model_path().exists()
    assert F.find_blender()["success"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("ALL JARVIS UNIT TESTS PASS")
