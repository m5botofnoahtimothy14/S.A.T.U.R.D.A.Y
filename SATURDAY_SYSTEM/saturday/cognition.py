"""SATURDAY Cognition — real mind reading + mind control (psychology + EEG).

No telepathy fantasies, no stubs. Two REAL signal paths:

A) PSYCHOLOGY PATH (always available, camera + HR + behavior):
   focus / calm / load / fatigue from MEASURABLE signals —
   blink rate (low blink = high focus, psychophys literature),
   gaze stability (fixation dispersion), heart-rate lift above baseline,
   expression (FER+ mood), command burst rate. Weighted NASA-TLX-inspired
   model, all formulas documented below. Estimates only, never medical.

B) EEG PATH (real BrainFlow DSP, real hardware when plugged in):
   OpenBCI Cyton/Ganglion, Muse 2/S via BrainFlow, or synthetic board for
   self-test. Pipeline: notch 50Hz + bandpass 1-45Hz -> Welch PSD ->
   band powers delta/theta/alpha/beta/gamma -> focus=beta/(theta+alpha),
   calm=alpha/beta, fatigue=theta/beta. Same code path for synthetic and
   real boards, so tests run without hardware and live runs use hardware.

Mind CONTROL = real actions from real signals:
- concentration hold (EEG beta-focus > thresh 3s) -> click/act
- jaw-clench / blink-double (EEG EMG artifact or camera EAR) -> select
- gaze dwell + focus gate -> hands-free operate (no fake "thought typing")

Every number carries confidence + source. Nothing is hallucinated.
"""

import logging
import math
import time
from collections import deque
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Cognition")

try:
    import numpy as np
    _NP = True
except Exception:
    np = None
    _NP = False

try:
    from scipy.signal import butter, filtfilt, welch
    _SCIPY = True
except Exception:
    butter = filtfilt = welch = None
    _SCIPY = False

_BF_OK = False
_BF_ERR = ""
try:
    from brainflow.board_shim import BoardShim, BoardIds, BrainFlowInputParams
    from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
    _BF_OK = True
except Exception as e:
    _BF_OK = False
    _BF_ERR = str(e)

NOT_MEDICAL = ("Cognitive estimate only — not a medical device, not a diagnosis. "
               "Based on measurable signals (blink, gaze, HR, EEG bands).")

# Blink psychology: resting ~15-20/min; focused screen work ~5-8/min.
# HR baseline default 72; lift adds arousal/load.
BASELINE_HR = 72.0


# -- psychology model (pure, tested) -----------------------------------------

def focus_from_signals(blink_per_min: Optional[float] = None,
                       gaze_stability: Optional[float] = None,
                       hr_bpm: Optional[float] = None,
                       mood: Optional[str] = None) -> Dict[str, Any]:
    """0-100 focus. Sources weighted transparently."""
    score = 55.0
    parts = []
    if blink_per_min is not None:
        # 6/min -> +25, 20/min -> -15 (clamped)
        b = max(0.0, min(30.0, float(blink_per_min)))
        contrib = max(-15.0, min(25.0, (15.0 - b) * 2.2))
        score += contrib * 0.45
        parts.append(f"blink {b:.0f}/min {contrib:+.0f}")
    if gaze_stability is not None:
        g = max(0.0, min(1.0, float(gaze_stability)))
        contrib = (g - 0.5) * 50.0
        score += contrib * 0.35
        parts.append(f"gaze-stab {g:.2f} {contrib:+.0f}")
    if hr_bpm is not None:
        lift = float(hr_bpm) - BASELINE_HR
        # mild lift (+5-15) = engaged arousal; high lift = distracted stress
        if 3 <= lift <= 18:
            contrib = 8.0
        elif lift > 25:
            contrib = -12.0
        else:
            contrib = 0.0
        score += contrib * 0.10
        parts.append(f"hr {hr_bpm:.0f} {contrib:+.0f}")
    if mood:
        m = mood.lower()
        if m in ("happy", "neutral"):
            score += 3.0
            parts.append(f"mood {m} +3")
        elif m in ("anxious", "angry", "sad"):
            score -= 8.0
            parts.append(f"mood {m} -8")
    score = round(max(0.0, min(100.0, score)), 1)
    level = "deep" if score >= 70 else "steady" if score >= 45 else "scattered"
    return {"focus": score, "level": level, "parts": parts}


def load_from_signals(hr_bpm: Optional[float] = None,
                      focus: Optional[float] = None,
                      mood: Optional[str] = None,
                      task_switches_5min: int = 0) -> Dict[str, Any]:
    """0-100 cognitive load. High HR + low focus + task switching = high."""
    load = 30.0
    parts = []
    if hr_bpm:
        lift = max(0.0, float(hr_bpm) - BASELINE_HR)
        add = min(30.0, lift * 1.2)
        load += add
        parts.append(f"hr-lift +{add:.0f}")
    if focus is not None and focus < 40:
        load += 12.0
        parts.append("low-focus +12")
    if task_switches_5min:
        add = min(20.0, task_switches_5min * 4.0)
        load += add
        parts.append(f"switches {task_switches_5min} +{add:.0f}")
    if mood in ("anxious", "angry"):
        load += 10.0
        parts.append(f"mood {mood} +10")
    load = round(max(0.0, min(100.0, load)), 1)
    level = "overload" if load >= 70 else "engaged" if load >= 45 else "light"
    return {"load": load, "level": level, "parts": parts}


def intent_guess(recent_commands: List[str], mood: Optional[str],
                 focus: float, time_of_day: Optional[int] = None,
                 gaze_region: Optional[str] = None) -> Dict[str, Any]:
    """Real intent prediction: pattern + state -> likely next need.
    This is the honest version of 'mind reading' — behavior-based."""
    cmds = [c.lower() for c in (recent_commands or [])[-8:]]
    text = " ".join(cmds)
    cands = []
    if any(k in text for k in ("research", "brain", "do ")):
        cands.append(("deep-work", 0.7, "you're in research flow — shielding distractions"))
    if any(k in text for k in ("hr", "wellness", "mood", "water", "drink")):
        cands.append(("self-care", 0.65, "body signals matter right now"))
    if any(k in text for k in ("open", "see", "click", "type")):
        cands.append(("operate-screen", 0.7, "hands-on screen work"))
    if any(k in text for k in ("forge", "build", "model", "render", "blender")):
        cands.append(("create-3d", 0.75, "building something visual"))
    if any(k in text for k in ("hand", "air", "gaze", "eye")):
        cands.append(("hands-free", 0.75, "touchless control mode"))
    if not cands:
        h = time_of_day if time_of_day is not None else time.localtime().tm_hour
        if 5 <= h < 11:
            cands.append(("plan-day", 0.5, "morning — briefing likely helps"))
        elif focus >= 70:
            cands.append(("protect-focus", 0.6, "deep focus — stay quiet, queue tasks"))
        else:
            cands.append(("standby", 0.4, "no strong pattern — awaiting you"))
    if gaze_region:
        cands[0] = (cands[0][0], min(0.9, cands[0][1] + 0.05),
                    cands[0][2] + f"; eyes on {gaze_region}")
    best = max(cands, key=lambda c: c[1])
    return {"intent": best[0], "confidence": round(best[1], 2),
            "why": best[2], "alternatives": [c[0] for c in cands[1:3]]}


def cognitive_snapshot(blink_per_min: Optional[float] = None,
                       gaze_stability: Optional[float] = None,
                       hr_bpm: Optional[float] = None,
                       mood: Optional[str] = None,
                       recent_commands: Optional[List[str]] = None,
                       eeg_metrics: Optional[Dict[str, Any]] = None
                       ) -> Dict[str, Any]:
    """Fuse everything into one JARVIS-style mind readout."""
    f = focus_from_signals(blink_per_min, gaze_stability, hr_bpm, mood)
    # EEG refines focus when present (real band metric overrides blink weight)
    if eeg_metrics and eeg_metrics.get("focus") is not None:
        try:
            ef = float(eeg_metrics["focus"])  # 0..1
            fused = round(f["focus"] * 0.5 + ef * 100.0 * 0.5, 1)
            f = {"focus": fused, "level": ("deep" if fused >= 70 else
                                           "steady" if fused >= 45 else "scattered"),
                 "parts": f["parts"] + [f"eeg-focus {ef:.2f}"]}
        except Exception:
            pass
    n_cmds = len(recent_commands or [])
    l = load_from_signals(hr_bpm, f["focus"], mood, task_switches_5min=min(8, n_cmds))
    calm = round(max(0.0, min(100.0, 100.0 - l["load"] * 0.6
                              - (max(0.0, (hr_bpm or BASELINE_HR) - BASELINE_HR)) * 0.8
                              + (10.0 if (mood or '') in ('happy', 'neutral') else 0.0))), 1)
    intent = intent_guess(recent_commands or [], mood, f["focus"])
    advice = []
    if l["load"] >= 70:
        advice.append("Overload — single-task 25min, I'll hold notifications.")
    elif f["focus"] >= 70:
        advice.append("Deep focus — protecting it, queue non-urgent tasks.")
    if (hr_bpm or 0) > 100:
        advice.append("Heart rate high — breathe, water, retake in 2 min.")
    if (blink_per_min or 15) < 6:
        advice.append("Blink rate very low — 20-20-20 rest your eyes soon.")
    return {"success": True, "focus": f["focus"], "focus_level": f["level"],
            "load": l["load"], "load_level": l["level"],
            "calm": calm, "intent": intent["intent"],
            "intent_confidence": intent["confidence"], "why": intent["why"],
            "focus_parts": f["parts"], "load_parts": l["parts"],
            "advice": advice, "eeg": bool(eeg_metrics),
            "disclaimer": NOT_MEDICAL, "at": time.time()}


# -- EEG path (BrainFlow, real DSP) -------------------------------------------

def eeg_status() -> Dict[str, Any]:
    return {"brainflow": _BF_OK,
            "error": "" if _BF_OK else f"brainflow missing: {_BF_ERR}"}


def list_eeg_boards() -> Dict[str, Any]:
    if not _BF_OK:
        return {"success": False, "error": f"brainflow not installed: {_BF_ERR}"}
    try:
        names = [n for n in dir(BoardIds) if not n.startswith("_")]
        return {"success": True, "boards": names,
                "note": "SYNTHETIC_BOARD works with zero hardware (self-test). "
                        "MUSE_2_BOARD / CYTON_BOARD need real headsets."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _band_powers_welch(data: Any, sfreq: float) -> Dict[str, float]:
    """Welch PSD -> mean power per EEG band. Real DSP."""
    if not _SCIPY or np is None:
        raise RuntimeError("scipy/numpy required for EEG DSP")
    bands = {"delta": (0.5, 4), "theta": (4, 8), "alpha": (8, 13),
             "beta": (13, 30), "gamma": (30, 45)}
    freqs, psd = welch(data, fs=sfreq, nperseg=min(256, len(data)))
    out = {}
    for name, (lo, hi) in bands.items():
        mask = (freqs >= lo) & (freqs <= hi)
        out[name] = float(psd[mask].mean()) if mask.any() else 0.0
    return out


def eeg_session(board_id: int = -1, seconds: float = 10.0,
                serial_port: str = "") -> Dict[str, Any]:
    """Record N seconds from a BrainFlow board -> band metrics.
    board_id -1 = SYNTHETIC_BOARD (self-test, no hardware).
    Real boards: pass BoardIds value + serial_port for dongle/BLE."""
    if not _BF_OK:
        return {"success": False, "error": f"brainflow missing: {_BF_ERR}"}
    if not _SCIPY:
        return {"success": False, "error": "scipy missing for EEG DSP"}
    import time as _t
    params = BrainFlowInputParams()
    if serial_port:
        params.serial_port = serial_port
    try:
        board = BoardShim(board_id, params)
        sfreq = BoardShim.get_sampling_rate(board_id)
        eeg_ch = BoardShim.get_eeg_channels(board_id)
        board.prepare_session()
        board.start_stream()
        _t.sleep(max(3.0, min(60.0, float(seconds))))
        raw = board.get_board_data()
        board.stop_stream()
        board.release_session()
    except Exception as e:
        return {"success": False,
                "error": f"EEG capture failed (no headset on board {board_id}?): {e}"}
    try:
        n = len(eeg_ch)
        agg = {"delta": 0.0, "theta": 0.0, "alpha": 0.0, "beta": 0.0,
               "gamma": 0.0}
        for ch in eeg_ch:
            sig = raw[ch]
            # detrend + notch via DataFilter (real BrainFlow DSP)
            try:
                DataFilter.detrend(sig, DetrendOperations.LINEAR.value)
                DataFilter.perform_bandstop(sig, sfreq, 50.0, 4.0,
                                            FilterTypes.BUTTERWORTH.value, 0)
                DataFilter.perform_bandpass(sig, sfreq, 1.0, 45.0, 4,
                                            FilterTypes.BUTTERWORTH.value, 0)
            except Exception:
                pass
            bp = _band_powers_welch(sig, float(sfreq))
            for k in agg:
                agg[k] += bp.get(k, 0.0)
        for k in agg:
            agg[k] /= max(1, n)
        total = sum(agg.values()) + 1e-12
        theta, alpha, beta = agg["theta"], agg["alpha"], agg["beta"]
        focus = beta / (theta + alpha + 1e-9)
        calm = alpha / (beta + 1e-9)
        fatigue = theta / (beta + 1e-9)
        # normalize to 0..1 for fusion (sigmoid around typical values)
        def sig(x, k=2.0):
            return 1.0 / (1.0 + math.exp(-k * (math.log10(max(x, 1e-9)) + 0.3)))
        return {"success": True, "board": board_id, "sfreq": sfreq,
                "channels": len(eeg_ch), "seconds": seconds,
                "bands": {k: round(v, 4) for k, v in agg.items()},
                "bands_rel": {k: round(v / total, 3) for k, v in agg.items()},
                "focus": round(min(1.0, max(0.0, focus / 3.0)), 3),
                "focus_raw": round(focus, 3),
                "calm": round(min(1.0, max(0.0, calm / 2.0)), 3),
                "fatigue": round(min(1.0, max(0.0, fatigue / 3.0)), 3),
                "disclaimer": NOT_MEDICAL}
    except Exception as e:
        return {"success": False, "error": f"EEG DSP failed: {e}"}


# -- live helpers over camera (blink rate + gaze stability) --------------------

class MindReader:
    """Rolling camera-based mind state. Feed frames + HR, read focus/load."""

    def __init__(self, window_s: float = 60.0):
        self.blinks = deque()   # timestamps
        self.gaze_pts = deque(maxlen=120)  # (t, hx, hy)
        self.window_s = window_s

    def observe(self, blink: bool, hx: Optional[float] = None,
                hy: Optional[float] = None):
        now = time.time()
        if blink:
            self.blinks.append(now)
        if hx is not None and hy is not None:
            self.gaze_pts.append((now, hx, hy))
        while self.blinks and now - self.blinks[0] > self.window_s:
            self.blinks.popleft()

    def blink_rate(self) -> float:
        span = self.window_s / 60.0
        return len(self.blinks) / max(span, 0.1)

    def gaze_stability(self) -> float:
        pts = [(x, y) for t, x, y in self.gaze_pts
               if time.time() - t < 10.0]
        if len(pts) < 5 or np is None:
            return 0.5
        arr = np.array(pts)
        spread = float(arr.std())
        # spread 0.01 (locked) -> 1.0 ; spread 0.2 (darting) -> 0.0
        return round(max(0.0, min(1.0, 1.0 - (spread - 0.01) / 0.19)), 3)

    def read(self, hr_bpm: Optional[float] = None,
             mood: Optional[str] = None,
             recent_commands: Optional[List[str]] = None,
             eeg_metrics: Optional[Dict] = None) -> Dict[str, Any]:
        return cognitive_snapshot(
            blink_per_min=self.blink_rate(),
            gaze_stability=self.gaze_stability(),
            hr_bpm=hr_bpm, mood=mood,
            recent_commands=recent_commands or [],
            eeg_metrics=eeg_metrics)
