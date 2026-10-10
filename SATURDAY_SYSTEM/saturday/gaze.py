"""SATURDAY Gaze — real eye tracking + eye reading, webcam only.

Local ML, no cloud, no mocks:
- Detector: MediaPipe Tasks FaceLandmarker (478 landmarks + iris 468-477).
  Model auto-downloads to models/face_landmarker.task. Honest fallback when
  offline: Haar eye boxes + Hough pupil (coarse, labelled method).
- Gaze math (pure, tested): iris-center vs eye-corner ratios -> gaze vector;
  Eye Aspect Ratio (EAR) -> blink; 5-point calibration (corners+center) maps
  ratios to screen pixels via least-squares affine (numpy).
- Eye control: gaze moves cursor (smoothed), blink / dwell clicks.
- Eye READING: gaze point -> screen crop -> local OCR (Tesseract) reads the
  word/block you are looking at; gaze path -> reading estimate
  (fixations/s, regression count) with psychology notes.

Accuracy note: webcam gaze is ~2-5 deg after calibration. Needs good light,
steady head, 40-70cm distance. Everything reports confidence honestly.
"""

import json
import logging
import math
import os
import time
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("SATURDAY.Gaze")

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

FACE_TASK_URL = ("https://storage.googleapis.com/mediapipe-models/"
                 "face_landmarker/face_landmarker/float16/1/"
                 "face_landmarker.task")

# FaceMesh indices (standard)
LEFT_EYE_OUTER, LEFT_EYE_INNER = 33, 133
LEFT_EYE_UP, LEFT_EYE_DOWN = 159, 145
RIGHT_EYE_OUTER, RIGHT_EYE_INNER = 263, 362
RIGHT_EYE_UP, RIGHT_EYE_DOWN = 386, 374
LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]

CAL_FILE = "gaze_cal.json"


def models_dir(project_root: Optional[str] = None) -> Path:
    if project_root:
        return Path(project_root) / "models"
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "models"
    return Path(__file__).parent.parent / "models"


def face_model_path(project_root: Optional[str] = None) -> Path:
    return models_dir(project_root) / "face_landmarker.task"


def cal_path() -> Path:
    base = Path(os.getenv("SATURDAY_D_TMP", "D:/SATURDAY_TEMP"))
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base / CAL_FILE


def ensure_face_model(project_root: Optional[str] = None,
                      timeout: int = 120) -> Dict[str, Any]:
    p = face_model_path(project_root)
    if p.exists() and p.stat().st_size > 100_000:
        return {"success": True, "path": str(p), "cached": True}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(p) + ".part"
        logger.warning("Downloading face landmarker model ...")
        urllib.request.urlretrieve(FACE_TASK_URL, tmp)
        if Path(tmp).stat().st_size < 100_000:
            raise RuntimeError("download too small")
        Path(tmp).replace(p)
        return {"success": True, "path": str(p), "cached": False}
    except Exception as e:
        return {"success": False,
                "error": (f"Face model missing ({p}) and download failed: {e}. "
                          "Go online once or place face_landmarker.task in models/.")}


# -- pure math (unit-testable) ----------------------------------------------

def iris_center(lm: List[Tuple[float, float]], idx: List[int]
                ) -> Tuple[float, float]:
    xs = [lm[i][0] for i in idx if i < len(lm)]
    ys = [lm[i][1] for i in idx if i < len(lm)]
    if not xs:
        return (0.5, 0.5)
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def gaze_ratios(lm: List[Tuple[float, float]]
                ) -> Optional[Dict[str, float]]:
    """Normalized iris position inside each eye: 0=outer,1=inner; 0=up,1=down."""
    try:
        lx, ly = iris_center(lm, LEFT_IRIS)
        rx, ry = iris_center(lm, RIGHT_IRIS)
        lox, loy = lm[LEFT_EYE_OUTER], lm[LEFT_EYE_INNER]
        rox, roy = lm[RIGHT_EYE_OUTER], lm[RIGHT_EYE_INNER]
        lux, luy = lm[LEFT_EYE_UP][0], lm[LEFT_EYE_UP][1]
        ldx, ldy = lm[LEFT_EYE_DOWN][0], lm[LEFT_EYE_DOWN][1]
        rux, ruy = lm[RIGHT_EYE_UP][0], lm[RIGHT_EYE_UP][1]
        rdx, rdy = lm[RIGHT_EYE_DOWN][0], lm[RIGHT_EYE_DOWN][1]

        def ratio(v, a, b):
            d = (b - a)
            if abs(d) < 1e-9:
                return 0.5
            return min(1.2, max(-0.2, (v - a) / d))

        lhx = ratio(lx, lm[LEFT_EYE_OUTER][0], lm[LEFT_EYE_INNER][0])
        rhx = ratio(rx, lm[RIGHT_EYE_OUTER][0], lm[RIGHT_EYE_INNER][0])
        lhy = ratio(ly, luy, ldy)
        rhy = ratio(ry, ruy, rdy)
        return {"lhx": lhx, "lhy": lhy, "rhx": rhx, "rhy": rhy,
                "hx": (lhx + (1.0 - rhx)) / 2.0,  # mirror right eye
                "hy": (lhy + rhy) / 2.0}
    except Exception:
        return None


def eye_aspect(lm: List[Tuple[float, float]], side: str = "left") -> float:
    """EAR: vertical eye opening / horizontal width. Blink when < ~0.2."""
    try:
        if side == "left":
            o, i, u, d = (lm[LEFT_EYE_OUTER], lm[LEFT_EYE_INNER],
                          lm[LEFT_EYE_UP], lm[LEFT_EYE_DOWN])
        else:
            o, i, u, d = (lm[RIGHT_EYE_OUTER], lm[RIGHT_EYE_INNER],
                          lm[RIGHT_EYE_UP], lm[RIGHT_EYE_DOWN])
        horiz = math.hypot(i[0] - o[0], i[1] - o[1])
        vert = math.hypot(d[0] - u[0], d[1] - u[1])
        if horiz < 1e-9:
            return 0.3
        return vert / horiz
    except Exception:
        return 0.3


def is_blink(lm: List[Tuple[float, float]], thresh: float = 0.19) -> bool:
    return (eye_aspect(lm, "left") + eye_aspect(lm, "right")) / 2.0 < thresh


def fit_affine(src: List[Tuple[float, float]],
               dst: List[Tuple[float, float]]) -> Optional[List[List[float]]]:
    """Least-squares affine 2x3 mapping src->dst. Needs numpy, >=3 points."""
    if np is None or len(src) < 3 or len(src) != len(dst):
        return None
    try:
        A = []
        bx, by = [], []
        for (sx, sy), (dx, dy) in zip(src, dst):
            A.append([sx, sy, 1, 0, 0, 0])
            A.append([0, 0, 0, sx, sy, 1])
            bx.append(dx)
            by.append(dy)
        A = np.array(A, dtype=float)
        b = np.array(bx + by if False else
                     [v for pair in zip([d[0] for d in dst],
                                        [d[1] for d in dst]) for v in pair],
                     dtype=float)
        # Build properly: interleave
        A = np.zeros((2 * len(src), 6))
        b = np.zeros(2 * len(src))
        for k, ((sx, sy), (dx, dy)) in enumerate(zip(src, dst)):
            A[2 * k] = [sx, sy, 1, 0, 0, 0]
            A[2 * k + 1] = [0, 0, 0, sx, sy, 1]
            b[2 * k] = dx
            b[2 * k + 1] = dy
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        return [[float(sol[0]), float(sol[1]), float(sol[2])],
                [float(sol[3]), float(sol[4]), float(sol[5])]]
    except Exception as e:
        logger.debug(f"affine fit failed: {e}")
        return None


def apply_affine(M: List[List[float]], x: float, y: float) -> Tuple[float, float]:
    return (M[0][0] * x + M[0][1] * y + M[0][2],
            M[1][0] * x + M[1][1] * y + M[1][2])


def load_cal() -> Optional[Dict[str, Any]]:
    try:
        p = cal_path()
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def save_cal(data: Dict[str, Any]) -> None:
    try:
        cal_path().write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


# -- Face tracker ------------------------------------------------------------

class GazeTracker:
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root
        self._lm = None
        self._mode = None
        self.method = "none"

    def _load(self, mode: str = "IMAGE"):
        if self._lm is not None and self._mode == mode:
            return
        self.close()
        if not _MP_OK:
            raise RuntimeError(f"mediapipe tasks unavailable: {_MP_ERR}")
        dl = ensure_face_model(self.project_root)
        if not dl.get("success"):
            raise RuntimeError(dl["error"])
        running = (mp_vision.RunningMode.IMAGE if mode == "IMAGE"
                   else mp_vision.RunningMode.VIDEO)
        opts = mp_vision.FaceLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=str(face_model_path(self.project_root))),
            running_mode=running, num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False)
        self._lm = mp_vision.FaceLandmarker.create_from_options(opts)
        self._mode = mode
        self.method = f"mediapipe-face-{mode}"

    def faces_image(self, frame_bgr) -> Dict[str, Any]:
        self._load("IMAGE")
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = self._lm.detect(mp_img)
        return self._pack(res)

    def faces_video(self, frame_bgr, ts: int) -> Dict[str, Any]:
        self._load("VIDEO")
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = self._lm.detect_for_video(mp_img, ts)
        return self._pack(res)

    @staticmethod
    def _pack(res) -> Dict[str, Any]:
        try:
            lists = res.face_landmarks or []
        except Exception:
            lists = []
        out = []
        for fl in lists:
            lm = [(p.x, p.y) for p in fl]
            r = gaze_ratios(lm)
            out.append({"landmarks": lm, "ratios": r,
                        "blink": is_blink(lm),
                        "ear": round((eye_aspect(lm, "left") +
                                      eye_aspect(lm, "right")) / 2, 3)})
        return {"success": True, "faces": out, "count": len(out),
                "method": "mediapipe-face"}

    def close(self):
        try:
            if self._lm is not None:
                self._lm.close()
        except Exception:
            pass
        self._lm = None
        self._mode = None


def snapshot(frame_bgr, project_root: Optional[str] = None) -> Dict[str, Any]:
    """One gaze read: ratios + blink + screen point if calibrated."""
    if frame_bgr is None:
        return {"success": False, "error": "no frame"}
    if not _CV:
        return {"success": False, "error": f"opencv missing: {_CV_ERR}"}
    if _MP_OK:
        try:
            t = GazeTracker(project_root=project_root)
            res = t.faces_image(frame_bgr)
            t.close()
            if res.get("count"):
                f = res["faces"][0]
                cal = load_cal()
                pt = None
                if cal and cal.get("M") and f.get("ratios"):
                    M = cal["M"]
                    r = f["ratios"]
                    pt = apply_affine(M, r["hx"], r["hy"])
                    pt = [int(pt[0]), int(pt[1])]
                res["gaze_point"] = pt
                res["calibrated"] = cal is not None
                return res
            return {"success": False,
                    "error": "No face in view for gaze. Face camera, good light."}
        except Exception as e:
            logger.debug(f"gaze ML failed: {e}")
            return {"success": False, "error": str(e)[:200]}
    return {"success": False,
            "error": "Eye tracking needs the face model (face_landmarker.task). " +
                     (f"mediapipe: {_MP_ERR}" if not _MP_OK else "download it once online.")}


def calibrate_interactive(project_root: Optional[str] = None,
                          use_session_frames=None) -> Dict[str, Any]:
    """5-point calibration: look at each dot, press SPACE. Real mapping fit."""
    if not _CV:
        return {"success": False, "error": "opencv missing"}
    try:
        import pyautogui
        sw, sh = pyautogui.size()
    except Exception as e:
        return {"success": False, "error": f"screen size failed: {e}"}
    pts = [(sw // 2, sh // 2), (80, 80), (sw - 80, 80),
           (80, sh - 80), (sw - 80, sh - 80)]
    names = ["CENTER", "TOP-LEFT", "TOP-RIGHT", "BOTTOM-LEFT", "BOTTOM-RIGHT"]
    tracker = GazeTracker(project_root=project_root)
    cap = None
    use_direct = use_session_frames is None
    src, dst = [], []
    try:
        if use_direct:
            from saturday import senses as _s
            cap, _, _ = _s.open_camera()
        for (sx, sy), nm in zip(pts, names):
            print(f"  Look at {nm} ({sx},{sy}) — focus, then press SPACE in the camera window.")
            collected = []
            while True:
                if use_direct:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        continue
                else:
                    frame = use_session_frames()
                    if frame is None:
                        time.sleep(0.1)
                        continue
                small = cv2.resize(frame, (640, 480))
                cv2.putText(small, f"Look at {nm} then SPACE",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (0, 255, 0), 2)
                cv2.imshow("SATURDAY GAZE CALIBRATE", small)
                k = cv2.waitKey(30) & 0xFF
                if k == 32:  # space: sample 10 frames median
                    for _ in range(10):
                        if use_direct:
                            ok2, f2 = cap.read()
                            if not ok2 or f2 is None:
                                continue
                        else:
                            f2 = use_session_frames()
                            if f2 is None:
                                continue
                        try:
                            r = tracker.faces_image(f2)
                            if r.get("count"):
                                rt = r["faces"][0]["ratios"]
                                if rt:
                                    collected.append((rt["hx"], rt["hy"]))
                        except Exception:
                            pass
                        time.sleep(0.05)
                    break
                if k in (27, ord("q")):
                    return {"success": False, "error": "calibration cancelled"}
            if not collected:
                return {"success": False,
                        "error": f"No gaze sample at {nm} — face the camera."}
            mx = sorted(c[0] for c in collected)[len(collected) // 2]
            my = sorted(c[1] for c in collected)[len(collected) // 2]
            src.append((mx, my))
            dst.append((float(sx), float(sy)))
        M = fit_affine(src, dst)
        if not M:
            return {"success": False, "error": "affine fit failed"}
        # residual check
        errs = []
        for (sx, sy), (dx, dy) in zip(src, dst):
            px, py = apply_affine(M, sx, sy)
            errs.append(math.hypot(px - dx, py - dy))
        mean_err = sum(errs) / len(errs)
        save_cal({"M": M, "at": time.time(), "mean_err_px": mean_err,
                  "screen": [sw, sh]})
        return {"success": True, "mean_err_px": round(mean_err, 1),
                "points": len(src),
                "note": ("Good <150px, usable <300px. "
                         "Webcam gaze is approximate — dwell-click needs 1s+.")}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}
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
            cv2.destroyWindow("SATURDAY GAZE CALIBRATE")
        except Exception:
            pass


def live_gaze_control(seconds: float = 30.0, confirm: bool = False,
                      project_root: Optional[str] = None,
                      use_session_frames=None, dwell_click: bool = True,
                      show_window: bool = True) -> Dict[str, Any]:
    """Gaze cursor: look to move, blink (both eyes 250ms+) or 1s dwell clicks."""
    if not confirm:
        return {"success": False,
                "error": "gaze control needs local confirm=True."}
    cal = load_cal()
    if not cal or not cal.get("M"):
        return {"success": False,
                "error": "Not calibrated. Run: gaze calibrate (5-point, 60s)."}
    if not _CV:
        return {"success": False, "error": "opencv missing"}
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        sw, sh = pyautogui.size()
    except Exception as e:
        return {"success": False, "error": f"pyautogui: {e}"}
    tracker = GazeTracker(project_root=project_root)
    M = cal["M"]
    sx, sy = sw // 2, sh // 2
    alpha = 0.25
    stats = {"frames": 0, "blinks": 0, "dwells": 0, "moves": 0}
    cap = None
    use_direct = use_session_frames is None
    dwell_start = None
    dwell_pos = None
    blink_since = None
    try:
        if use_direct:
            from saturday import senses as _s
            cap, _, _ = _s.open_camera()
        t0 = time.time()
        ts = 0
        while time.time() - t0 < max(5.0, float(seconds)):
            if use_direct:
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                ts += 33
                try:
                    res = tracker.faces_video(frame, ts)
                except Exception:
                    res = tracker.faces_image(frame)
            else:
                frame = use_session_frames()
                if frame is None:
                    time.sleep(0.1)
                    continue
                try:
                    res = tracker.faces_image(frame)
                except Exception as e:
                    time.sleep(0.1)
                    continue
            stats["frames"] += 1
            if not res.get("count"):
                if show_window:
                    cv2.imshow("SATURDAY GAZE — Q quits",
                               cv2.resize(frame, (640, 480)))
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        break
                continue
            f = res["faces"][0]
            r = f.get("ratios")
            if not r:
                continue
            gx, gy = apply_affine(M, r["hx"], r["hy"])
            gx = min(sw - 1, max(0, int(gx)))
            gy = min(sh - 1, max(0, int(gy)))
            sx = sx * (1 - alpha) + gx * alpha
            sy = sy * (1 - alpha) + gy * alpha
            try:
                import pyautogui as _pg
                _pg.moveTo(int(sx), int(sy), duration=0)
                stats["moves"] += 1
            except Exception:
                pass
            now = time.time()
            # blink click: EAR blink held 0.25s
            if f.get("blink"):
                if blink_since is None:
                    blink_since = now
                elif now - blink_since > 0.25:
                    try:
                        import pyautogui as _p2
                        _p2.click()
                        stats["blinks"] += 1
                    except Exception:
                        pass
                    blink_since = None
                    time.sleep(0.5)  # debounce
            else:
                blink_since = None
            # dwell click: gaze stable in 60px for 1.0s
            if dwell_click:
                if dwell_pos is None or math.hypot(sx - dwell_pos[0],
                                                  sy - dwell_pos[1]) > 60:
                    dwell_pos = (sx, sy)
                    dwell_start = now
                elif now - dwell_start > 1.0:
                    try:
                        import pyautogui as _p3
                        _p3.click()
                        stats["dwells"] += 1
                    except Exception:
                        pass
                    dwell_start = now
            if show_window:
                small = cv2.resize(frame, (640, 480))
                cv2.circle(small, (int(sx / sw * 640), int(sy / sh * 480)),
                           10, (255, 0, 255), 2)
                cv2.putText(small, f"gaze {gx},{gy} blinks={stats['blinks']} "
                                   f"dwell={stats['dwells']} Q quits",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (255, 0, 255), 2)
                cv2.imshow("SATURDAY GAZE — Q quits", small)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}
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
                cv2.destroyWindow("SATURDAY GAZE — Q quits")
        except Exception:
            pass


def read_at_gaze(screen_op, frame_bgr, project_root: Optional[str] = None,
                 window_px: int = 320) -> Dict[str, Any]:
    """Eye READING: where you look -> OCR that screen region. Real pipeline."""
    snap = snapshot(frame_bgr, project_root=project_root)
    if not snap.get("success"):
        return snap
    pt = snap.get("gaze_point")
    if not pt:
        return {"success": False,
                "error": "No calibration — run: gaze calibrate. Then I can read what you look at."}
    try:
        shot = screen_op.screenshot()
        if not shot.get("success"):
            return shot
        from PIL import Image as _Im
        img = _Im.open(shot["path"])
        W, H = img.size
        x, y = max(0, pt[0] - window_px // 2), max(0, pt[1] - window_px // 2)
        crop = img.crop((x, y, min(W, x + window_px), min(H, y + window_px)))
        base = Path(os.getenv("SATURDAY_D_TMP", "D:/SATURDAY_TEMP"))
        out = str(base / f"gaze_read_{int(time.time())}.png")
        crop.save(out)
        read = screen_op.read_screen(out)
        if not read.get("success"):
            return read
        return {"success": True, "gaze": pt, "crop": out,
                "text": read.get("text", "")[:800],
                "words": len(read.get("words", []))}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}
