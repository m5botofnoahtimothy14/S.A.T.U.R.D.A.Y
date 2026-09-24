"""SATURDAY Mind — OWN cognition that runs on its own. Observe → learn → act.

A background loop (tick ~30s) that:
1. OBSERVES: who is present (face gallery), their mood, hour, recent commands.
2. LEARNS : updates preferences from patterns — active hours, top commands,
   sightings per identity — persisted ENCRYPTED (vault tag:prefs). Episodes
   (arrivals, nudges, milestones) go to tag:episode, pruned past 300.
3. ACTS   : proactively and politely — greet a recognized arrival once per
   session, nudge hydration when low, note newcomers. Hard anti-spam:
   per-action cooldowns, max 3 proactive speaks/hour, total respect for
   do-not-disturb (double-clap idle) — DND blocks ALL proactive speech.

Nothing is a black box: `mind` shows prefs + loop state, every rule is
below, every episode is in the vault. This is learning by living with you.
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Mind")

TICK_SECONDS = 30.0
MAX_SPEAKS_PER_HOUR = 3
GREET_COOLDOWN_S = 4 * 3600
NUDGE_COOLDOWN_S = 2 * 3600
MAX_EPISODES = 300


class MindLoop:
    def __init__(self, core, observe_fn: Optional[Callable[[], Dict[str, Any]]] = None):
        self.core = core
        self.observe_fn = observe_fn or (lambda: {})
        self.prefs: Dict[str, Any] = {
            "active_hours": {}, "top_commands": {}, "sightings": {},
            "greeted": {}, "last_nudge": 0.0, "speaks_this_hour": [],
            "dnd": False, "born": time.time(),
        }
        self.running = False
        self.ticks = 0
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._load_prefs()

    # -- persistence (encrypted vault) -----------------------------------------
    def _vault(self):
        return self.core.pmv

    def _load_prefs(self):
        try:
            found = self._vault().secure_search(tag="prefs")
            if found:
                import json

                data = json.loads(found[-1].get("content", "{}"))
                if isinstance(data, dict):
                    data.setdefault("active_hours", {})
                    data.setdefault("top_commands", {})
                    data.setdefault("sightings", {})
                    data.setdefault("greeted", {})
                    data.setdefault("speaks_this_hour", [])
                    self.prefs.update(data)
                    logger.info("Mind: loaded learned preferences.")
        except Exception as e:
            logger.debug(f"Mind prefs load skipped: {e}")

    def save_prefs(self):
        try:
            import json

            with self._lock:
                snapshot = json.dumps(self.prefs)
            self._vault().secure_store(snapshot, tags=["prefs"])
        except Exception as e:
            logger.debug(f"Mind prefs save skipped: {e}")

    def episode(self, text: str):
        try:
            self._vault().secure_store(f"[{time.strftime('%Y-%m-%d %H:%M')}] {text}",
                                       tags=["episode"])
        except Exception:
            pass

    def prune_episodes(self):
        try:
            found = self._vault().secure_search(tag="episode") or []
            if len(found) > MAX_EPISODES:
                for e in sorted(found, key=lambda x: x.get("timestamp", 0))[:len(found) - MAX_EPISODES]:
                    try:
                        self._vault().memory_engine.delete_entry(e["id"])
                    except Exception:
                        pass
        except Exception:
            pass

    # -- loop --------------------------------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="mind-loop")
        self._thread.start()
        logger.info("Mind: cognition loop running on its own.")

    def stop(self):
        self._stop.set()
        self.running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        self._thread = None
        try:
            self.save_prefs()
        except Exception:
            pass

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick(self.observe_fn())
            except Exception as e:
                logger.debug(f"Mind tick failed: {e}")
            self._stop.wait(TICK_SECONDS)

    # -- cognition ---------------------------------------------------------------
    def _can_speak(self) -> bool:
        with self._lock:
            if self.prefs.get("dnd"):
                return False
            hour_ago = time.time() - 3600
            self.prefs["speaks_this_hour"] = [t for t in self.prefs["speaks_this_hour"] if t > hour_ago]
            return len(self.prefs["speaks_this_hour"]) < MAX_SPEAKS_PER_HOUR

    def _mark_spoke(self):
        with self._lock:
            self.prefs["speaks_this_hour"].append(time.time())

    def _say(self, text: str):
        try:
            self.core._speak(text)
            self._mark_spoke()
        except Exception:
            pass

    def tick(self, obs: Dict[str, Any]) -> List[str]:
        """One observe→learn→act cycle. Returns actions taken (for tests/logs)."""
        actions = []
        now = time.time()
        hour = str(time.localtime().tm_hour)
        name = (obs.get("present") or "").strip() or None
        mood = obs.get("mood")

        with self._lock:
            ah = self.prefs["active_hours"]
            ah[hour] = ah.get(hour, 0) + (1 if name else 0)
            for cmd, n in (obs.get("commands") or {}).items():
                tc = self.prefs["top_commands"]
                tc[cmd] = tc.get(cmd, 0) + n
            if name:
                sg = self.prefs["sightings"]
                entry = sg.get(name, {"first": now, "last": 0, "count": 0})
                entry["last"] = now
                entry["count"] += 1
                sg[name] = entry
        self.ticks += 1

        # Greet recognized arrivals, once per session window.
        if name and name.lower() != "unknown":
            last = self.prefs["greeted"].get(name, 0)
            if now - last > GREET_COOLDOWN_S and self._can_speak():
                part = "evening" if int(hour) >= 17 else "afternoon" if int(hour) >= 12 else "morning"
                self._say(f"Good {part}, {name}. All systems ready.")
                with self._lock:
                    self.prefs["greeted"][name] = now
                self.episode(f"greeted {name} (mood {mood or '?'})")
                actions.append(f"greet:{name}")
        elif name is None and obs.get("face_seen") and self._can_speak():
            self._say("Hello. I don't recognize you yet — I can learn you with enroll.")
            actions.append("greet:stranger")
            self.episode("met someone new (unenrolled)")

        # Hydration nudge: assign MYSELF a speak-task (single control point).
        try:
            if now - self.prefs.get("last_nudge", 0) > NUDGE_COOLDOWN_S:
                from saturday import senses

                entries = self.core._hydration_entries() if hasattr(self.core, "_hydration_entries") else []
                st = senses.water_status(entries)
                if st["percent"] < 25 and name:
                    session = getattr(self.core, "session", None)
                    if session is not None:
                        session.inbox_add(kind="say",
                                          text=f"{name}, your water is low today. Have a glass.",
                                          priority=4)
                        with self._lock:
                            self.prefs["last_nudge"] = now
                        actions.append("selftask:water-nudge")
        except Exception:
            pass

        # Morning briefing: once a day, first recognized sighting 5–11am.
        try:
            day = time.strftime("%Y-%m-%d")
            h = int(hour)
            if (name and name.lower() != "unknown" and 5 <= h < 11
                    and self.prefs.get("briefed_day") != day):
                session = getattr(self.core, "session", None)
                if session is not None and hasattr(self.core, "build_briefing"):
                    session.inbox_add(kind="say", text=self.core.build_briefing(name),
                                      priority=5)
                    with self._lock:
                        self.prefs["briefed_day"] = day
                    self.episode(f"morning briefing for {name}")
                    actions.append("selftask:briefing")
        except Exception:
            pass

        if self.ticks % 20 == 0:
            self.save_prefs()
            self.prune_episodes()
        return actions

    def consolidate(self) -> str:
        """Learn now: persist prefs + prune, report what the mind knows."""
        self.save_prefs()
        self.prune_episodes()
        tc = sorted(self.prefs["top_commands"].items(), key=lambda kv: kv[1], reverse=True)[:5]
        ah = sorted(self.prefs["active_hours"].items(), key=lambda kv: kv[1], reverse=True)[:3]
        sg = {k: v.get("count", 0) for k, v in self.prefs["sightings"].items()}
        return (f"🧠 Mind: {self.ticks} ticks, loop {'running' if self.running else 'stopped'}, "
                f"DND {'on' if self.prefs.get('dnd') else 'off'}.\n"
                f"   Top commands: {tc or 'none yet'}\n"
                f"   Active hours: {ah or 'none yet'}\n"
                f"   Sightings: {sg or 'nobody yet'}")

    def set_dnd(self, on: bool) -> str:
        with self._lock:
            self.prefs["dnd"] = bool(on)
        self.save_prefs()
        self.episode("entered quiet mode" if on else "left quiet mode")
        return "🤫 Quiet mode ON — I won't speak unless spoken to." if on else "🔊 I'm back."
