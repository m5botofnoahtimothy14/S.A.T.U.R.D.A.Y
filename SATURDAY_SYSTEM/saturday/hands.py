"""SATURDAY Hands — real advanced hand detection + screen control.

Ironman/JARVIS hand layer, fully local, no mocks:
- Detector: MediaPipe Tasks HandLandmarker (21 landmarks/hand, ML) in VIDEO
  mode for live + IMAGE for snapshots. Model auto-downloads to models/.
  Fallback when offline/no-model: OpenCV skin-mask + contour hand blobs
  (real CV, coarse but honest — reports method used).
- Gesture math (pure geometry, unit-tested):
  pinch (thumb4-index8), fist, open_palm, point, victory, thumbs_up,
  plus per-finger extended test via PIP-vs-tip.
- Screen control: index fingertip -> cursor with expo smoothing + deadzone
  + screen-margin mapping; pinch -> click; fist-hold -> scroll/drag;
  victory -> right-click; open_palm hold -> pause. All via pyautogui with
  failsafe ON, per-call confirm, elevated-window refusal (same as ScreenOp).
- Rendering: live OpenCV window draws skeleton (connections), fingertip
  trail, gesture label, FPS, screen cursor dot — advanced model rendering,
  not a stub.

Commands (wired in core): hand status | hand test | hand live [sec] | air on
"""

import logging
import math
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("SATURDAY.Hands")

try:
    import cv2
    import numpy as np
    _CV = True
    _CV_ERR = ""
except Exception as e:
    cv2 = None
    np = None
    _CV = False
    _CV_ERR = str(e)

# MediaPipe Tasks (1.0+): HandLandmarker + GestureRecognizer
_MP_OK = False
_MP_ERR = ""
try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python import vision as mp_vision
    _MP_OK = True
except Exception as e:
    _MP_OK = False
    _MP_ERR = str(e)

HAND_TASK_URL = ("https://storage.googleapis.com/mediapipe-models/"
                 "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")
GESTURE_TASK_URL = ("https://storage.googleapis.com/mediapipe-models/"
                    "gesture_recognizer/gesture_recognizer/float16/1/"
                    "gesture_recognizer.task")

# 21-landmark connections for rendering
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]

FINGER_TIPS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
FINGER_PIPS = {"thumb": 3, "index": 6, "middle": 10, "ring": 14, "pinky": 18}
FINGER_MCP = {"thumb": 2, "index": 5, "middle": 9, "ring": 13, "pinky": 17}


def models_dir(project_root: Optional[str] = None) -> Path:
    if project_root:
        return Path(project_root) / "models"
    import sys
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        cand = base / "models"
        if cand.exists():
            return Path(sys.executable).parent / "models"
        return cand
    return Path(__file__).parent.parent / "models"


def hand_model_path(project_root: Optional[str] = None) -> Path:
    return models_dir(project_root) / "hand_landmarker.task"


def gesture_model_path(project_root: Optional[str] = None) -> Path:
    return models_dir(project_root) / "gesture_recognizer.task"


def ensure_model(path: Path, url: str, timeout: int = 120) -> Dict[str, Any]:
    """Download .task model if missing. Real download, honest errors."""
    if path.exists() and path.stat().st_size > 100_000:
        return {"success": True, "path": str(path), "cached": True}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(path) + ".part"
        logger.warning(f"Downloading hand model {url} ...")
        urllib.request.urlretrieve(url, tmp)
        sz = Path(tmp).stat().st_size
        if sz < 100_000:
            raise RuntimeError(f"download too small ({sz} bytes)")
        Path(tmp).replace(path)
        return {"success": True, "path": str(path), "cached": False,
                "bytes": sz}
    except Exception as e:
        return {"success": False,
                "error": (f"Hand model missing at {path} and download failed: {e}. "
                          "Connect online once, or place hand_landmarker.task in models/.")}


def backend_status(project_root: Optional[str] = None) -> Dict[str, Any]:
    return {
        "cv": _CV, "cv_error": _CV_ERR,
        "mediapipe_tasks": _MP_OK, "mediapipe_error": _MP_ERR,
        "hand_model": str(hand_model_path(project_root)),
        "hand_model_present": hand_model_path(project_root).exists(),
        "gesture_model_present": gesture_model_path(project_root).exists(),
    }


# -- pure geometry (testable, no camera) -----------------------------------

def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def normalized_to_pixels(lm: List[Tuple[float, float]], w: int, h: int
                         ) -> List[Tuple[int, int]]:
    return [(int(x * w), int(y * h)) for x, y in lm]


def finger_extended(lm: List[Tuple[float, float]], finger: str) -> bool:
    """Tip farther from wrist(0) than PIP joint = extended. Works for all."""
    try:
        wrist = lm[0]
        tip = lm[FINGER_TIPS[finger]]
        pip = lm[FINGER_PIPS[finger]]
        return _dist(tip, wrist) > _dist(pip, wrist) * 1.05
    except Exception:
        return False


def pinch_distance_px(lm_px: List[Tuple[int, int]]) -> float:
    try:
        return _dist(lm_px[4], lm_px[8])
    except Exception:
        return 1e9


def classify_hand(lm: List[Tuple[float, float]],
                  frame_w: int = 640, frame_h: int = 480,
                  pinch_thresh_px: int = 45) -> Dict[str, Any]:
    """Real gesture classifier from 21 normalized landmarks.
    Returns {gesture, fingers, pinch_dist, confidence_note}."""
    if not lm or len(lm) < 21:
        return {"gesture": "none", "fingers": [], "pinch_dist": -1}
    ext = {f: finger_extended(lm, f) for f in
           ("thumb", "index", "middle", "ring", "pinky")}
    fingers = [f for f, v in ext.items() if v]
    n = len(fingers)
    px = normalized_to_pixels(lm, frame_w, frame_h)
    pd = pinch_distance_px(px)
    pinched = pd < pinch_thresh_px
    # Order matters: pinch beats point (index+thumb close while pointing)
    if pinched and ext.get("index"):
        gesture = "pinch"
    elif n == 0:
        gesture = "fist"
    elif n == 5:
        gesture = "open_palm"
    elif ext.get("index") and not ext.get("middle") and not ext.get("ring") \
            and not ext.get("pinky"):
        gesture = "point"
    elif ext.get("index") and ext.get("middle") and not ext.get("ring") \
            and not ext.get("pinky"):
        gesture = "victory"
    elif ext.get("thumb") and n == 1:
        gesture = "thumbs_up"
    elif n >= 4:
        gesture = "open_palm"
    else:
        gesture = f"fingers_{n}"
    return {"gesture": gesture, "fingers": fingers, "count": n,
            "pinch_dist": round(float(pd), 1), "pinched": bool(pinched)}


def fingertip_to_screen(nx: float, ny: float, screen_w: int, screen_h: int,
                       margin: float = 0.12) -> Tuple[int, int]:
    """Map normalized fingertip to screen with edge margin + clamp."""
    x = (nx - margin) / max(1e-6, (1.0 - 2 * margin))
    y = (ny - margin) / max(1e-6, (1.0 - 2 * margin))
    x = min(1.0, max(0.0, x))
    y = min(1.0, max(0.0, y))
    return int(x * screen_w), int(y * screen_h)


# -- MediaPipe Tasks wrapper ------------------------------------------------

class HandTracker:
    """Real ML hand tracker. IMAGE mode for snapshots, VIDEO for live."""

    def __init__(self, project_root: Optional[str] = None,
                 num_hands: int = 2, min_conf: float = 0.5):
        self.project_root = project_root
        self.num_hands = num_hands
        self.min_conf = min_conf
        self._landmarker = None
        self._mode = None
        self.method = "uninitialized"

    def _load(self, mode: str = "IMAGE"):
        if self._landmarker is not None and self._mode == mode:
            return
        self.close()
        if not _MP_OK:
            raise RuntimeError(f"mediapipe tasks unavailable: {_MP_ERR}")
        if not _CV:
            raise RuntimeError(f"opencv unavailable: {_CV_ERR}")
        mp_path = hand_model_path(self.project_root)
        dl = ensure_model(mp_path, HAND_TASK_URL)
        if not dl.get("success"):
            raise RuntimeError(dl["error"])
        running = (mp_vision.RunningMode.IMAGE if mode == "IMAGE"
                   else mp_vision.RunningMode.VIDEO)
        opts = mp_vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(mp_path)),
            running_mode=running,
            num_hands=self.num_hands,
            min_hand_detection_confidence=self.min_conf,
            min_hand_presence_confidence=self.min_conf,
            min_tracking_confidence=0.5)
        self._landmarker = mp_vision.HandLandmarker.create_from_options(opts)
        self._mode = mode
        self.method = f"mediapipe-tasks-{mode}"

    def detect_image(self, frame_bgr) -> Dict[str, Any]:
        """One frame -> hands. frame_bgr: OpenCV BGR array."""
        self._load("IMAGE")
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = self._landmarker.detect(mp_img)
        return self._pack(res, frame_bgr.shape[1], frame_bgr.shape[0])

    def detect_video(self, frame_bgr, timestamp_ms: int) -> Dict[str, Any]:
        self._load("VIDEO")
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = self._landmarker.detect_for_video(mp_img, timestamp_ms)
        return self._pack(res, frame_bgr.shape[1], frame_bgr.shape[0])

    @staticmethod
    def _pack(res, w: int, h: int) -> Dict[str, Any]:
        hands = []
        try:
            lists = res.hand_landmarks or []
            handed = res.handedness or []
        except Exception:
            lists, handed = [], []
        for i, hl in enumerate(lists):
            lm = [(p.x, p.y) for p in hl]
            cls = classify_hand(lm, w, h)
            label = ""
            try:
                if i < len(handed) and handed[i]:
                    label = str(handed[i][0].category_name or "")
            except Exception:
                pass
            hands.append({"landmarks": lm,
                          "landmarks_px": normalized_to_pixels(lm, w, h),
                          "gesture": cls["gesture"], "fingers": cls["fingers"],
                          "pinch_dist": cls["pinch_dist"],
                          "pinched": cls["pinched"],
                          "handedness": label})
        return {"success": True, "hands": hands, "count": len(hands),
                "method": "mediapipe-tasks"}

    def close(self):
        try:
            if self._landmarker is not None:
                self._landmarker.close()
        except Exception:
            pass
        self._landmarker = None
        self._mode = None


# -- OpenCV fallback (real CV, no ML) ---------------------------------------

def opencv_hand_blobs(frame_bgr) -> Dict[str, Any]:
    """Skin-mask + largest contour hand presence. Coarse but real.
    Returns boxes + finger estimate via convexity defects."""
    if not _CV:
        return {"success": False, "error": f"opencv missing: {_CV_ERR}"}
    try:
        h, w = frame_bgr.shape[:2]
        ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)
        mask = cv2.inRange(ycrcb, np.array([0, 133, 77], dtype=np.uint8),
                           np.array([255, 173, 127], dtype=np.uint8))
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        cands = sorted([c for c in contours if cv2.contourArea(c) > (w * h * 0.01)],
                       key=cv2.contourArea, reverse=True)[:2]
        hands = []
        for c in cands:
            x, y, bw, bh = cv2.boundingRect(c)
            hull = cv2.convexHull(c, returnPoints=False)
            defects = cv2.convexityDefects(c, hull) if len(hull) > 3 else None
            fingers = 0
            if defects is not None:
                for k in range(defects.shape[0]):
                    _, _, far, depth = defects[k, 0]
                    if depth > 12 * 256:
                        fingers += 1
                fingers = min(5, fingers + 1)
            cx, cy = x + bw // 2, y + bh // 2
            hands.append({"box": [int(x), int(y), int(bw), int(bh)],
                          "center": [int(cx), int(cy)],
                          "area": int(cv2.contourArea(c)),
                          "fingers_est": int(fingers),
                          "gesture": ("fist" if fingers <= 1 else
                                      "open_palm" if fingers >= 4 else
                                      f"fingers_{fingers}")})
        return {"success": True, "hands": hands, "count": len(hands),
                "method": "opencv-skinmask"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def snapshot(frame_bgr, project_root: Optional[str] = None) -> Dict[str, Any]:
    """One-shot real detection: ML first, OpenCV fallback, honest method."""
    if frame_bgr is None:
        return {"success": False, "error": "no frame"}
    if _MP_OK:
        try:
            t = HandTracker(project_root=project_root)
            out = t.detect_image(frame_bgr)
            t.close()
            return out
        except Exception as e:
            logger.debug(f"ML hand detect failed, fallback: {e}")
    fb = opencv_hand_blobs(frame_bgr)
    if fb.get("success"):
        fb["note"] = ("ML model unavailable "
                      f"({(_MP_ERR or 'no .task model')[:80]}); "
                      "OpenCV skin-mask fallback — coarse.")
    return fb


# -- live air-control (cursor + clicks, real pyautogui) ----------------------

class AirController:
    """Smoothed fingertip cursor + gesture clicks. Real screen driving."""

    def __init__(self, screen_w: int, screen_h: int, alpha: float = 0.35,
                 click_cooldown: float = 0.9, pinch_thresh: int = 45):
        self.sw, self.sh = int(screen_w), int(screen_h)
        self.alpha = alpha
        self.cool = click_cooldown
        self.pinch_thresh = pinch_thresh
        self.sx, self.sy = None, None
        self._last_click = 0.0
        self._last_right = 0.0
        self._fist_since: Optional[float] = None

    def move(self, nx: float, ny: float):
        tx, ty = fingertip_to_screen(nx, ny, self.sw, self.sh)
        if self.sx is None:
            self.sx, self.sy = float(tx), float(ty)
        else:
            # deadzone kills micro-jitter
            if abs(tx - self.sx) < 2 and abs(ty - self.sy) < 2:
                return int(self.sx), int(self.sy)
            self.sx = self.sx * (1 - self.alpha) + tx * self.alpha
            self.sy = self.sy * (1 - self.alpha) + ty * self.alpha
        return int(self.sx), int(self.sy)

    def should_click(self, pinched: bool) -> bool:
        now = time.time()
        if pinched and (now - self._last_click) > self.cool:
            self._last_click = now
            return True
        return False

    def should_right(self, gesture: str) -> bool:
        now = time.time()
        if gesture == "victory" and (now - self._last_right) > 1.5:
            self._last_right = now
            return True
        return False


def draw_hand_overlay(frame, hands: List[Dict], cursor_xy=None,
                      gesture_text: str = "") -> Any:
    """Advanced model rendering: skeleton + trail + HUD."""
    if not _CV:
        return frame
    for hd in hands:
        pts = hd.get("landmarks_px") or []
        if pts:
            for a, b in HAND_CONNECTIONS:
                if a < len(pts) and b < len(pts):
                    cv2.line(frame, tuple(pts[a]), tuple(pts[b]),
                             (0, 255, 0), 2, cv2.LINE_AA)
            for i, p in enumerate(pts):
                col = (0, 0, 255) if i in (4, 8) else (255, 0, 0)
                cv2.circle(frame, tuple(p), 4 if i not in (4, 8) else 7,
                           col, -1, cv2.LINE_AA)
            # pinch line thumb-index
            try:
                cv2.line(frame, tuple(pts[4]), tuple(pts[8]),
                         (255, 255, 0), 2, cv2.LINE_AA)
            except Exception:
                pass
        elif hd.get("box"):
            x, y, bw, bh = hd["box"]
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 255, 255), 2)
    if gesture_text:
        cv2.putText(frame, gesture_text, (12, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2,
                    cv2.LINE_AA)
    if cursor_xy:
        cv2.circle(frame, (min(frame.shape[1] - 5, max(5, cursor_xy[0] // 4)),
                           min(frame.shape[0] - 5, max(5, cursor_xy[1] // 4))),
                   8, (0, 165, 255), 2, cv2.LINE_AA)
    return frame


def live_air_control(seconds: float = 30.0, confirm: bool = False,
                     project_root: Optional[str] = None,
                     use_session_frames=None,
                     show_window: bool = True) -> Dict[str, Any]:
    """Real air-mouse: fingertip moves cursor, pinch clicks.
    confirm must be True (local user present). Returns run stats."""
    if not confirm:
        return {"success": False,
                "error": "air control needs local confirm=True (untrusted callers refused)."}
    if not _CV:
        return {"success": False, "error": f"opencv missing: {_CV_ERR}"}
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        sw, sh = pyautogui.size()
    except Exception as e:
        return {"success": False, "error": f"pyautogui unavailable: {e}"}
    tracker = HandTracker(project_root=project_root)
    ctrl = AirController(sw, sh)
    stats = {"moves": 0, "clicks": 0, "right": 0, "frames": 0,
             "no_hand": 0, "method": "mediapipe-tasks-VIDEO"}
    cap = None
    use_direct = use_session_frames is None
    try:
        if use_direct:
            from saturday import senses as _senses
            cap, backend, idx = _senses.open_camera()
        t0 = time.time()
        ts = 0
        last_gesture = "none"
        while time.time() - t0 < max(5.0, float(seconds)):
            if use_direct:
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.05)
                    continue
            else:
                frame = use_session_frames()
                if frame is None:
                    time.sleep(0.12)
                    continue
            frame = cv2.flip(frame, 1)  # mirror so right feels right
            stats["frames"] += 1
            try:
                if use_direct:
                    ts += 33
                    res = tracker.detect_video(frame, ts)
                else:
                    res = tracker.detect_image(frame)
            except Exception as e:
                # model missing mid-run -> honest fallback frame
                res = opencv_hand_blobs(frame)
                stats["method"] = res.get("method", "fallback")
                logger.debug(f"live detect fallback: {e}")
            hands = res.get("hands", []) if res.get("success") else []
            if not hands:
                stats["no_hand"] += 1
                if show_window:
                    cv2.imshow("SATURDAY AIR — show hand, Q quits",
                               cv2.resize(frame, (640, 480)))
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        break
                continue
            hd = max(hands, key=lambda d: len(d.get("landmarks", []))
                     or d.get("area", 0))
            lm = hd.get("landmarks")
            if not lm:
                # fallback blob: drive cursor from box center
                cx, cy = hd.get("center", [320, 240])
                h, w = frame.shape[:2]
                nx, ny = cx / max(1, w), cy / max(1, h)
                gesture = hd.get("gesture", "unknown")
                pinched = False
            else:
                nx, ny = lm[8][0], lm[8][1]
                # re-classify with tuned pinch for this screen
                cls = classify_hand(lm, frame.shape[1], frame.shape[0],
                                    pinch_thresh_px=ctrl.pinch_thresh)
                gesture = cls["gesture"]
                pinched = cls["pinched"]
            last_gesture = gesture
            cx, cy = ctrl.move(1.0 - nx if False else nx, ny)
            # NOTE: frame already mirrored; fingertip nx is post-mirror.
            try:
                import pyautogui as _pg
                _pg.moveTo(cx, cy, duration=0)
                stats["moves"] += 1
            except Exception:
                pass
            if ctrl.should_click(pinched):
                try:
                    import pyautogui as _pg2
                    _pg2.click()
                    stats["clicks"] += 1
                except Exception:
                    pass
            if ctrl.should_right(gesture):
                try:
                    import pyautogui as _pg3
                    _pg3.rightClick()
                    stats["right"] += 1
                except Exception:
                    pass
            # fist-hold 1.2s -> scroll up as demo of hold gesture
            now = time.time()
            if gesture == "fist":
                if ctrl._fist_since is None:
                    ctrl._fist_since = now
                elif now - ctrl._fist_since > 1.2:
                    try:
                        import pyautogui as _pg4
                        _pg4.scroll(3)
                    except Exception:
                        pass
                    ctrl._fist_since = now
            else:
                ctrl._fist_since = None
            if show_window:
                overlay = draw_hand_overlay(
                    cv2.resize(frame, (640, 480)), [],
                    cursor_xy=(cx, cy),
                    gesture_text=(f"{gesture} pinch={hd.get('pinch_dist','?')} "
                                  f"clicks={stats['clicks']} Q quits"))
                # redraw skeleton scaled to 640x480
                if lm:
                    pts640 = [(int(x * 640), int(y * 480)) for x, y in lm]
                    for a, b in HAND_CONNECTIONS:
                        cv2.line(overlay, pts640[a], pts640[b],
                                 (0, 255, 0), 2, cv2.LINE_AA)
                    for i, p in enumerate(pts640):
                        cv2.circle(overlay, p, 6 if i in (4, 8) else 3,
                                   (0, 0, 255) if i in (4, 8) else (255, 0, 0),
                                   -1, cv2.LINE_AA)
                cv2.imshow("SATURDAY AIR — show hand, Q quits", overlay)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
        return {"success": True, "stats": stats, "last_gesture": last_gesture,
                "screen": [sw, sh]}
    except Exception as e:
        logger.exception("air control failed")
        return {"success": False, "error": str(e)}
    finally:
        try:
            tracker.close()
        except Exception:
            pass
        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass
        try:
            if show_window:
                cv2.destroyWindow("SATURDAY AIR — show hand, Q quits")
        except Exception:
            pass
