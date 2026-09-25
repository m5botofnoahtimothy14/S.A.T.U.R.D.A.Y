import logging
import json
import shlex
import time
from pathlib import Path
from saturday.controller import MemoryController
from saturday.screen_operator import ScreenOperator, backend_available, ocr_available
from saturday.agent import AgentRunner, AgentTask, TemplateBrain, research_plan, supervised_plan
from saturday import senses
from saturday import ears
from saturday.homebot import HomeBotLink
from saturday.dashboard import DashboardServer

logger = logging.getLogger("SATURDAY.Core")

class SATURDAYCore:
    def __init__(self, passphrase: str, project_root: Path):
        self.project_root = project_root
        self.pmv = MemoryController(passphrase, project_root)
        self.screen = ScreenOperator()
        self.agent_history = []
        self._homebot = None
        self._dashboard = None
        self._brain_probe = None
        self.session = None
        self.cmd_counts = {}
        self._gallery_cache = None
        self._voice_cache = None
        self._share_obj = None
        self.cloud_config = {}
        self.is_running = False
        # Set per process_command call; read by screen handlers. Assignment
        # and dispatch have no I/O between them, so this is GIL-atomic.
        self._current_trusted = True
        self._command_handlers = self._build_command_handlers()

    def initialize(self):
        """Pre-flight checks and vault mounting."""
        self.pmv.mount_vaults()
        self.pmv.update_heartbeat()
        self.is_running = True
        logger.info("SATURDAY Intelligence initialized and online.")
        # Always-on session: camera stays open, voice/brain/homebot warm up,
        # HUD auto-starts. Everything serves from here until shutdown.
        try:
            from saturday.session import SessionManager
            self.session = SessionManager(self)
            self.session.boot()
        except Exception as e:
            logger.warning(f"Session boot degraded: {e}")
            self.session = None

    def _build_command_handlers(self):
        return {
            "store": self._handle_store,
            "retrieve": self._handle_retrieve,
            "search": self._handle_search,
            "status": self._handle_status,
            "sync": self._handle_sync,
            "heartbeat": self._handle_heartbeat,
            "delete": self._handle_delete,
            "open": self._handle_open,
            "see": self._handle_see,
            "shot": self._handle_see,
            "click": self._handle_click,
            "type": self._handle_type,
            "press": self._handle_press,
            "hotkey": self._handle_hotkey,
            "scroll": self._handle_scroll,
            "read": self._handle_read,
            "clicktext": self._handle_clicktext,
            "do": self._handle_do,
            "research": self._handle_research,
            "tasks": self._handle_tasks,
            "brain": self._handle_brain,
            "sense": self._handle_sense,
            "mood": self._handle_mood,
            "hr": self._handle_hr,
            "wellness": self._handle_wellness,
            "drink": self._handle_drink,
            "water": self._handle_water,
            "say": self._handle_say,
            "hear": self._handle_hear,
            "listen": self._handle_listen,
            "dashboard": self._handle_dashboard,
            "bot": self._handle_bot,
            "botstatus": self._handle_botstatus,
            "services": self._handle_services,
            "cam": self._handle_cam,
            "queue": self._handle_queue,
            "docker": self._handle_docker,
            "maps": self._handle_maps,
            "route": self._handle_route,
            "enroll": self._handle_enroll,
            "who": self._handle_who,
            "enrollvoice": self._handle_enrollvoice,
            "voiceid": self._handle_voiceid,
            "claps": self._handle_claps,
            "mind": self._handle_mind,
            "learn": self._handle_learn,
            "glow": self._handle_glow,
            "heal": self._handle_heal,
            "assign": self._handle_assign,
            "inbox": self._handle_inbox,
            "briefing": self._handle_briefing,
            "announce": self._handle_announce,
            "share": self._handle_share,
            "server": self._handle_server,
            "cloudsetup": self._handle_cloudsetup,
            "cloudbackup": self._handle_cloudbackup,
            "cloudrestore": self._handle_cloudrestore,
            "help": self._handle_help,
        }

    def _parse_command(self, cmd_string: str):
        tokens = shlex.split(cmd_string.strip())
        command = tokens[0].lower() if tokens else ""
        args = tokens[1:]
        return command, args

    def _extract_tags(self, text: str):
        tags = []
        if "tag:" in text:
            content_part, tag_part = text.split("tag:", 1)
            tags = [t.strip() for t in tag_part.split(",") if t.strip()]
            return content_part.strip(), tags
        return text.strip(), tags

    def process_command(self, cmd_string: str, trusted: bool = True):
        """trusted=True for local CLI/voice (user is present).
        trusted=False for remote callers (realtime bridge): screen-driving
        commands are refused without explicit local confirmation."""
        cmd_string = cmd_string.strip()
        if not cmd_string:
            return "❓ Please enter a command. Type 'help' for available commands."
        self._current_trusted = trusted

        if self.pmv.auto_lock_check():
            logger.info("Vault auto-locked due to inactivity.")

        command, args = self._parse_command(cmd_string)
        try:
            self.cmd_counts[command or "?"] = self.cmd_counts.get(command or "?", 0) + 1
        except Exception:
            pass
        handler = self._command_handlers.get(command, self._handle_unknown)
        try:
            return handler(args, cmd_string)
        except Exception as exc:
            logger.exception("Command processing failed")
            return f"❌ System Error: {str(exc)}"

    def _handle_store(self, args, raw_text):
        content, tags = self._extract_tags(raw_text[len("store"):].strip())
        if not content:
            return "❌ Please provide text to store. Example: store My secret tag:project,secret"
        entry_id = self.pmv.secure_store(content, tags=tags)
        return f"✅ Stored securely. Entry ID: {entry_id}"

    def _handle_retrieve(self, args, raw_text):
        if not args:
            return "❌ Provide the entry ID to retrieve. Example: retrieve <entry_id>"
        entry = self.pmv.secure_retrieve(args[0])
        if not entry:
            return "❌ Entry not found."
        return (
            f"📝 Entry found:\n"
            f"   Time: {entry.get('timestamp')}\n"
            f"   Content: {entry.get('content')}\n"
            f"   Tags: {entry.get('tags')}"
        )

    def _handle_search(self, args, raw_text):
        query = raw_text[len("search"):].strip()
        if query.lower().startswith("tag:"):
            tag = query[4:].strip()
            results = self.pmv.secure_search(tag=tag)
        else:
            results = self.pmv.secure_search()

        if not results:
            return "🔎 No matches found."

        results = sorted(results, key=lambda e: e.get("timestamp", 0), reverse=True)
        summary = []
        for r in results[:5]:
            rid = str(r.get('id', '?'))[:8]
            content = str(r.get('content', ''))[:60]
            summary.append(f"   - [{rid}] {content}...")
        return f"🔎 Found {len(results)} matches:\n" + "\n".join(summary)

    def _handle_status(self, args, raw_text):
        dm_status = self.pmv.get_deadman_status()
        node_status = self.pmv.node_status()
        return (
            "🔋 SATURDAY Status: ONLINE\n"
            f"🛡️ Vault mounted: {self.pmv.vault_mounted}\n"
            f"💀 Deadman status: {dm_status}\n"
            f"🌐 {node_status}"
        )

    def _handle_sync(self, args, raw_text):
        return "🔄 Sync initiated. Synchronizing encrypted containers via P2P..."

    def _handle_heartbeat(self, args, raw_text):
        self.pmv.update_heartbeat()
        return "💓 Heartbeat updated."

    def _handle_delete(self, args, raw_text):
        if not args:
            return "❌ Provide the entry ID to delete. Example: delete <entry_id>"
        ok = self.pmv.secure_delete(args[0])
        return "🗑️ Entry deleted." if ok else "❌ Entry not found."

    # -- Screen operator (offline GUI automation, no APIs/credentials) --
    def _screen_denied(self, result: dict) -> str:
        err = result.get("error", "refused")
        suffix = " (Remote callers cannot drive the screen.)" if not self._current_trusted else ""
        return f"❌ {err}{suffix}"

    def _handle_open(self, args, raw_text):
        target = " ".join(args).strip()
        if not target:
            return "❌ Usage: open <app name|url>. Example: open gmail | open notepad"
        lowered = target.lower()
        is_url = (
            lowered.startswith(("http://", "https://"))
            or "://" in target
            or lowered in ("gmail", "mail", "calendar", "drive", "youtube", "whatsapp")
            or (" " not in target and "." in target)
        )
        if is_url:
            result = self.screen.open_url(target, confirm=self._current_trusted)
            if not result.get("success"):
                return self._screen_denied(result)
            return f"🌐 Opened: {result['url']}"
        result = self.screen.open_app(target, confirm=self._current_trusted)
        if not result.get("success"):
            return self._screen_denied(result)
        return f"🖥️ Opening app: {result['app']}"

    def _handle_see(self, args, raw_text):
        result = self.screen.screenshot(args[0] if args else None)
        if not result.get("success"):
            return f"❌ Screenshot failed: {result.get('error')}"
        return (
            f"📷 Screen captured: {result['path']}\n"
            f"   Size: {result['width']}x{result['height']}\n"
            "   View the image, then use click/type/press with what you see."
        )

    def _handle_click(self, args, raw_text):
        if len(args) < 2:
            return "❌ Usage: click <x> <y>. Run 'see' first for coordinates."
        result = self.screen.click(args[0], args[1], confirm=self._current_trusted)
        if not result.get("success"):
            return self._screen_denied(result)
        return f"🖱️ Clicked ({result['x']},{result['y']}). Run 'see' to verify."

    def _handle_type(self, args, raw_text):
        text = raw_text[len("type"):].strip()
        if not text:
            return "❌ Usage: type <text to type into the focused window>"
        result = self.screen.type_text(text, confirm=self._current_trusted)
        if not result.get("success"):
            return self._screen_denied(result)
        return f"⌨️ Typed {result['chars']} chars. Run 'see' to verify."

    def _handle_press(self, args, raw_text):
        if not args:
            return "❌ Usage: press <key>. Example: press enter"
        result = self.screen.press(args[0], confirm=self._current_trusted)
        if not result.get("success"):
            return self._screen_denied(result)
        return f"⌨️ Pressed {result['key']}."

    def _handle_hotkey(self, args, raw_text):
        if not args:
            return "❌ Usage: hotkey <key1> <key2> [key3]. Example: hotkey ctrl t"
        result = self.screen.hotkey(args, confirm=self._current_trusted)
        if not result.get("success"):
            return self._screen_denied(result)
        return f"⌨️ Hotkey {'+'.join(result['keys'])} sent."

    def _handle_scroll(self, args, raw_text):
        if not args:
            return "❌ Usage: scroll <amount>. Example: scroll -5"
        result = self.screen.scroll(args[0], confirm=self._current_trusted)
        if not result.get("success"):
            return self._screen_denied(result)
        return f"🖱️ Scrolled {result['amount']}."

    def _handle_read(self, args, raw_text):
        result = self.screen.read_screen(args[0] if args else None)
        if not result.get("success"):
            return f"❌ Read failed: {result.get('error')}"
        text = result.get("text", "")
        preview = text[:500] + ("..." if len(text) > 500 else "")
        return (
            f"📖 Read {len(result.get('words', []))} words:\n"
            f"   {preview or '(no text detected)'}"
        )

    def _handle_clicktext(self, args, raw_text):
        phrase = " ".join(args).strip()
        if not phrase:
            return "❌ Usage: clicktext <word on screen>. Example: clicktext Compose"
        result = self.screen.click_text(phrase, confirm=self._current_trusted)
        if not result.get("success"):
            return self._screen_denied(result)
        return f"🖱️ Clicked '{phrase}' at ({result['x']},{result['y']}). Run 'see' to verify."

    # -- Agent (autonomy: SATURDAY acts by itself) ---------------------
    def _run_agent_task(self, task: AgentTask) -> str:
        trusted = self._current_trusted
        prompter = None
        if trusted:
            def prompter(question, observation):
                print(f"\n🤖 SATURDAY asks: {question}")
                return input("   You ❯ ").strip()
        runner = AgentRunner(
            operator=self.screen,
            brain=TemplateBrain(),
            store_fn=lambda content, tags: self.pmv.secure_store(content, tags=tags),
            prompter=prompter,
            confirm=trusted,
        )
        print(f"\n🤖 Working on it by myself: {task.goal}")
        finished = runner.run(task)
        self.agent_history.append(finished)
        self.agent_history = self.agent_history[-50:]  # bounded for long runs
        return "\n" + finished.summary() + "\n"

    def _homebot_link(self):
        if self._homebot is None:
            self._homebot = HomeBotLink()
        return self._homebot

    def _handle_dashboard(self, args, raw_text):
        port = 8099
        if args:
            try:
                port = int(args[0])
            except ValueError:
                return "❌ Usage: dashboard [port]. Example: dashboard 8099"
        if self._dashboard is None:
            self._dashboard = DashboardServer(self, homebot_link=self._homebot)
        elif self._dashboard.port != port and not self._dashboard.running:
            self._dashboard.port = port
        # Late-bind the bot link so HUD started before first bot use still shows it.
        try:
            if self._homebot is not None:
                self._dashboard.homebot_link = self._homebot
        except Exception:
            pass
        res = self._dashboard.start()
        if not res.get("success"):
            return f"❌ Dashboard failed: {res.get('error')}"
        return f"🖥️ HUD live at {res['url']}  (127.0.0.1 only — this PC)"

    def _handle_bot(self, args, raw_text):
        if not args:
            return ("❌ Usage: bot <forward|back|left|right|spinleft|spinright|stop|"
                    "autonomy_on|autonomy_off|express WORD> [seconds] [speed]. "
                    "Example: bot forward 2 80")
        name = args[0]
        if name == "express" and len(args) > 1:
            name = "express " + " ".join(args[1:])
            duration, speed = 0, 80
        else:
            try:
                duration = float(args[1]) if len(args) > 1 else 1.0
            except ValueError:
                return "❌ Seconds must be a number."
            try:
                speed = int(args[2]) if len(args) > 2 else 80
            except ValueError:
                return "❌ Speed must be 0-100."
        res = self._homebot_link().command(name, duration=duration, speed=speed)
        if res.get("status") == "success":
            return f"🤖 Bot {res['command']} via {res.get('via')}."
        return f"❌ {res.get('reason', res.get('status'))}"

    def _handle_botstatus(self, args, raw_text):
        st = self._homebot_link().status()
        link = st.get("link", "never")
        if link == "live":
            link_txt = "🟢 BOT LIVE"
        elif link == "stale":
            link_txt = "🟡 BOT STALE (heard before, quiet now)"
        elif st.get("broker_connected"):
            link_txt = "🟡 broker up, bot never seen"
        else:
            link_txt = "🔴 no link (plug Core2 USB or set MQTT_BROKER)"
        lines = [f"🤖 HomeBot: {link_txt}",
                 f"   Transport: {st.get('transport')} | broker={st.get('broker')} "
                 f"com={st.get('com_port')}"]
        if st.get("last_seen_age_s") is not None:
            lines.append(f"   Last heard: {st['last_seen_age_s']}s ago | cmd={st.get('current_command')}")
        if st.get("sensors"):
            lines.append(f"   Sensors: {str(st['sensors'])[:200]}")
        ports = [f"{p['device']} ({p['description'][:30]})" for p in st.get("ports", [])[:5]]
        lines.append(f"   COM ports: {', '.join(ports) or 'none'}")
        return "\n".join(lines)

    # -- Always-on session commands --------------------------------------
    def _handle_services(self, args, raw_text):
        session = getattr(self, "session", None)
        if session is None:
            return "⚠️ Session manager not booted (running degraded)."
        st = session.status()
        return (
            "🖥️ Session services:\n"
            f"   Uptime: {st['uptime_s']}s\n"
            f"   📷 Camera: {st['camera']} ({st['camera_frames']} frames)\n"
            f"   👂 Ears: {st['ears']} | 🧠 Brain: {st['brain']}\n"
            f"   🗄️ Vault: {st['vault']} | 🤖 HomeBot: {st['homebot']}\n"
            f"   🌐 HUD: {st['dashboard']} | bg tasks: {st['queued']}"
        )

    def _handle_cam(self, args, raw_text):
        got = self._camera_frame()
        if not got.get("success"):
            return f"❌ {got['error']}"
        try:
            import cv2
            import tempfile
            from pathlib import Path as _P
            path = str(_P(tempfile.gettempdir()) / f"saturday_cam_{int(time.time())}.png")
            cv2.imwrite(path, got["frame"])
            h, w = got["frame"].shape[:2]
            return f"📷 Live camera frame {w}x{h} via {got.get('via')}: {path}"
        except Exception as e:
            return f"❌ Snapshot failed: {e}"

    def _handle_queue(self, args, raw_text):
        goal = raw_text[len("queue"):].strip()
        if not goal:
            return "❌ Usage: queue <goal>. Runs unsupervised in background."
        session = getattr(self, "session", None)
        if session is None:
            return "⚠️ Session manager not booted; use `do` instead."
        try:
            tid = session.queue_goal(goal)
            return f"📥 Queued background task {tid}: {goal}\n   Watch with `tasks`."
        except Exception as e:
            return f"❌ Queue failed: {e}"

    def _handle_docker(self, args, raw_text):
        import shutil
        import subprocess
        if not shutil.which("docker"):
            return "❌ Docker not installed (winget install Docker.DockerDesktop)."
        cmd = ["docker"] + (args or ["info", "--format",
                                     "{{.ServerVersion}} | mem {{.MemTotal}} | containers {{.Containers}}"])
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            out = (proc.stdout or proc.stderr or "").strip()[:2000]
            if proc.returncode != 0:
                return f"❌ docker exited {proc.returncode}: {out or 'no output'}"
            return f"🐳 docker {' '.join(args) if args else 'status'}:\n   {out or '(ok, no output)'}"
        except subprocess.TimeoutExpired:
            return "❌ docker timed out (daemon busy?)."
        except Exception as e:
            return f"❌ docker failed: {e}"

    @staticmethod
    def _osm_get(url: str) -> dict:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "SATURDAY/1.0 (local assistant)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            import json as _json
            return _json.loads(resp.read().decode())

    def _handle_maps(self, args, raw_text):
        query = raw_text[len("maps"):].strip()
        if not query:
            return "❌ Usage: maps <place>. Example: maps Burj Khalifa (online OSM data)"
        try:
            import urllib.parse
            url = ("https://nominatim.openstreetmap.org/search?q="
                   + urllib.parse.quote(query) + "&format=json&limit=1")
            res = self._osm_get(url)
            if not res:
                return f"🗺️ No OSM match for '{query}'."
            top = res[0]
            return (f"🗺️ {top.get('display_name', '?')}\n"
                    f"   lat {top.get('lat')}, lon {top.get('lon')} (online OSM)")
        except Exception as e:
            return f"❌ Maps lookup failed (offline?): {e}"

    def _handle_route(self, args, raw_text):
        rest = raw_text[len("route"):].strip()
        if " to " not in rest.lower():
            return "❌ Usage: route <from> to <to>. Example: route Dubai Mall to Airport"
        import re as _re
        parts = _re.split(r"\s+to\s+", rest, maxsplit=1, flags=_re.IGNORECASE)
        try:
            import urllib.parse
            geo = []
            for p in parts:
                url = ("https://nominatim.openstreetmap.org/search?q="
                       + urllib.parse.quote(p.strip()) + "&format=json&limit=1")
                res = self._osm_get(url)
                if not res:
                    return f"🗺️ No OSM match for '{p.strip()}'."
                geo.append((res[0]["lon"], res[0]["lat"]))
            (x1, y1), (x2, y2) = geo
            url = (f"https://router.project-osrm.org/route/v1/driving/{x1},{y1};{x2},{y2}"
                   "?overview=false")
            r = self._osm_get(url)
            leg = (r.get("routes") or [{}])[0]
            km = leg.get("distance", 0) / 1000.0
            mins = leg.get("duration", 0) / 60.0
            return (f"🗺️ Route: {parts[0].strip()} → {parts[1].strip()}\n"
                    f"   {km:.1f} km, ~{mins:.0f} min drive (online OSRM)")
        except Exception as e:
            return f"❌ Route failed (offline?): {e}"

    def _handle_do(self, args, raw_text):
        goal = raw_text[len("do"):].strip()
        if not goal:
            return "❌ Usage: do <goal>. Example: do research quantum batteries"
        lowered = goal.lower()
        if lowered.startswith("research "):
            plan = research_plan(goal[9:].strip() or goal)
        else:
            plan = supervised_plan(goal)
        return self._run_agent_task(AgentTask(goal, plan))

    def _handle_research(self, args, raw_text):
        topic = raw_text[len("research"):].strip()
        if not topic:
            return "❌ Usage: research <topic>. Example: research best local OCR engines"
        return self._run_agent_task(AgentTask(f"research {topic}", research_plan(topic)))

    def _handle_tasks(self, args, raw_text):
        if not self.agent_history:
            return "📋 No autonomous tasks yet. Try: research <topic> | do <goal>"
        lines = [f"   {i+1}. {t.summary()}" for i, t in enumerate(self.agent_history[-10:])]
        return "📋 Recent autonomous tasks:\n" + "\n".join(lines)

    # -- Senses (real local body sensing; estimates, never diagnoses) ---
    def _camera_frame(self):
        # Prefer the always-on session hub (zero re-open). Fallback: direct.
        try:
            session = getattr(self, "session", None)
            if session is not None and session.camera.running:
                frame = session.camera.get_frame(max_age=5.0)
                if frame is not None:
                    return {"success": True, "frame": frame, "via": "session"}
        except Exception:
            pass
        try:
            return {"success": True, "frame": senses.grab_frame(), "via": "direct"}
        except RuntimeError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception("Camera capture failed")
            return {"success": False, "error": str(e)}

    def _handle_sense(self, args, raw_text):
        got = self._camera_frame()
        if not got.get("success"):
            return f"❌ {got['error']}"
        frame = got["frame"]
        people = senses.find_people(frame)
        faces = senses.find_faces(frame)
        mood = senses.mood(frame)
        lines = ["👁️ Sense dashboard (local camera, nothing leaves this PC):"]
        lines.append(f"   People: {people.get('count', '?') if people.get('success') else 'unavailable'}")
        lines.append(f"   Faces: {faces.get('count', '?') if faces.get('success') else 'unavailable'}")
        if mood.get("success"):
            lines.append(f"   Mood: {mood['mood']} (top: {mood['top_emotion']} {mood['confidence']:.0%})")
        else:
            lines.append(f"   Mood: unavailable ({mood.get('error')})")
        return "\n".join(lines)

    def _handle_mood(self, args, raw_text):
        got = self._camera_frame()
        if not got.get("success"):
            return f"❌ {got['error']}"
        res = senses.mood(got["frame"])
        if not res.get("success"):
            return f"❌ {res['error']}"
        top3 = sorted(res["scores"].items(), key=lambda kv: kv[1], reverse=True)[:3]
        detail = ", ".join(f"{k} {v:.0%}" for k, v in top3)
        return f"🙂 Mood: {res['mood']} ({detail})"

    def _handle_hr(self, args, raw_text):
        secs = 20.0
        if args:
            try:
                secs = float(args[0])
            except ValueError:
                return "❌ Usage: hr [seconds 10-60]. Example: hr 20"
        # Instant path: session ring buffer (no 9s camera re-open).
        try:
            session = getattr(self, "session", None)
            if session is not None and session.camera.running:
                ring = session.camera.get_ring(secs)
                if len(ring) >= 8 * 8:  # ~8s at service fps
                    import time as _t
                    span = ring[-1][0] - ring[0][0]
                    fps = len(ring) / max(span, 0.1)
                    res = senses.heart_rate(secs, frames=[f for _, f in ring], fps=fps)
                    return self._format_hr(res, instant=True)
        except Exception as e:
            logger.debug(f"Ring HR failed, falling back to live: {e}")
        print("💓 Measuring — sit still, face the camera, good light...")
        return self._format_hr(senses.heart_rate(secs))

    @staticmethod
    def _format_hr(res, instant=False):
        if not res.get("success"):
            return f"❌ {res['error']}"
        tag = " (instant, from live buffer)" if instant else ""
        out = (f"💓 Heart rate: {res['bpm']} BPM "
               f"(confidence {res['confidence']:.0%}, {res['seconds']}s scan){tag}")
        if res.get("flag"):
            out += f"\n   ⚠️ {res['flag']}"
        return out + "\n   " + res.get("note", "")

    def _handle_wellness(self, args, raw_text):
        got = self._camera_frame()
        if not got.get("success"):
            return f"❌ {got['error']}"
        mood = senses.mood(got["frame"])
        mood_label = mood.get("mood") if mood.get("success") else None
        sad_score = mood.get("scores", {}).get("sadness", 0.0) if mood.get("success") else 0.0
        print("💓 Wellness check — 12s heart scan, hold still...")
        hr = senses.heart_rate(12.0)
        hr_bpm = hr.get("bpm") if hr.get("success") else None
        if not hr.get("success"):
            print(f"   (HR scan failed: {hr.get('error')})")
        res = senses.wellness(hr_bpm=hr_bpm, mood_label=mood_label, sad_score=sad_score)
        lines = [f"🧠 Wellness estimate: anxiety {res['anxiety']}/100 ({res['anxiety_level']}), "
                 f"sadness {res['sadness']}/100"]
        if res.get("mood"):
            lines.append(f"   Expression: {res['mood']}")
        if res.get("hr_bpm"):
            lines.append(f"   Heart rate: {res['hr_bpm']} BPM (measured)")
        else:
            lines.append("   Heart rate: not measured (see `hr`)")
        for n in res.get("notes", []):
            lines.append(f"   Note: {n}")
        if res.get("danger"):
            lines.append(f"   ⚠️ {res['danger']}")
        lines.append(f"   {res['disclaimer']}")
        return "\n".join(lines)

    def _identity_snapshot(self) -> dict:
        try:
            names = list(getattr(self._gallery(), "names", []))
        except Exception:
            names = []
        try:
            voice = self._voicevault().print is not None
        except Exception:
            voice = False
        mind = getattr(getattr(self, "session", None), "mind", None)
        return {"known_faces": names, "voice_enrolled": voice,
                "dnd": bool(mind.prefs.get("dnd")) if mind else False,
                "mind_ticks": mind.ticks if mind else 0}

    def _glow_snapshot(self):
        try:
            glow = getattr(getattr(self, "session", None), "glow", None)
            if glow and glow.enabled:
                return glow.current()
            return "off"
        except Exception:
            return "off"

    def _hydration_entries(self):
        try:
            raw = self.pmv.secure_search(tag="hydration")
        except Exception:
            return []
        entries = []
        for e in raw or []:
            try:
                d = json.loads(e.get("content", ""))
                if isinstance(d, dict) and "ml" in d:
                    entries.append(d)
            except Exception:
                continue
        return entries

    def _handle_drink(self, args, raw_text):
        if not args:
            return "❌ Usage: drink <ml>. Example: drink 500"
        try:
            ml = float(args[0])
        except ValueError:
            return "❌ Usage: drink <ml>. Example: drink 500"
        entries = self._hydration_entries()
        res = senses.log_drink(entries, ml)
        if not res.get("success"):
            return f"❌ {res['error']}"
        try:
            self.pmv.secure_store(json.dumps({"ml": ml, "at": entries[-1]["at"]}),
                                  tags=["hydration"])
        except Exception as e:
            return f"❌ Vault locked ({e}). Unlock first — drink not saved."
        st = senses.water_status(entries)
        return f"💧 Logged {ml:g} ml (today {st['today_ml']:g}/{st['goal_ml']:g} ml). {st['message']}"

    def _handle_water(self, args, raw_text):
        st = senses.water_status(self._hydration_entries())
        return (f"💧 Water level today: {st['today_ml']:g}/{st['goal_ml']:g} ml "
                f"({st['percent']}%). {st['message']}")

    # -- Identity: face gallery + voiceprint (encrypted vault) ------------
    def _gallery(self):
        if self._gallery_cache is not None:
            return self._gallery_cache
        from saturday.identity import FaceGallery
        import base64

        def load_fn():
            gallery = {}
            try:
                for e in self.pmv.secure_search(tag="identity") or []:
                    person = None
                    for t in e.get("tags", []):
                        if t.startswith("person:"):
                            person = t.split(":", 1)[1]
                    if not person:
                        continue
                    gallery.setdefault(person, []).append(base64.b64decode(e.get("content", "")))
            except Exception:
                pass
            return gallery

        def save_fn(name, png_bytes):
            import base64 as _b64
            self.pmv.secure_store(_b64.b64encode(png_bytes).decode(),
                                  tags=["identity", f"person:{name}"])

        self._gallery_cache = FaceGallery(load_fn=load_fn, save_fn=save_fn)
        return self._gallery_cache

    def _voicevault(self):
        if self._voice_cache is not None:
            return self._voice_cache
        from saturday.identity import VoiceVault
        import json as _json
        vv = VoiceVault()
        try:
            found = self.pmv.secure_search(tag="voiceprint") or []
            if found:
                vv.load(_json.loads(found[-1].get("content", "{}")))
        except Exception:
            pass
        self._voice_cache = vv
        return vv

    def _collect_face_crops(self, want: int = 15, wait_s: float = 8.0):
        """Gather face crops from session hub (instant) or live capture."""
        import time as _t
        crops = []
        session = getattr(self, "session", None)
        if session is not None and session.camera.running:
            deadline = _t.time() + wait_s
            seen_ids = set()
            while len(crops) < want and _t.time() < deadline:
                frames = session.camera.get_ring(2.0)
                for _, fr in frames:
                    boxes = senses.find_faces(fr).get("boxes", [])
                    for b in boxes:
                        key = (b["x"] // 20, b["y"] // 20)
                        if key in seen_ids:
                            continue
                        seen_ids.add(key)
                        crop = fr[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]]
                        norm = self._gallery().norm(crop)
                        if norm:
                            crops.append(norm)
                        if len(crops) >= want:
                            break
                    if len(crops) >= want:
                        break
                _t.sleep(0.5)
            return crops
        # Fallback: direct capture.
        try:
            frames, _ = senses.capture_series(min(wait_s, 10.0), fps_target=6.0)
        except RuntimeError as e:
            return {"error": str(e)}
        for fr in frames:
            for b in senses.find_faces(fr).get("boxes", [])[:1]:
                crop = fr[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]]
                norm = self._gallery().norm(crop)
                if norm:
                    crops.append(norm)
            if len(crops) >= want:
                break
        return crops

    def _handle_enroll(self, args, raw_text):
        name = raw_text[len("enroll"):].strip()
        if not name:
            return "❌ Usage: enroll <name>. Look at the camera for ~8 seconds."
        gallery = self._gallery()
        if not gallery.available():
            return "❌ Face engine unavailable (cv2.face missing)."
        print(f"📸 Enrolling '{name}' — look at the camera, move slightly...")
        crops = self._collect_face_crops()
        if isinstance(crops, dict):
            return f"❌ {crops.get('error')}"
        if len(crops) < 5:
            return f"❌ Only {len(crops)} face samples — need 5+. Better light, face the camera."
        saved = 0
        import base64 as _b64
        try:
            for png in crops:
                self.pmv.secure_store(_b64.b64encode(png).decode(),
                                      tags=["identity", f"person:{name}"])
                saved += 1
        except Exception as e:
            return f"❌ Vault save failed ({e}). Unlock first."
        self._gallery_cache = None
        self._gallery()  # reload + retrain from vault
        return f"✅ Enrolled '{name}': {saved} samples saved (encrypted). I know you now."

    def _handle_who(self, args, raw_text):
        got = self._camera_frame()
        if not got.get("success"):
            return f"❌ {got['error']}"
        faces = senses.find_faces(got["frame"])
        boxes = faces.get("boxes", []) if faces.get("success") else []
        if not boxes:
            return "👤 Nobody in view."
        gallery = self._gallery()
        biggest = max(boxes, key=lambda b: b["w"] * b["h"])
        crop = got["frame"][biggest["y"]:biggest["y"] + biggest["h"],
                            biggest["x"]:biggest["x"] + biggest["w"]]
        name, dist = gallery.recognize(crop)
        extra = f" +{len(boxes) - 1} other face(s)" if len(boxes) > 1 else ""
        if name:
            return f"👤 I see {name} (match distance {dist}){extra}."
        return f"👤 {len(boxes)} face(s), none recognized{extra}. Use enroll to teach me."

    def _handle_enrollvoice(self, args, raw_text):
        from saturday import ears
        import json as _json
        print("🎙️ Say your name clearly, 3 takes (~4s each)...")
        takes = []
        for i in range(3):
            print(f"   Take {i + 1}/3 — speak now...")
            cap = ears.capture(4.0)
            if not cap.get("success"):
                return f"❌ Mic failed: {cap.get('error')}"
            if not ears.heard(cap["samples"]):
                return "❌ Heard silence — speak up and retry."
            takes.append(cap["samples"])
        vv = self._voicevault()
        res = vv.enroll(takes)
        if not res.get("success"):
            return f"❌ Voice enroll failed: {res.get('error')}"
        try:
            self.pmv.secure_store(_json.dumps(vv.dump()), tags=["voiceprint"])
        except Exception as e:
            return f"❌ Vault save failed ({e}). Unlock first."
        return (f"✅ Voice enrolled ({res['samples']} takes, encrypted). "
                f"Personal threshold {res['threshold']} — I'll know your voice.")

    def _handle_voiceid(self, args, raw_text):
        from saturday import ears
        print("🎙️ Say something (~4s)...")
        cap = ears.capture(4.0)
        if not cap.get("success"):
            return f"❌ Mic failed: {cap.get('error')}"
        res = self._voicevault().verify(cap["samples"])
        if not res.get("success"):
            return f"❌ {res.get('error')}"
        return (f"🎙️ Voice verdict: {res['verdict']} "
                f"(distance {res['distance']}, threshold {res['threshold']})")

    def _handle_claps(self, args, raw_text):
        session = getattr(self, "session", None)
        arg = (args[0].lower() if args else "status")
        if arg == "on":
            if session is None:
                return "⚠️ Session not booted."
            if session.claps is None:
                session._start_claps()
            st = session.claps.status() if session.claps else {}
            return f"👏 Clap listener: {st}" if st.get("live") else "❌ Mic unavailable for claps."
        if arg == "off":
            if session and session.claps:
                session.claps.stop()
            return "👏 Clap listener off."
        if session and session.claps:
            st = session.claps.status()
            return (f"👏 Claps: live={st['live']} singles={st['singles']} "
                    f"doubles={st['doubles']} floor={st['noise_floor']}")
        return "👏 Clap listener not running. Use: claps on"

    def _handle_mind(self, args, raw_text):
        session = getattr(self, "session", None)
        if session is None or session.mind is None:
            return "🧠 Mind loop not running (session degraded)."
        return session.mind.consolidate() + f"\n   Ticks: {session.mind.ticks}"

    def _handle_learn(self, args, raw_text):
        session = getattr(self, "session", None)
        if session is None or session.mind is None:
            return "🧠 Mind loop not running (session degraded)."
        return "🧠 Consolidated:\n" + session.mind.consolidate()

    def build_briefing(self, name: str = "there") -> str:
        import datetime as _dt
        now = _dt.datetime.now()
        part = "evening" if now.hour >= 17 else "afternoon" if now.hour >= 12 else "morning"
        bits = [f"Good {part}, {name}. Briefing."]
        try:
            st = senses.water_status(self._hydration_entries())
            bits.append(f"Water {st['today_ml']:g} of {st['goal_ml']:g} ml.")
        except Exception:
            pass
        try:
            n = len(getattr(self, "agent_history", []))
            bits.append(f"{n} autonomous tasks on record.")
        except Exception:
            pass
        try:
            link = self._homebot_link().status().get("link", "never")
            bits.append(f"HomeBot {link}.")
        except Exception:
            pass
        try:
            top = sorted((self.cmd_counts or {}).items(), key=lambda kv: kv[1], reverse=True)[:3]
            if top:
                bits.append("You use me most for: " + ", ".join(k for k, _ in top) + ".")
        except Exception:
            pass
        return " ".join(bits)

    def _handle_briefing(self, args, raw_text):
        session = getattr(self, "session", None)
        name = None
        try:
            if session is not None:
                obs = session.observe()
                name = obs.get("present")
        except Exception:
            pass
        text = self.build_briefing(name or "there")
        self._speak(text)
        return f"📋 {text}"

    def _handle_announce(self, args, raw_text):
        text = raw_text[len("announce"):].strip()
        if not text:
            return "❌ Usage: announce <text> (speaks + logs + HUD event)."
        self._speak(text)
        try:
            if self._dashboard is not None:
                self._dashboard.note("announce", text)
        except Exception:
            pass
        try:
            self.pmv.secure_store(f"[announce] {text}", tags=["episode"])
        except Exception:
            pass
        return f"📣 Announced: {text[:150]}"

    # -- Online server (free Cloudflare tunnel) + cloud DB -----------------
    def _share_link(self):
        if self._share_obj is None:
            from saturday.share import ShareLink
            self._share_obj = ShareLink()
        return self._share_obj

    def _handle_server(self, args, raw_text):
        session = getattr(self, "session", None)
        if session is None or session.server is None:
            return "🛰️ Server layer not running (session degraded)."
        st = session.server.status()
        tn = st.get("tunnel", {})
        lines = ["🛰️ Always-on server (separate from the humanoid):",
                 f"   Tunnel: {'LIVE '+tn.get('url','') if tn.get('running') else 'off'}"
                 f" (persist {'on' if st.get('persist') else 'off'})",
                 f"   RTDB presence/commands: {'ONLINE' if st.get('rtdb') else 'offline (no Firebase creds)'}"]
        if st.get("last_heartbeat_s_ago") is not None:
            lines.append(f"   Last heartbeat: {st['last_heartbeat_s_ago']}s ago")
        lines.append("   Humanoid runs on top of this — `services` shows the body.")
        return "\n".join(lines)

    def _handle_share(self, args, raw_text):
        arg = (args[0].lower() if args else "status")
        link = self._share_link()
        session = getattr(self, "session", None)
        if arg == "on":
            hostname = args[1] if len(args) > 1 else ""
            if self._dashboard is None:
                self.process_command("dashboard 8099", trusted=True)
            port = self._dashboard.port if self._dashboard else 8099
            tok = self._dashboard.share() if self._dashboard else {"token": ""}
            res = link.start(port, hostname=hostname)
            if not res.get("success"):
                return f"❌ Share failed: {res.get('error')}"
            try:
                session = getattr(self, "session", None)
                if session is not None:
                    session._write_share_url(res["url"], tok.get("token", ""))
            except Exception:
                pass
            return (f"🌐 SATURDAY is ONLINE: {res['url']}\n"
                    f"   🔑 Token (show once, guard it): {tok.get('token', '')}\n"
                    f"   Open {res['url']}?token=TOKEN on your phone.\n"
                    f"   `share persist` keeps it up for months. `share off` kills it.")
        if arg == "persist":
            if session is None:
                return "⚠️ Session not booted."
            if args[1:] and args[1].lower() == "off":
                session.share_persist = False
                return "🌐 Persist OFF (tunnel keeps running until `share off`)."
            session.share_hostname = args[1] if len(args) > 1 else ""
            session.share_persist = True
            session._bg("share-watch", session._share_watch_loop)
            return ("🌐 Persist ON — watchdog re-opens the tunnel if it ever drops.\n"
                    f"   Hostname: {session.share_hostname or '(rotating quick URL)'}.")
        if arg == "off":
            if session is not None:
                session.share_persist = False
            link.stop()
            try:
                if self._dashboard is not None:
                    self._dashboard.unshare()
            except Exception:
                pass
            return "🌐 Share closed. Back to localhost-only."
        st = link.status()
        if st["running"]:
            extra = " (+persist watchdog)" if session and session.share_persist else ""
            host = f" host={session.share_hostname}" if session and session.share_hostname else ""
            return f"🌐 Sharing LIVE: {st['url']} (port {st['port']}){extra}{host}."
        persist = ""
        if session and session.share_persist:
            persist = f" (persist armed{f' host={session.share_hostname}' if session.share_hostname else ''})"
        return "🌐 Not sharing. Use: share on [hostname] | share persist" + persist

    def _cloud_creds(self):
        cfg = getattr(self, "cloud_config", {}) or {}
        sa = cfg.get("service_account") or ""
        url = cfg.get("database_url") or ""
        node = cfg.get("node") or "saturday-node"
        return sa, url, node

    def _handle_cloudsetup(self, args, raw_text):
        if len(args) < 2:
            return ("❌ Usage: cloudsetup <serviceAccount.json path> <database URL> [node]\n"
                    "   Firebase console (free Spark plan) → Realtime Database → locked mode → URL.\n"
                    "   Project settings → Service accounts → Generate key (keep the file private!).\n"
                    "   Memory-only: never written to disk.")
        from pathlib import Path as _P
        if not _P(args[0]).exists():
            return f"❌ Service file not found: {args[0]}"
        self.cloud_config = {"service_account": args[0], "database_url": args[1],
                             "node": args[2] if len(args) > 2 else "saturday-node"}
        return (f"☁️ Cloud DB armed (node {self.cloud_config['node']}). "
                "Try: cloudbackup. Ciphertext only ever leaves this PC.")

    def _handle_cloudbackup(self, args, raw_text):
        sa, url, node = self._cloud_creds()
        if not sa or not url:
            return "❌ Cloud DB not configured. Use: cloudsetup <json> <url>"
        from saturday import cloud as _cloud
        from pathlib import Path as _P
        vault_mem = str(_P(self.pmv.memory_engine.vault_path))
        salt = str(self.pmv.crypto.salt_path)
        print("☁️ Uploading encrypted blobs (ciphertext only)...")
        res = _cloud.backup_vault(vault_mem, salt, sa, url, node)
        if not res.get("success"):
            return f"❌ Backup failed: {res.get('error')}"
        return f"☁️ Backed up {res['entries']} encrypted entries + salt. Zero plaintext left the PC."

    def _handle_cloudrestore(self, args, raw_text):
        sa, url, node = self._cloud_creds()
        if not sa or not url:
            return "❌ Cloud DB not configured. Use: cloudsetup <json> <url>"
        from saturday import cloud as _cloud
        from pathlib import Path as _P
        vault_mem = str(_P(self.pmv.memory_engine.vault_path))
        salt = str(self.pmv.crypto.salt_path)
        print("☁️ Downloading backup (fills gaps only, never overwrites)...")
        res = _cloud.restore_vault(vault_mem, salt, sa, url, node)
        if not res.get("success"):
            return f"❌ Restore failed: {res.get('error')}"
        return (f"☁️ Restored {res['restored']} entries, skipped {res['skipped']} local. "
                "Same passphrase unlocks them.")

    def _handle_glow(self, args, raw_text):
        session = getattr(self, "session", None)
        arg = (args[0].lower() if args else "status")
        if arg == "on":
            if session is None:
                return "⚠️ Session not booted."
            if session.glow is None:
                session._start_glow()
            if session.glow and session.glow.enabled:
                return f"✨ Edge glow live ({session.glow.current()})."
            return "❌ Glow unavailable (no display/tkinter)."
        if arg == "off":
            if session and session.glow:
                session.glow.stop()
            return "✨ Edge glow off."
        if arg in ("idle", "listening", "thinking", "speaking", "alert"):
            if session and session.glow and session.glow.enabled:
                session.glow.set_state(arg)
                return f"✨ Glow → {arg}."
            return "❌ Glow not running. Use: glow on"
        if session and session.glow:
            return f"✨ Glow: {session.glow.current()}, enabled={session.glow.enabled}."
        return "✨ Glow not running. Use: glow on"

    def _handle_heal(self, args, raw_text):
        session = getattr(self, "session", None)
        if session is None or session.healer is None:
            return "🩺 Healer not running (session degraded)."
        session.healer.run_checks()
        return session.healer.summary()

    def _handle_assign(self, args, raw_text):
        rest = raw_text[len("assign"):].strip()
        if not rest:
            return "❌ Usage: assign <goal> [priority 1-9]. Example: assign research fusion 8"
        import re as _re
        m = _re.match(r"^(.*)\s+([1-9])$", rest)
        goal, prio = (m.group(1), int(m.group(2))) if m else (rest, 5)
        session = getattr(self, "session", None)
        if session is None:
            return "⚠️ Session not booted; use `do` instead."
        tid = session.inbox_add(goal=goal, kind="agent", priority=prio)
        session._start_inbox_worker()
        return f"🧭 Assigned {tid} (priority {prio}): {goal}\n   Inbox: `inbox`, history: `tasks`."

    def _handle_inbox(self, args, raw_text):
        session = getattr(self, "session", None)
        if session is None:
            return "📥 No inbox (session degraded)."
        items = session.inbox_list()
        if not items:
            return "📥 Inbox empty."
        lines = [f"   {i['id']} [{i['status']}] p{i['priority']} {i['kind']}: "
                 f"{(i['goal'] or i['text'])[:80]}" for i in items[-10:]]
        return "📥 Task inbox:\n" + "\n".join(lines)

    # -- Voice orchestration (ears → command → hands → voice) -----------
    def _glow_pulse(self, state: str, seconds: float = 4.0) -> None:
        try:
            session = getattr(self, "session", None)
            glow = getattr(session, "glow", None) if session else None
            if glow:
                glow.pulse(state, seconds)
        except Exception:
            pass

    def _speak(self, text: str) -> None:
        """Speak like a human: strip machine markers, soften, never read
        raw readouts (BPM/JSON/raw tags) aloud. Best-effort, never raises."""
        self._glow_pulse("speaking", 4.0)
        try:
            from saturday import humanvoice as hv

            spoken = hv.naturalize(str(text)) if hasattr(hv, "naturalize") else str(text)
            from interface.voice import SATURDAYVoice
            if getattr(self, "_voice", None) is None:
                self._voice = SATURDAYVoice(self)
            self._voice.speak(spoken[:300])
        except Exception:
            pass

    def _handle_say(self, args, raw_text):
        text = raw_text[len("say"):].strip()
        if not text:
            return "❌ Usage: say <text>. Example: say Systems online"
        self._speak(text)
        return f"🔊 Said: {text[:120]}"

    def _handle_hear(self, args, raw_text):
        secs = 5.0
        if args:
            try:
                secs = float(args[0])
            except ValueError:
                return "❌ Usage: hear [seconds]. Example: hear 5"
        print(f"👂 Listening for {secs:g}s — speak now...")
        try:
            res = ears.hear_once(secs)
        except KeyboardInterrupt:
            return "👂 Listen cancelled."
        if not res.get("success"):
            return f"❌ Hearing failed: {res.get('error')}"
        if not res.get("heard_something"):
            return f"👂 {res.get('note', 'Silence.')}"
        return f"👂 Heard ({res.get('language', '?')}): {res['text']}"

    def _handle_listen(self, args, raw_text):
        """Jarvis loop: hear → execute → speak, until goodbye/Ctrl+C."""
        secs = 6.0
        if args:
            try:
                secs = float(args[0])
            except ValueError:
                return "❌ Usage: listen [seconds per turn]. Example: listen 6"
        print("👂 Continuous listening — speak commands, 'goodbye' to stop, Ctrl+C anytime.")
        turns = 0
        while turns < 30:
            turns += 1
            try:
                self._glow_pulse("listening", 8.0)
                cap = ears.capture(secs)
                if not cap.get("success"):
                    print(f"   (mic: {cap.get('error')})")
                    continue
                if not ears.heard(cap["samples"]):
                    print("   (silence)")
                    continue
                gate = getattr(getattr(self, "session", None), "voice_gate", None)
                who = {"verdict": "open", "authorized": True}
                if gate is not None:
                    who = gate.who_authorized(cap["samples"])
                res = ears.transcribe(samples=cap["samples"],
                                      samplerate=cap["samplerate"])
            except KeyboardInterrupt:
                return "👂 Stopped listening."
            if not res.get("success"):
                print(f"   (hear: {res.get('error')})")
                continue
            text = (res.get("text") or "").strip()
            if not text:
                print("   (nothing understood)")
                continue
            print(f"👂 You said: {text}")
            if text.lower().rstrip(".!").strip() in ("goodbye", "stop", "stop listening",
                                                     "exit", "quit", "bye"):
                self._speak("Powering down listening mode.")
                return "👂 Stopped listening. Goodbye."
            if not who.get("authorized"):
                from saturday import humanvoice as hv

                self._speak(hv.refusal_line(who.get("verdict", "guest")))
                print(f"🔒 Not owner ({who.get('verdict')}) — command ignored.")
                continue
            out = self.process_command(text, trusted=True)
            print(f"🤖 {out[:500]}")
            self._speak(out)
        return "👂 Listen session ended (30-turn limit)."

    def _handle_brain(self, args, raw_text):
        """Fully unsupervised arbitrary goal, driven by the local brain."""
        goal = raw_text[len("brain"):].strip()
        if not goal:
            return "❌ Usage: brain <goal>. Example: brain find my cheapest electricity plan"
        if not self._current_trusted:
            return "❌ Unsupervised brain is local-only. Remote callers cannot use it."
        try:
            from saturday.brain import OllamaBrain
            brain = OllamaBrain()
            if not brain.available():
                return ("❌ Local brain offline. Start Ollama and pull a model:\n"
                        "   ollama pull llama3.2   (reasoning)\n"
                        "   ollama pull moondream  (vision)")
        except Exception as e:
            return f"❌ Brain failed to load: {e}"
        runner = AgentRunner(
            operator=self.screen,
            brain=brain,
            store_fn=lambda content, tags: self.pmv.secure_store(content, tags=tags),
            prompter=None,  # unsupervised: no human in the loop
            max_steps=20,
            confirm=True,   # local CLI = present user
        )
        print(f"\n🧠 Brain engaged, working alone: {goal}")
        print("   (failsafe active — slam mouse to a corner to abort motion)")
        self._glow_pulse("thinking", 120.0)
        finished = runner.run(AgentTask(goal, []))
        self._glow_pulse("idle", 0.1)
        self.agent_history.append(finished)
        self.agent_history = self.agent_history[-50:]
        return "\n" + finished.summary() + "\n"

    def _handle_help(self, args, raw_text):
        return (
            "Available commands:\n"
            " - store [content] tag:[tags] : Store encrypted memory.\n"
            " - retrieve [id] : Retrieve a stored entry.\n"
            " - delete [id] : Permanently delete a stored entry.\n"
            " - search tag:[tag] : Search memory by tag.\n"
            " - search : List recent entries.\n"
            " - status : Show system and vault status.\n"
            " - heartbeat : Update the deadman heartbeat.\n"
            " - sync : Trigger a sync operation.\n"
            "Screen (offline, no credentials needed):\n"
            " - open [app|url] : Open app or site. Example: open gmail\n"
            " - see : Screenshot the screen for review.\n"
            " - click [x] [y] : Click screen coordinates (see first).\n"
            " - type [text] : Type into the focused window.\n"
            " - press [key] / hotkey [k1] [k2] / scroll [n]\n"
            " - read : Read text off the screen (needs Tesseract).\n"
            " - clicktext [word] : Click on-screen text, no coordinates.\n"
            "Autonomy (SATURDAY acts by itself):\n"
            " - research [topic] : Search, read, and vault findings alone.\n"
            " - do [goal] : Work a goal alone (asks you when unsure).\n"
            " - brain [goal] : Fully unsupervised, local LLM brain decides.\n"
            " - tasks : Show recent autonomous tasks.\n"
            "Senses (real local camera sensing):\n"
            " - sense : People/faces/mood snapshot.\n"
            " - mood / hr [sec] / wellness : Expression, heart rate, composite.\n"
            " - drink [ml] / water : Log and check hydration.\n"
            "Voice (ears → command → voice, all local):\n"
            " - hear [sec] : Transcribe one listen (offline whisper).\n"
            " - say [text] : Speak through system voice.\n"
            " - listen : Continuous Jarvis loop until 'goodbye'.\n"
            "HUD + HomeBot Core2:\n"
            " - dashboard [port] : Start the local HUD (default 8099).\n"
            " - bot [cmd] [sec] [speed] : Drive Core2 (forward/stop/...).\n"
            " - botstatus : Link, telemetry, COM ports.\n"
            "Session (always-on autonomous system):\n"
            " - services : Camera/ears/brain/vault/bot/HUD status.\n"
            " - cam : Snapshot from the live camera hub.\n"
            " - queue [goal] : Background unsupervised task.\n"
            " - docker [args] : Container daemon status/passthrough.\n"
            " - maps [place] / route [a] to [b] : Online OSM maps.\n"
            "Identity + mind (it knows you, learns alone):\n"
            " - enroll [name] : Teach your face (~8s, encrypted).\n"
            " - who : Who is in view right now.\n"
            " - enrollvoice / voiceid : Owner voiceprint enroll/verify.\n"
            " - claps [on|off] : 1 clap = attention, 2 = quiet mode.\n"
            " - mind / learn : What it learned + consolidate now.\n"
            "Self-running system:\n"
            " - glow [on|off|state] : Screen-edge living glow.\n"
            " - heal : Watchdog check + self-repair now.\n"
            " - assign [goal] [prio] / inbox : Priority task inbox.\n"
            " - briefing / announce [text] : Spoken status / proclamation.\n"
            "Online (free) + cloud DB:\n"
            " - share [on|off] : Public tunnel URL + token for your phone.\n"
            " - server : Always-on layer status (tunnel + RTDB, not the AI).\n"
            " - cloudsetup/cloudbackup/cloudrestore : Encrypted Firebase backup.\n"
            " - help : Show this help text."
        )

    def _handle_unknown(self, args, raw_text):
        return "❓ Unknown command. Type 'help' for available commands."

    def get_status_payload(self):
        screen = getattr(self, "screen", None)
        if getattr(self, "_brain_probe", None) is None:
            try:
                from saturday.brain import OllamaBrain
                self._brain_probe = OllamaBrain()
            except Exception:
                self._brain_probe = None
        try:
            brain_on = bool(self._brain_probe.available()) if self._brain_probe else False
        except Exception:
            brain_on = False
        try:
            session = getattr(self, "session", None)
            session_snapshot = session.status() if session is not None else None
        except Exception:
            session_snapshot = None
        return {
            "online": self.is_running,
            "version": self.pmv.settings.get("version", "?"),
            "vault_mounted": self.pmv.vault_mounted,
            "deadman_status": self.pmv.get_deadman_status(),
            "node_status": self.pmv.node_status(),
            "screen_backend": backend_available(),
            "screen_actions": len(screen.history) if screen else 0,
            "ocr_available": ocr_available(),
            "mic_available": ears.mic_available(),
            "stt_available": ears.stt_available(),
            "brain_available": brain_on,
            "agent_tasks": len(getattr(self, "agent_history", [])),
            "identity": self._identity_snapshot(),
            "session": session_snapshot,
            "glow": self._glow_snapshot(),
            "last_activity": self.pmv.last_activity,
            "timestamp": time.time(),
        }

    def shutdown(self):
        if self.is_running:
            logger.info("Securing memory core...")
            try:
                session = getattr(self, "session", None)
                if session is not None:
                    session.shutdown()
            except Exception:
                pass
            self.pmv.dismount_vaults()
            self.is_running = False
            logger.info("SATURDAY Core deactivated.")
