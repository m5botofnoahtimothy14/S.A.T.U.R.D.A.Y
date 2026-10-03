"""SATURDAY Presence — the human layer: sees you, greets you once, behaves.

PresenceLoop runs off the always-on camera hub (no extra capture cost):
- Notices a face (and WHO, via the identity gallery) within ~2s.
- Greets ONCE per arrival (face lost ≥ 6s = new arrival), spoken through
  the humanized voice, never during quiet mode, never mid-thought.
- Emits speech only when something changed (face appeared / identity
  changed) — the classic robot bug of "How may I help?" every 10s is
  designed out: cooldown + seen-set + dnd.

Proactive lines are drawn from humanvoice, so SATURDAY says sentences,
never status dumps.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("SATURDAY.Presence")

POLL_SECONDS = 1.5
ARRIVAL_GAP = 6.0      # face gone this long = new arrival
REPEAT_COOLDOWN = 900.0  # never re-greet the same person within 15 min
WATCH_COOLDOWN = 300.0  # unknown-face snapshots at most every 5 min
WATCH_DIRNAME = "watch"


class PresenceLoop:
    def __init__(self, session):
        self.session = session
        self.core = session.core
        self.face_seen = False
        self.present_name: Optional[str] = None
        self.last_greeted_at = 0.0
        self.last_greeted_name = ""
        self.greets = 0
        self.running = False
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="presence")
        self._thread.start()
        logger.info("Presence loop running.")

    def stop(self):
        self._stop.set()
        self.running = False
        if self._thread:
            self._thread.join(timeout=4.0)
        self._thread = None

    def _quiet(self) -> bool:
        mind = getattr(self.session, "mind", None)
        if mind and mind.prefs.get("dnd"):
            return True
        if self.session.inbox and any(j.get("status") == "running" for j in self.session.inbox):
            return True
        return False

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:
                logger.debug(f"presence tick failed: {e}")
            self._stop.wait(POLL_SECONDS)

    def tick(self) -> Optional[str]:
        """One observation. Returns the spoken line if it greeted."""
        cam = self.session.camera
        if not cam.running or cam.get_frame(max_age=6.0) is None:
            self.face_seen = False
            self.present_name = None
            return None
        from saturday import senses

        frame = cam.get_frame(max_age=6.0)
        faces = senses.find_faces(frame)
        boxes = faces.get("boxes", []) if faces.get("success") else []
        now = time.time()
        if not boxes:
            if self.face_seen and (now - self.last_greeted_at > 0) and self.present_name is None:
                pass
            self.face_seen = False
            self.present_name = None
            return None
        self.face_seen = True
        name = None
        try:
            biggest = max(boxes, key=lambda b: b["w"] * b["h"])
            crop = frame[biggest["y"]:biggest["y"] + biggest["h"],
                         biggest["x"]:biggest["x"] + biggest["w"]]
            name, _ = self.core._gallery().recognize(crop)
        except Exception:
            pass
        self.present_name = name
        if self._quiet():
            return None
        if name is None or str(name).lower() == "unknown":
            self._watch_snapshot(frame)  # unknown face near the laptop: keep evidence
        if (name and name == self.last_greeted_name
                and now - self.last_greeted_at < REPEAT_COOLDOWN):
            return None
        if self.last_greeted_at and now - self.last_greeted_at < 20.0:
            return None
        return self._greet(name)

    def _watch_snapshot(self, frame) -> Optional[str]:
        """Theft/threat evidence: unknown face near the laptop → timestamped
        JPEG on D: (bounded dir, 5-min cooldown) + dashboard event. Never
        facial-recognition-accuses: it stores 'unknown face seen', not a name."""
        now = time.time()
        if now - getattr(self, "_last_watch", 0.0) < WATCH_COOLDOWN:
            return None
        try:
            import os as _os
            from pathlib import Path as _P

            base = _P(_os.getenv("SATURDAY_D_TMP", "D:/SATURDAY_TEMP")) / WATCH_DIRNAME
            base.mkdir(parents=True, exist_ok=True)
            for old in sorted(base.glob("watch_*.jpg"))[:-20]:
                try:
                    old.unlink()
                except Exception:
                    pass
            import cv2 as _cv2

            path = str(base / f"watch_{int(now)}.jpg")
            _cv2.imwrite(path, frame)
            self._last_watch = now
            logger.warning(f"WATCH: unknown face snapshot {path}")
            try:
                dash = getattr(getattr(self.session, "core", None), "_dashboard", None)
                if dash is not None:
                    dash.note("watch", f"unknown face near laptop ({path})")
            except Exception:
                pass
            return path
        except Exception as e:
            logger.debug(f"watch snapshot failed: {e}")
            return None

    def _greet(self, name: Optional[str]) -> str:
        from saturday import humanvoice as hv

        try:
            mood = None
            from saturday import senses
            frame = self.session.camera.get_frame(max_age=4.0)
            if frame is not None:
                m = senses.mood(frame)
                mood = m.get("mood") if m.get("success") else None
            line = hv.arrival_line(name, mood)
        except Exception:
            hour = time.localtime().tm_hour
            part = "evening" if hour >= 17 else "afternoon" if hour >= 12 else "morning"
            line = f"Good {part}, {name}." if name else f"Good {part}."
        self.last_greeted_at = time.time()
        self.last_greeted_name = name or ""
        self.greets += 1
        self.core._speak(line)
        logger.info(f"Presence greeting: {line}")
        return line

    def startup_hello(self) -> None:
        """First words after boot — after services warm, once."""
        try:
            self._stop.wait(20.0)  # let camera/heal/ears come up quietly
        except Exception:
            pass
        if self._stop.is_set() or self._quiet():
            return
        from saturday import humanvoice as hv
        try:
            core_ok = bool(getattr(self.core, "is_running", False))
            vault_ok = bool(getattr(self.core.pmv, "vault_mounted", False))
            line = hv.startup_line(core_ok, vault_ok)
        except Exception:
            line = "SATURDAY online. All systems ready."
        self.core._speak(line)
        logger.info(f"Startup hello: {line}")

    def status(self) -> Dict[str, Any]:
        return {"running": self.running, "face_seen": self.face_seen,
                "who": self.present_name, "greets": self.greets}
