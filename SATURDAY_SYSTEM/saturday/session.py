"""SATURDAY Session — the always-on autonomous core.

One boot starts EVERYTHING and keeps it warm for the whole session:
- CameraService : opens the camera ONCE (slow ~9s open happens in the
  background at boot, never per-command), holds a live frame hub +
  ring buffer so sense/mood/hr read instantly with zero re-opens.
- STT preload   : whisper tiny loads in background; hear/listen answer fast.
- Brain probe   : checks Ollama in background (no RAM-hogging preload).
- HomeBot link  : supervisor connects when broker/bot appear.
- Task queue    : `queue <goal>` runs unsupervised in background; `tasks` shows all.
- Dashboard hook: HUD auto-starts on 8099 (localhost only).

Shutdown reverses everything cleanly. All threads daemon + stoppable;
all buffers bounded; nothing here can hot-spin or leak over months.
"""

import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Session")


class CameraService:
    """Persistent camera: one slow open, then warm frames forever."""

    def __init__(self, fps: float = 8.0, ring_seconds: float = 45.0,
                 width: int = 320, height: int = 240):
        self.fps = fps
        self.width = width
        self.height = height
        self.ring = deque(maxlen=int(fps * ring_seconds))
        self.latest = None
        self.latest_at = 0.0
        self.opened_ok = False
        self.last_error = ""
        self.frames_captured = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def age(self) -> Optional[float]:
        with self._lock:
            return (time.time() - self.latest_at) if self.latest is not None else None

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="camera-service")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        self._thread = None

    def _open(self):
        import cv2

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("device 0 would not open")
        # Discard warmup frames (auto-exposure settles; first frames black).
        for _ in range(5):
            cap.read()
        return cap

    def _loop(self):
        import cv2

        cap = None
        try:
            cap = self._open()
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"Camera service: no camera ({e})")
            return
        self.opened_ok = True
        logger.info("Camera service: live.")
        interval = 1.0 / self.fps
        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if ok and frame is not None:
                    small = cv2.resize(frame, (self.width, self.height))
                    with self._lock:
                        self.latest = frame
                        self.latest_at = time.time()
                        self.ring.append((time.time(), small))
                        self.frames_captured += 1
                else:
                    time.sleep(0.2)
                    continue
                time.sleep(interval)
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"Camera service loop ended: {e}")
        finally:
            try:
                cap.release()
            except Exception:
                pass
            logger.info("Camera service: stopped.")

    def get_frame(self, max_age: float = 5.0):
        with self._lock:
            if self.latest is None or (time.time() - self.latest_at) > max_age:
                return None
            return self.latest.copy()

    def get_ring(self, seconds: float):
        """Frames from the last `seconds` (instant history for hr)."""
        cutoff = time.time() - seconds
        with self._lock:
            items = [(ts, f.copy()) for ts, f in self.ring if ts >= cutoff]
        return items

    def status(self) -> Dict[str, Any]:
        with self._lock:
            n = len(self.ring)
        return {"running": self.running, "opened_ok": self.opened_ok,
                "frames": self.frames_captured, "buffered": n,
                "age_s": round(self.age, 1) if self.age is not None else None,
                "error": self.last_error}


class SessionManager:
    def __init__(self, core):
        self.core = core
        self.started_at = 0.0
        self.camera = CameraService()
        self.stt_ready = False
        self.brain_ready: Optional[bool] = None
        self.dashboard_url = ""
        self.mind = None
        self.claps = None
        self.glow = None
        self.healer = None
        self.presence = None
        self.voice_gate = None
        self.server = None
        self._startup_hello_thread = None
        self.inbox: List[Dict[str, Any]] = []
        self._inbox_seq = 0
        self._inbox_event = threading.Event()
        self._inbox_worker = None
        self.share_persist = False
        self.share_hostname = ""
        self._share_watch = None
        self._dead = False
        self._threads: List[threading.Thread] = []

    def _bg(self, name: str, fn: Callable):
        t = threading.Thread(target=self._guarded(fn, name), daemon=True, name=name)
        t.start()
        self._threads.append(t)

    @staticmethod
    def _guarded(fn: Callable, name: str):
        def run():
            try:
                fn()
            except Exception as e:
                logger.warning(f"Session background '{name}' failed: {e}")
        return run

    # -- boot ----------------------------------------------------------------
    def boot(self):
        self.started_at = time.time()
        logger.info("Session boot: starting all services...")
        self.camera.start()  # slow open happens here, in background
        self._bg("stt-preload", self._preload_stt)
        self._bg("brain-probe", self._probe_brain)
        self._bg("homebot-start", self._start_homebot)
        self._bg("dashboard-start", self._start_dashboard)
        self._bg("identity-load", self._load_identity)
        self._bg("mind-start", self._start_mind)
        self._bg("claps-start", self._start_claps)
        self._bg("glow-start", self._start_glow)
        self._bg("heal-start", self._start_healer)
        self._start_inbox_worker()
        self._bg("voice-gate", self._start_voice_gate)
        self._bg("presence-start", self._start_presence)
        self._bg("startup-hello", self._startup_hello)
        self._bg("server-start", self._start_server)
        import os as _os
        if _os.getenv("SATURDAY_SHARE_PERSIST", "") == "1":
            self.share_persist = True
            self.share_hostname = _os.getenv("SATURDAY_SHARE_HOSTNAME", "")
            self._bg("share-watch", self._share_watch_loop)
        logger.info("Session boot dispatched (services warming up).")

    def _preload_stt(self):
        from saturday import ears

        if not ears.stt_available():
            return
        try:
            ears._get_model()
            self.stt_ready = True
            logger.info("Session: voice model preloaded, ears hot.")
        except Exception as e:
            logger.warning(f"STT preload failed: {e}")

    def _probe_brain(self):
        try:
            from saturday.brain import OllamaBrain

            self.brain_ready = OllamaBrain().available()
            logger.info(f"Session: brain probe → {self.brain_ready}.")
        except Exception:
            self.brain_ready = False

    def _start_homebot(self):
        try:
            self.core._homebot_link()
            logger.info("Session: homebot supervisor running.")
        except Exception as e:
            logger.warning(f"Homebot start failed: {e}")

    def _start_dashboard(self):
        try:
            out = self.core.process_command("dashboard 8099", trusted=True)
            if "http" in out:
                self.dashboard_url = out.split("http", 1)[1].split()[0]
                self.dashboard_url = "http" + self.dashboard_url
        except Exception as e:
            logger.warning(f"Dashboard autostart failed: {e}")

    def _load_identity(self):
        try:
            self.core._gallery()
            self.core._voicevault()
            logger.info("Session: identity gallery + voiceprint loaded.")
        except Exception as e:
            logger.warning(f"Identity load failed: {e}")

    def _start_mind(self):
        try:
            from saturday.mind import MindLoop

            self.mind = MindLoop(self.core, observe_fn=self.observe)
            self.mind.start()
            logger.info("Session: mind cognition loop running on its own.")
        except Exception as e:
            logger.warning(f"Mind start failed: {e}")

    def observe(self) -> Dict[str, Any]:
        """One snapshot for the mind: who is here, mood, command flow."""
        obs: Dict[str, Any] = {}
        try:
            frame = self.camera.get_frame(max_age=8.0)
            if frame is None:
                return obs
            from saturday import senses

            faces = senses.find_faces(frame)
            boxes = faces.get("boxes", []) if faces.get("success") else []
            obs["face_seen"] = bool(boxes)
            if boxes:
                biggest = max(boxes, key=lambda b: b["w"] * b["h"])
                crop = frame[biggest["y"]:biggest["y"] + biggest["h"],
                             biggest["x"]:biggest["x"] + biggest["w"]]
                try:
                    name, dist = self.core._gallery().recognize(crop)
                    obs["present"] = name
                    obs["face_dist"] = dist
                except Exception:
                    obs["present"] = None
                try:
                    mood = senses.mood(frame)
                    if mood.get("success"):
                        obs["mood"] = mood["mood"]
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"observe failed: {e}")
        try:
            counts = dict(getattr(self.core, "cmd_counts", {}))
            if counts:
                obs["commands"] = counts
                self.core.cmd_counts = {}
        except Exception:
            pass
        return obs

    def _start_claps(self):
        try:
            from saturday.claps import ClapListener

            self.claps = ClapListener(on_single=self._clap_single,
                                      on_double=self._clap_double)
            res = self.claps.start()
            if res.get("success"):
                logger.info("Session: clap listener live (1 clap = attention, 2 = quiet).")
        except Exception as e:
            logger.warning(f"Clap start failed: {e}")

    def _start_glow(self):
        try:
            from saturday.edgeglow import EdgeGlow

            self.glow = EdgeGlow()
            res = self.glow.start()
            if res.get("success"):
                logger.info("Session: edge glow live.")
        except Exception as e:
            logger.warning(f"Glow start failed: {e}")

    def _start_healer(self):
        try:
            from saturday.selfheal import SelfHeal

            self.healer = SelfHeal(self.core, self)
            self.healer.start()
            logger.info("Session: self-heal watchdog running.")
        except Exception as e:
            logger.warning(f"Healer start failed: {e}")

    def _start_voice_gate(self):
        try:
            from saturday.humanvoice import VoiceGate

            self.voice_gate = VoiceGate(self.core)
            logger.info("Session: voice gate ready.")
        except Exception as e:
            logger.warning(f"Voice gate failed: {e}")

    def _start_presence(self):
        try:
            from saturday.presence import PresenceLoop

            self.presence = PresenceLoop(self)
            self.presence.start()
            logger.info("Session: presence loop live (sees and greets you).")
        except Exception as e:
            logger.warning(f"Presence failed: {e}")

    def _startup_hello(self):
        try:
            if self.presence is None:
                from saturday.presence import PresenceLoop
                self.presence = PresenceLoop(self)
            self.presence.startup_hello()
        except Exception as e:
            logger.warning(f"Startup hello failed: {e}")

    def _start_server(self):
        try:
            from saturday.server import AlwaysOnServer

            self.server = AlwaysOnServer(self.core, self)
            self.server.start()
            logger.info("Session: always-on server live (tunnel + RTDB).")
        except Exception as e:
            logger.warning(f"Server start failed: {e}")

    # -- share keep-alive: tunnel stays up for months --------------------------
    def ensure_shared(self) -> dict:
        """Dashboard + token + tunnel, idempotent. Returns {url, token} or error."""
        try:
            if self.core._dashboard is None:
                self.core.process_command("dashboard 8099", trusted=True)
            dash = self.core._dashboard
            if dash is None or not dash.running:
                return {"success": False, "error": "dashboard would not start"}
            tok = dash.share()
            link = self.core._share_link()
            res = link.start(dash.port, hostname=self.share_hostname)
            if not res.get("success"):
                return res
            return {"success": True, "url": res["url"], "token": tok.get("token", "")}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    def _write_share_url(self, url: str, token: str) -> None:
        """Persist the current public URL so it's never lost in scrollback."""
        try:
            from pathlib import Path as _P
            p = _P(self.core.pmv.project_root) / "share_url.txt"
            p.write_text(f"URL={url}\nTOKEN={token}\nHUD=https://saturdayagenticai.vercel.app"
                         f"/?api={url}&token={token}\n")
        except Exception:
            pass

    def _share_watch_loop(self):
        while not self._dead:
            try:
                if self.share_persist:
                    link = self.core._share_link()
                    if not link.running:
                        res = self.ensure_shared()
                        if res.get("success"):
                            self._write_share_url(res["url"], res.get("token", ""))
                        logger.info(f"Share watch: {res.get('url', res.get('error'))}")
                    elif link.url:
                        self._write_share_url(link.url,
                                              getattr(self.core._dashboard, "token", ""))
            except Exception as e:
                logger.debug(f"Share watch failed: {e}")
            self._stop_watch_wait(30.0)

    def _stop_watch_wait(self, seconds: float):
        end = time.time() + seconds
        while time.time() < end and not self._dead:
            time.sleep(1.0)

    # -- task inbox: ONE worker, priority order (self task controller) -------
    def inbox_add(self, goal: str = "", kind: str = "agent", text: str = "",
                  priority: int = 3) -> str:
        self._inbox_seq += 1
        item = {"id": f"T{self._inbox_seq:03d}", "goal": goal, "kind": kind,
                "text": text, "priority": max(1, min(9, int(priority or 3))),
                "status": "pending", "created": time.time(),
                "finished": None, "result": ""}
        self.inbox.append(item)
        self.inbox = self.inbox[-100:]
        self._inbox_event.set()
        return item["id"]

    def inbox_list(self) -> List[Dict[str, Any]]:
        return list(self.inbox[-20:])

    def _start_inbox_worker(self):
        if self._inbox_worker and self._inbox_worker.is_alive():
            return
        self._inbox_worker = threading.Thread(target=self._inbox_loop, daemon=True,
                                              name="inbox-worker")
        self._inbox_worker.start()

    def _next_job(self) -> Optional[Dict[str, Any]]:
        pending = [i for i in self.inbox if i["status"] == "pending"]
        if not pending:
            return None
        pending.sort(key=lambda i: (-i["priority"], i["created"]))
        return pending[0]

    def _inbox_loop(self):
        from saturday.agent import AgentRunner, AgentTask, TemplateBrain, research_plan

        while not self._dead:
            self._inbox_event.wait(timeout=5.0)
            if self._dead:
                return
            job = self._next_job()
            if not job:
                self._inbox_event.clear()
                continue
            job["status"] = "running"
            try:
                if job["kind"] == "say":
                    self._inbox_say(job)
                else:
                    self._inbox_agent(job, AgentRunner, AgentTask, TemplateBrain, research_plan)
            except Exception as e:
                job["status"] = "failed"
                job["result"] = str(e)[:200]
                logger.warning(f"Inbox job {job['id']} failed: {e}")
            job["finished"] = time.time()

    def _inbox_say(self, job: Dict[str, Any]):
        mind = self.mind
        allowed = True
        if mind:
            try:
                allowed = mind._can_speak()
            except Exception:
                allowed = True
        if not allowed:
            job["status"] = "skipped"
            job["result"] = "suppressed (quiet mode / hourly cap)"
            return
        try:
            self.core._speak(job.get("text", ""))
            if mind:
                try:
                    mind._mark_spoke()
                except Exception:
                    pass
            job["status"] = "done"
            job["result"] = "spoken"
        except Exception as e:
            job["status"] = "failed"
            job["result"] = str(e)[:200]

    def _inbox_agent(self, job: Dict[str, Any], AgentRunner, AgentTask, TemplateBrain, research_plan):
        goal = job.get("goal", "")
        lowered = goal.lower()
        plan = research_plan(goal[9:].strip() or goal) if lowered.startswith("research ") else []
        try:
            from saturday.brain import OllamaBrain

            brain = OllamaBrain()
            use_brain = brain.available()
        except Exception:
            brain, use_brain = TemplateBrain(), False
        runner = AgentRunner(
            operator=self.core.screen, brain=brain if use_brain else TemplateBrain(),
            store_fn=lambda c, t: self.core.pmv.secure_store(c, tags=t),
            prompter=None, max_steps=20, confirm=True)
        finished = runner.run(AgentTask(goal, plan))
        self.core.agent_history.append(finished)
        self.core.agent_history = self.core.agent_history[-50:]
        job["status"] = "done" if finished.status == "done" else "failed"
        job["result"] = finished.summary()[:300]

    def _clap_single(self):
        try:
            self.core._speak("Yes?")
        except Exception:
            pass

        def cycle():
            try:
                from saturday import ears

                res = ears.hear_once(6.0)
                text = (res.get("text") or "").strip()
                if not text:
                    return
                if text.lower().rstrip(".!").strip() in ("goodbye", "stop", "quiet"):
                    return
                out = self.core.process_command(text, trusted=True)
                try:
                    self.core._speak(out)
                except Exception:
                    pass
            except Exception as e:
                logger.debug(f"Clap attention cycle failed: {e}")

        threading.Thread(target=cycle, daemon=True, name="clap-attention").start()

    def _clap_double(self):
        try:
            mind = self.mind
            dnd_on = not (mind.prefs.get("dnd") if mind else False)
            if dnd_on:
                try:
                    self.core._speak("Going quiet.")
                except Exception:
                    pass
            if mind:
                msg = mind.set_dnd(dnd_on)
            else:
                msg = "quiet" if dnd_on else "back"
            if not dnd_on:
                try:
                    self.core._speak("I'm back.")
                except Exception:
                    pass
            logger.info(f"Clap double → DND {dnd_on}: {msg}")
        except Exception as e:
            logger.debug(f"Clap idle toggle failed: {e}")

    # -- task queue (tasker: background unsupervised goals) --------------------
    def queue_goal(self, goal: str, priority: int = 3) -> str:
        """All background goals flow through the ONE priority inbox worker."""
        self._start_inbox_worker()
        return self.inbox_add(goal=goal, kind="agent", priority=priority)

    # -- introspection -----------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        cam = self.camera.status()
        mind = self.mind
        claps = self.claps
        try:
            gallery_names = len(getattr(self.core._gallery(), "names", [])) if hasattr(self.core, "_gallery") else 0
        except Exception:
            gallery_names = 0
        return {
            "uptime_s": round(time.time() - self.started_at, 1) if self.started_at else 0,
            "camera": ("live" if cam["running"] and cam["age_s"] is not None and cam["age_s"] < 5
                       else "starting" if cam["running"] else f"offline ({cam['error']})" if cam["error"] else "offline"),
            "camera_frames": cam["frames"],
            "ears": "hot" if self.stt_ready else "warming",
            "brain": ("ready" if self.brain_ready else "offline" if self.brain_ready is False else "probing"),
            "vault": "mounted" if self.core.pmv.vault_mounted else "locked",
            "homebot": (self.core._homebot.status()["link"] if self.core._homebot else "starting"),
            "dashboard": self.dashboard_url or "starting",
            "queued": sum(1 for i in self.inbox if i["status"] in ("pending", "running")),
            "inbox_depth": len([i for i in self.inbox if i["status"] == "pending"]),
            "mind": ("running" if mind and mind.running else "off"),
            "mind_ticks": mind.ticks if mind else 0,
            "dnd": bool(mind.prefs.get("dnd")) if mind else False,
            "claps": claps.status() if claps else {"enabled": False},
            "known_faces": gallery_names,
            "glow": (self.glow.current() if self.glow and self.glow.enabled else "off"),
            "healer": ("on" if self.healer and self.healer._thread else "off"),
            "server": (self.server.status() if self.server else
                       {"tunnel": {"running": False, "url": ""}, "rtdb": False,
                        "persist": self.share_persist}),
            "server": (self.server.status() if self.server else {"tunnel": {}, "rtdb": False}),
            "presence": (self.presence.status() if self.presence else {"running": False}),
            "voice_gate": (self.voice_gate.stats() if self.voice_gate else {}),
        }

    def shutdown(self):
        self._dead = True
        self._inbox_event.set()
        self.share_persist = False
        try:
            if self.presence:
                self.presence.stop()
        except Exception:
            pass
        try:
            if self.server:
                self.server.stop()
        except Exception:
            pass
        try:
            link = self.core._share_link()
            link.stop()
        except Exception:
            pass
        try:
            self.camera.stop()
        except Exception:
            pass
        try:
            if self.mind:
                self.mind.stop()
        except Exception:
            pass
        try:
            if self.claps:
                self.claps.stop()
        except Exception:
            pass
        try:
            if self.glow:
                self.glow.stop()
        except Exception:
            pass
        try:
            if self.healer:
                self.healer.stop()
        except Exception:
            pass
        try:
            if self.core._dashboard:
                self.core._dashboard.stop()
        except Exception:
            pass
        try:
            if self.core._homebot:
                self.core._homebot.stop()
        except Exception:
            pass
        logger.info("Session shut down.")
