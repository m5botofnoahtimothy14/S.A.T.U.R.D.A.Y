import logging
import json
import shlex
import time
from pathlib import Path
from typing import Dict
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
        self.workmode = False  # True = sharp/focused, addressed as sir
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
            "remember": self._handle_remember,
            "recall": self._handle_recall,
            "profile": self._handle_profile,
            "family": self._handle_family,
            "secret": self._handle_secret,
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
            "volume": self._handle_volume,
            "mute": lambda a, r: self._handle_volume(["mute"], r),
            "media": self._handle_media,
            "play": lambda a, r: self._handle_media(["play"], r),
            "pause": lambda a, r: self._handle_media(["pause"], r),
            "next": lambda a, r: self._handle_media(["next"], r),
            "prev": lambda a, r: self._handle_media(["prev"], r),
            "tell": self._handle_tell,
            "verse": self._handle_verse,
            "edith": self._handle_edith,
            "workmode": self._handle_workmode,
            "sys": self._handle_sys,
            "sysclean": self._handle_sysclean,
            "evolve": self._handle_evolve,
            "do": self._handle_do,
            "research": self._handle_research,
            "tasks": self._handle_tasks,
            "stop": self._handle_agent_stop,
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
            "hand": self._handle_hand,
            "hands": self._handle_hand,
            "air": self._handle_hand,
            "gaze": self._handle_gaze,
            "eyes": self._handle_gaze,
            "look": self._handle_gaze,
            "cog": self._handle_cog,
            "focus": self._handle_cog,
            "mindread": self._handle_cog,
            "eeg": self._handle_cog,
            "think": self._handle_cog,
            "forge": self._handle_forge,
            "build": self._handle_forge,
            "model": self._handle_forge,
            "render": self._handle_forge,
            "blender": self._handle_forge,
            "neural": self._handle_neural,
            "nmulti": self._handle_neural,
            "nsearch": self._handle_nsearch,
            "imagine": self._handle_imagine,
            "skills": self._handle_skills,
            "calc": self._handle_calc,
            "math": self._handle_calc,
            "humanoid": self._handle_humanoid,
            "think": self._handle_humanoid,
            "feel": self._handle_feel,
            "answer": self._handle_feel,
            "eq": self._handle_feel,
            "resources": self._handle_resources,
            "doctor": self._handle_doctor,
            "mic": self._handle_mic,
            "mailbox": self._handle_mailbox,
            "relay": self._handle_relay,
            "help": self._handle_help,
        }

    def _parse_command(self, cmd_string: str):
        text = (cmd_string or "").strip()
        try:
            tokens = shlex.split(text)
        except ValueError:
            tokens = text.split()  # apostrophes/quotes fall back to naive split
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

    # -- Memory: teach me, recall, profile, secrets ----------------------
    # Everything lands encrypted in YOUR vault (Fernet). Secrets are tagged
    # and never shown by recall/profile — only by explicit `secret get`.
    def _handle_remember(self, args, raw_text):
        fact = raw_text[len("remember"):].strip()
        if not fact:
            return "❌ Usage: remember <fact about you>. Example: remember my wife's name is Rida"
        entry_id = self.pmv.secure_store(fact, entry_type="fact", tags=["profile-fact"])
        return f"Noted — I'll remember that. (id {entry_id[:8]})"

    def _handle_recall(self, args, raw_text):
        query = raw_text[len("recall"):].strip().lower()
        try:
            results = self.pmv.secure_search() or []
        except Exception as e:
            return f"❌ Recall failed: {e}"
        # Secrets never leak through recall.
        results = [r for r in results if "secret" not in (r.get("tags") or [])]
        if query:
            results = [r for r in results if query in str(r.get("content", "")).lower()]
        if not results:
            return "I don't have anything on that yet. Teach me with: remember <fact>"
        results = sorted(results, key=lambda e: e.get("timestamp", 0), reverse=True)[:3]
        lines = [f"   - {str(r.get('content', ''))[:120]}" for r in results]
        return "Here's what I remember:\n" + "\n".join(lines)

    def _handle_profile(self, args, raw_text):
        try:
            facts = self.pmv.secure_search(tag="profile-fact") or []
            fam = self.pmv.secure_search(tag="family") or []
        except Exception as e:
            return f"❌ Profile unreadable: {e}"
        if not facts and not fam:
            return ("I don't know you yet. Teach me: remember <fact>, "
                    "family add <name> <relation>, enroll, enrollvoice.")
        lines = [f"   - {str(r.get('content', ''))[:120]}" for r in
                 sorted(facts, key=lambda e: e.get("timestamp", 0), reverse=True)[:10]]
        for r in fam:
            lines.append(f"   - family: {str(r.get('content', ''))[:120]}")
        return "What I know about you:\n" + "\n".join(lines)

    def _handle_family(self, args, raw_text):
        rest = raw_text[len("family"):].strip()
        if rest.lower().startswith("add"):
            parts = rest[3:].strip().split(None, 1)
            if len(parts) < 2:
                return "❌ Usage: family add <name> <relation>. Example: family add Rida wife"
            name, relation = parts
            entry_id = self.pmv.secure_store(f"{name} ({relation})",
                                             entry_type="fact", tags=["family"])
            return f"Noted — {name} ({relation}). I'll treat them with care. (id {entry_id[:8]})"
        try:
            fam = self.pmv.secure_search(tag="family") or []
        except Exception as e:
            return f"❌ Family list unreadable: {e}"
        if not fam:
            return "No family recorded. Usage: family add <name> <relation>"
        return "Family:\n" + "\n".join(f"   - {str(r.get('content', ''))[:80]}" for r in fam)

    def _handle_secret(self, args, raw_text):
        if not args or args[0] not in ("save", "get"):
            return "❌ Usage: secret save <label> | secret get <label>"
        if args[0] == "save":
            if len(args) < 2:
                return "❌ Usage: secret save <label>"
            label = args[1]
            try:
                import getpass as _gp

                value = _gp.getpass(f"   Password for '{label}' (hidden) ❯ ")
            except Exception:
                return "❌ Hidden input unavailable here."
            if not value:
                return "❌ Empty — nothing stored."
            entry_id = self.pmv.secure_store(f"[secret:{label}] {value}",
                                             entry_type="secret", tags=["secret"])
            return f"Locked away under '{label}'. (id {entry_id[:8]})"
        label = args[1] if len(args) > 1 else ""
        try:
            found = self.pmv.secure_search(tag="secret") or []
        except Exception as e:
            return f"❌ Secret lookup failed: {e}"
        for r in found:
            content = str(r.get("content", ""))
            if content.startswith(f"[secret:{label}]"):
                return f"Password for '{label}': {content.split(' ', 1)[1] if ' ' in content else ''}"
        return f"No secret stored under '{label}'. Usage: secret save <label>"

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

    def _handle_volume(self, args, raw_text):
        if not args or args[0] not in ("up", "down", "mute"):
            return "❌ Usage: volume <up|down|mute>"
        result = self.screen.volume(args[0], confirm=self._current_trusted)
        if not result.get("success"):
            return self._screen_denied(result)
        return f"Volume {result['action']} (media-key sent)."

    def _handle_media(self, args, raw_text):
        if not args or args[0] not in ("play", "pause", "stop", "next", "prev"):
            return "❌ Usage: media <play|pause|stop|next|prev> (or: play, pause, next, prev)"
        result = self.screen.media(args[0], confirm=self._current_trusted)
        if not result.get("success"):
            return self._screen_denied(result)
        return f"Media {result['action']} (media-key sent)."

    def _handle_tell(self, args, raw_text):
        """Read the screen, then SAY it: reading + speaking in one move."""
        seen = self.screen.read_screen(args[0] if args else None)
        if not seen.get("success"):
            return f"❌ Read failed: {seen.get('error')}"
        from saturday import humanvoice as hv

        said = hv.naturalize(seen.get("text", "")[:600])
        try:
            self._speak(said)
        except Exception as e:
            return f"Read {len(seen.get('words', []))} words, but voice failed: {e}\n   {said}"
        return f"Read {len(seen.get('words', []))} words and spoke: {said}"

    def _handle_verse(self, args, raw_text):
        try:
            from saturday import verse as _v
        except Exception as e:
            return f"❌ Verse module missing: {e}"
        ref = " ".join(args).strip()
        return _v.verse_of_day() if not ref else _v.verse_lookup(ref)

    def _handle_edith(self, args, raw_text):
        """EDITH: same brain, female voice, only when called."""
        if not self._current_trusted:
            return "❌ EDITH is local-only. Remote callers cannot use her."
        try:
            from saturday import edith as _ed

            return _ed.edith_handle(self, raw_text)
        except Exception as e:
            return f"❌ EDITH failed: {e}"

    # -- People: owner, family, workmode ---------------------------------
    def _owner_name(self) -> str:
        try:
            return (self.pmv.settings.get("identity", {}).get("owner_name", "")
                    or __import__("os").getenv("SATURDAY_OWNER", "") or "Noah")
        except Exception:
            return "Noah"

    def _family(self) -> Dict[str, str]:
        """Lowercased name → relation, from vault family facts."""
        try:
            found = self.pmv.secure_search(tag="family") or []
            out: Dict[str, str] = {}
            for r in found:
                content = str(r.get("content", ""))
                if "(" in content and content.endswith(")"):
                    nm, rel = content.rsplit("(", 1)
                    out[nm.strip().lower()] = rel[:-1].strip().lower()
            return out
        except Exception:
            return {}

    def _handle_workmode(self, args, raw_text):
        if args and args[0].lower() in ("on", "off"):
            self.workmode = args[0].lower() == "on"
            try:
                self.screen._audit("workmode", args[0], method="prefs",
                                   target="self", result=args[0])
            except Exception:
                pass
            return (f"Work mode ON — sharp and focused, sir."
                    if self.workmode else f"Work mode off — relaxed, {self._owner_name()}.")
        return f"Work mode is {'ON' if getattr(self, 'workmode', False) else 'off'}. Usage: workmode on|off"

    # -- Lawful admin: allowlisted READ-ONLY diagnostics -------------------
    # No free-form shell, no arguments, no writes, no privilege tricks.
    # Exact command names only; output truncated; everything audit-logged.
    SYS_ALLOWLIST = {
        "ver": ["cmd", "/c", "ver"],
        "whoami": ["whoami"],
        "hostname": ["hostname"],
        "ipconfig": ["ipconfig"],
        "tasklist": ["tasklist"],
        "netstat": ["netstat", "-an"],
        "drivers": ["driverquery", "/FO", "TABLE"],
    }

    @staticmethod
    def _we_are_elevated() -> bool:
        try:
            import ctypes as _ct

            return bool(_ct.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _handle_sys(self, args, raw_text):
        if not self._current_trusted:
            return "❌ sys diagnostics are local-only. Remote callers cannot use them."
        if not args or args[0].lower() not in self.SYS_ALLOWLIST:
            known = ", ".join(sorted(self.SYS_ALLOWLIST))
            return f"❌ Usage: sys <{known}>. Read-only diagnostics only — no free shell."
        name = args[0].lower()
        import subprocess as _sp

        elev = "elevated" if self._we_are_elevated() else "not elevated"
        try:
            r = _sp.run(self.SYS_ALLOWLIST[name], capture_output=True, text=True,
                        timeout=30, errors="replace")
            out = (r.stdout or "") + (r.stderr or "")
            out = out.strip()[:3000] or "(no output)"
            logger.warning(f"sys {name} ({elev}) by local user")
            try:
                self.screen._audit("sys", name, method="allowlist-shell",
                                   target=name, result=f"rc={r.returncode}")
            except Exception:
                pass
            return f"[{name}] ({elev}, rc={r.returncode}):\n{out}"
        except _sp.TimeoutExpired:
            return f"❌ sys {name} timed out after 30s."
        except Exception as e:
            return f"❌ sys {name} failed: {e}"

    def _handle_sysclean(self, args, raw_text):
        """Admin cleanup WITH your consent: launches an elevated PowerShell
        (Windows shows YOU the UAC prompt — approve it or nothing runs).
        Never bypasses UAC; that path does not exist here."""
        if not self._current_trusted:
            return "❌ sysclean is local-only."
        import tempfile as _tf

        script = (
            "$ErrorActionPreference='SilentlyContinue';"
            "dism /online /cleanup-image /startcomponentcleanup;"
            "Remove-Item $env:TEMP\\* -Recurse -Force;"
            "Remove-Item C:\\Windows\\Temp\\* -Recurse -Force;"
            "Remove-Item C:\\Windows\\SoftwareDistribution\\Download\\* -Recurse -Force;"
            "cleanmgr /sagerun:1;"
            "Write-Host 'SATURDAY admin cleanup done.'; Start-Sleep 5")
        path = str(_tf.NamedTemporaryFile(suffix=".ps1", delete=False,
                                          dir=r"D:\SATURDAY_TEMP").name)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(script)
        except Exception as e:
            return f"❌ Could not stage cleanup script: {e}"
        try:
            import ctypes as _ct

            rc = _ct.windll.shell32.ShellExecuteW(
                None, "runas", "powershell",
                f'-NoProfile -ExecutionPolicy Bypass -File "{path}"', None, 1)
            if int(rc) <= 32:
                return "❌ Elevation refused or failed (UAC said no — nothing ran)."
            try:
                self.screen._audit("sysclean", "elevated cleanup launched",
                                   method="runas-uac", target="C:",
                                   result="user-approved")
            except Exception:
                pass
            return ("⬆️ Elevated cleanup launched — approve the Windows UAC prompt "
                    "and it cleans WinSxS + temps. Deny it and nothing runs.")
        except Exception as e:
            return f"❌ Elevation launch failed: {e}"

    # -- Self code-writing (evolve): draft → YOUR approval → apply → test --
    # The brain proposes a unified diff for ONE project file; nothing applies
    # without your typed YES; backup kept; py_compile + related test must pass
    # or it auto-rolls back. This is how SATURDAY rewrites itself safely.
    def _handle_evolve(self, args, raw_text):
        if not self._current_trusted:
            return "❌ evolve is local-only."
        goal = raw_text[len("evolve"):].strip()
        if not goal:
            return "❌ Usage: evolve <file.py> <what to change>. Example: evolve verse add 5 verses"
        parts = goal.split(None, 1)
        if len(parts) < 2:
            return "❌ Usage: evolve <file.py> <what to change>."
        fname, change = parts
        from pathlib import Path as _P

        target = (_P.cwd() / fname).resolve() if not _P(fname).is_absolute() else _P(fname).resolve()
        root = _P(__file__).parent.parent.resolve()
        try:
            target.relative_to(root)
        except Exception:
            return f"❌ Refusing: {fname} is outside the SATURDAY project."
        if not target.exists() or target.suffix != ".py":
            return f"❌ Refusing: {target} is not an existing project .py file."
        try:
            from saturday.brain import OllamaBrain

            brain = OllamaBrain(timeout=300)  # codegen needs room on 8GB boxes
            if not brain.available():
                return "❌ Brain offline (Ollama). Evolve needs the local LLM."
        except Exception as e:
            return f"❌ Brain failed to load: {e}"
        try:
            original = target.read_text(encoding="utf-8")
        except Exception as e:
            return f"❌ Cannot read {target}: {e}"
        system = ("You output ONLY a unified diff (--- a/file, +++ b/file, @@ hunks) "
                  "for the given Python file. No explanations. Max 60 diff lines. "
                  "RULES: copy context lines CHARACTER-FOR-CHARACTER from the file, "
                  "never retype or shorten them; 2 context lines before/after max; "
                  "small hunk only.")
        prompt = (f"FILE: {target.name}\n```python\n{original[:12000]}\n```\n"
                  f"CHANGE: {change}\nUnified diff only:")
        try:
            raw = brain._generate(brain.model, prompt, system=system,
                                  json_mode=False, num_ctx=2048)
        except Exception as e:
            return f"❌ Brain generation failed: {e}"
        diff = self._extract_diff(raw)
        if not diff:
            return f"❌ Brain returned no usable diff. Raw head:\n{raw[:400]}"
        print(f"\n🧬 Proposed patch for {target.name}:\n{diff[:2000]}")
        print("Type YES to apply (backup kept, tests must pass) or anything else to drop it.")
        try:
            answer = input("   Apply ❯ ").strip()
        except Exception:
            answer = ""
        if answer != "YES":
            return "Dropped — no files touched."
        bak = str(target) + f".pre-evolve-{int(__import__('time').time())}.bak"
        try:
            _P(bak).write_text(original, encoding="utf-8")
            patched = self._apply_diff(original, diff)
            target.write_text(patched, encoding="utf-8")
        except Exception as e:
            return f"❌ Patch rejected (context mismatch, file untouched): {e}"
        import py_compile as _pc

        try:
            _pc.compile(str(target), doraise=True)
        except Exception as e:
            _P(bak).replace(target)
            return f"❌ Patched file would not compile — rolled back from backup. ({e})"
        test_out = self._evolve_test(target)
        try:
            self.screen._audit("evolve", f"{target.name}: {change[:80]}",
                               method="brain-diff", target=str(target),
                               result="applied" if test_out[0] else "rolled-back")
        except Exception:
            pass
        if not test_out[0]:
            _P(bak).replace(target)
            return f"❌ Tests failed after patch — rolled back from backup.\n{test_out[1][:500]}"
        return (f"🧬 Evolved {target.name}: {change[:100]}\n"
                f"   compile OK, {test_out[1]}Backup: {bak}")

    @staticmethod
    def _extract_diff(raw: str) -> str:
        import re as _re

        m = _re.search(r"```(?:diff)?\s*(.*?)\s*```", raw, _re.S)
        text = m.group(1) if m else raw
        lines = [ln for ln in text.splitlines()
                 if ln.startswith(("---", "+++", "@@", " ", "+", "-"))]
        lines = [ln for ln in lines if not ln.startswith(("--- /dev", "+++ /dev"))]
        hunks = [ln for ln in lines if ln.startswith("@@")]
        if not hunks or len(lines) > 200:
            return ""
        return "\n".join(lines) + "\n"

    @staticmethod
    def _apply_diff(original: str, diff: str) -> str:
        import re as _re

        src = original.splitlines(keepends=False)
        out: list = []
        pos = 0
        for line in diff.splitlines():
            if line.startswith(("---", "+++")):
                continue
            m = _re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if m:
                start = int(m.group(1)) - 1
                if start < pos:
                    raise ValueError("overlapping hunks")
                out.extend(src[pos:start])
                pos = start
                continue
            if line.startswith(" ") or line == "":
                if pos >= len(src) or src[pos] != line[1:]:
                    raise ValueError(f"context mismatch at line {pos + 1}")
                out.append(src[pos])
                pos += 1
            elif line.startswith("-"):
                if pos >= len(src) or src[pos] != line[1:]:
                    raise ValueError(f"removal mismatch at line {pos + 1}")
                pos += 1
            elif line.startswith("+"):
                out.append(line[1:])
            else:
                raise ValueError(f"bad diff line: {line[:40]}")
        out.extend(src[pos:])
        return "\n".join(out) + ("\n" if original.endswith("\n") else "")

    def _evolve_test(self, target):
        """Compile passed already; run the mapped unit test file if it exists."""
        import subprocess as _sp

        name = target.stem
        cand = target.parent.parent / "tests" / f"test_{name}.py"
        if not cand.exists():
            cand = target.parent / f"test_{name}.py"
        if not cand.exists():
            return True, "no mapped test file (compile only). "
        try:
            r = _sp.run(["python", str(cand)], capture_output=True, text=True,
                        timeout=240, errors="replace")
            tail = (r.stdout or "")[-300:] + (r.stderr or "")[-300:]
            ok = ("OK" in tail and "FAILED" not in tail) or r.returncode == 0
            return ok, f"{cand.name} rc={r.returncode}. "
        except Exception as e:
            return False, f"test run failed: {e}"

    # -- Agent (autonomy: SATURDAY acts by itself) ---------------------
    def _run_agent_task(self, task: AgentTask) -> str:
        trusted = self._current_trusted
        prompter = None
        confirm_fn = None
        if trusted:
            def prompter(question, observation):
                print(f"\n🤖 SATURDAY asks: {question}")
                return input("   You ❯ ").strip()

            def confirm_fn(question):
                print(f"\n⚠️ {question}")
                return input("   Confirm (type YES) ❯ ").strip() == "YES"
        agent_cfg = {}
        try:
            agent_cfg = (self.pmv.settings.get("agent", {}) or {})
        except Exception:
            pass
        runner = AgentRunner(
            operator=self.screen,
            brain=TemplateBrain(),
            store_fn=lambda content, tags: self.pmv.secure_store(content, tags=tags),
            prompter=prompter,
            confirm=trusted,
            confirm_fn=confirm_fn,
            allowed_apps=agent_cfg.get("allowed_apps", []),
            allowed_actions=agent_cfg.get("allowed_actions", []),
            context_fn=self._mood_context_fn(),
        )
        print(f"\n🤖 Working on it by myself: {task.goal}")
        print("   (failsafe ON + kill switch Ctrl+Alt+Shift+X or say 'stop')")
        finished = runner.run(task)
        self.agent_history.append(finished)
        self.agent_history = self.agent_history[-50:]  # bounded for long runs
        return "\n" + finished.summary() + "\n"

    def _mood_context_fn(self):
        """Trusted mood line for agent/brain prompts (OUR sensor, not screen)."""
        def _ctx():
            try:
                session = getattr(self, "session", None)
                if session is not None and hasattr(session, "mood_context"):
                    return session.mood_context()
            except Exception:
                pass
            return ""
        return _ctx

    def _handle_agent_stop(self, args, raw_text):
        from saturday import agent as _agent

        _agent.request_stop()
        return "⏹️ Stop requested — all agent task execution halts immediately."

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
                    "patrol|autonomy_on|autonomy_off|express WORD> [seconds] [speed]. "
                    "Example: bot forward 2 80 | bot patrol 3")
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
        if name == "patrol":
            res = self._homebot_link().patrol(minutes=duration, speed=speed)
            if res.get("status") == "success":
                return f"🤖 {res['message']}"
            return f"❌ {res.get('reason', res.get('status'))}"
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

    def enroll_photo(self, name: str, image_bytes: bytes) -> dict:
        """Website training: photo upload → face scan → vault gallery.
        Same norm/recognize pipeline as live camera, so uploads cross-verify
        against live frames. Returns {saved, faces_found} or honest error."""
        import base64 as _b64

        import numpy as _np

        name = (name or "").strip()
        if not name or len(name) > 40:
            return {"success": False, "error": "Name required (max 40 chars)."}
        if not image_bytes or len(image_bytes) > 8_000_000:
            return {"success": False, "error": "Photo missing or over 8MB."}
        try:
            import cv2 as _cv2

            arr = _np.frombuffer(image_bytes, dtype=_np.uint8)
            img = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
            if img is None:
                return {"success": False, "error": "Not a readable photo (JPEG/PNG only)."}
        except Exception as e:
            return {"success": False, "error": f"Photo decode failed: {e}"}
        gallery = self._gallery()
        if not gallery.available():
            return {"success": False, "error": "Face engine unavailable."}
        faces = senses.find_faces(img)
        boxes = faces.get("boxes", []) if faces.get("success") else []
        if not boxes:
            return {"success": False, "error": "No face found in this photo. Upload a clear front-facing pic."}
        saved = 0
        try:
            for b in sorted(boxes, key=lambda r: r["w"] * r["h"], reverse=True)[:3]:
                crop = img[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]]
                normed = gallery.norm(crop)
                if normed:
                    self.pmv.secure_store(_b64.b64encode(normed).decode(),
                                          tags=["identity", f"person:{name}"])
                    saved += 1
        except Exception as e:
            return {"success": False, "error": f"Vault save failed ({e}). Unlock first."}
        self._gallery_cache = None
        self._gallery()  # retrain incl. the new samples
        logger.warning(f"Photo-enrolled '{name}': {saved} sample(s) from upload")
        return {"success": True, "person": name, "faces_found": len(boxes),
                "saved": saved}

    def forget_person(self, name: str) -> dict:
        """Delete every gallery sample for a person (vault entries by id)."""
        name = (name or "").strip()
        if not name:
            return {"success": False, "error": "Name required."}
        try:
            found = self.pmv.secure_search(tag="identity") or []
            n = 0
            for e in found:
                tags = e.get("tags", []) or []
                if any(t == f"person:{name}" or t.lower() == f"person:{name.lower()}" for t in tags):
                    try:
                        if self.pmv.secure_delete(e.get("id", "")):
                            n += 1
                    except Exception:
                        pass
            self._gallery_cache = None
            self._gallery()
            return {"success": True, "person": name, "deleted": n}
        except Exception as e:
            return {"success": False, "error": str(e)[:120]}

    def gallery_roster(self) -> dict:
        """Who the camera knows: names + sample counts (for the website)."""
        try:
            found = self.pmv.secure_search(tag="identity") or []
            counts: dict = {}
            for e in found:
                for t in e.get("tags", []) or []:
                    if t.startswith("person:"):
                        counts[t.split(":", 1)[1]] = counts.get(t.split(":", 1)[1], 0) + 1
            return {"success": True, "people": counts}
        except Exception as e:
            return {"success": False, "error": str(e)[:120]}

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
        try:
            from saturday.identity import LBPH_THRESHOLD as _THR
        except Exception:
            _THR = 55.0
        return (f"👤 {len(boxes)} face(s), none recognized{extra} "
                f"(closest distance {dist}, need under {_THR}). "
                f"Upload sharper front-facing pics in FACE TRAINING.")

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
        out = "🧠 Consolidated:\n" + session.mind.consolidate()
        # sleep cycle: custom brain + episodic memory consolidate alongside
        try:
            from saturday import custom_brain as _cb, humanoid as _h
            r = _cb.learn()
            e = _h.consolidate_episodes()
            out += (f"\n💤 Sleep cycle: brain learn #{r['cycle']} (+{r['new_decisions']} decisions, "
                    f"{r['skills']['skills']} skills, test {r['trained']['test_acc']}) + "
                    f"episodes kept {e['kept']} (dropped {e['dropped']}, merged {e['merged']}).")
        except Exception as ex:
            out += f"\n💤 Sleep skipped: {ex}"
        return out

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
        if arg == "token":
            # Zero Trust token tunnel: NO cert, NO zone, NO domain needed.
            # Token lives in memory only — never written anywhere.
            # Bare `share token` uses SATURDAY_TUNNEL_TOKEN/_HOSTNAME env (the default).
            import os as _os
            tok_arg = args[1] if len(args) > 1 else ""
            host_arg = args[2] if len(args) > 2 else ""
            env_tok = _os.getenv("SATURDAY_TUNNEL_TOKEN", "")
            env_host = _os.getenv("SATURDAY_TUNNEL_HOSTNAME", "")
            use_tok = tok_arg or env_tok
            use_host = host_arg or env_host
            if not use_tok or not use_host:
                return ("❌ Usage: share token <TOKEN> <public-hostname>\n"
                        "   Or set SATURDAY_TUNNEL_TOKEN + SATURDAY_TUNNEL_HOSTNAME "
                        "in .env, then bare `share token`.\n"
                        "   Zero Trust → Tunnels → tunnel → copy Token; route the hostname there.")
            if self._dashboard is None:
                self.process_command("dashboard 8099", trusted=True)
            tok = self._dashboard.share() if self._dashboard else {"token": ""}
            res = link.start_token(use_tok, use_host)
            if not res.get("success"):
                return f"❌ Token tunnel failed: {res.get('error')}"
            try:
                session = getattr(self, "session", None)
                if session is not None:
                    session._write_share_url(res["url"], tok.get("token", ""))
            except Exception:
                pass
            return (f"🌐 SATURDAY is ONLINE (stable): {res['url']}\n"
                    f"   🔑 Token (show once, guard it): {tok.get('token', '')}\n"
                    f"   This address never rotates. `share off` kills it.")
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
            ct = "clicks pass ✅" if session.glow.click_through else "clicks MAY block ⚠️"
            return (f"✨ Glow: {session.glow.current()}, enabled={session.glow.enabled}, "
                    f"{ct}.")
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
        """Fully unsupervised arbitrary goal, driven by the local brain.
        Subcommands: brain train | brain learn | brain status | brain distill [n]
                     brain custom on|off | brain fairness
        Otherwise: brain <goal> runs it (CustomBrain when custom mode is on —
        zero network calls — else the Ollama teachers)."""
        sub = (args[0].lower() if args else "")
        if sub in ("train", "learn", "status", "distill", "custom", "fairness"):
            return self._handle_brain_ops(sub, args[1:], raw_text)
        goal = raw_text[len("brain"):].strip()
        if not goal:
            return "❌ Usage: brain <goal>. Example: brain find my cheapest electricity plan"
        if not self._current_trusted:
            return "❌ Unsupervised brain is local-only. Remote callers cannot use it."
        try:
            from saturday import custom_brain as _cb
            custom = bool(_cb._read_json("mode.json", {}).get("custom"))
        except Exception:
            custom = False
        try:
            if custom:
                from saturday.custom_brain import CustomBrain
                brain = CustomBrain()
                tag = "custom brain (ours, Ollama-free)"
            else:
                from saturday.brain import OllamaBrain
                brain = OllamaBrain()
                if not brain.available():
                    return ("❌ Local brain offline. Start Ollama and pull a model:\n"
                            "   ollama pull llama3.2   (reasoning)\n"
                            "   ollama pull moondream  (vision)\n"
                            "   ...or switch to ours: brain custom on")
                tag = "teachers (llama3.2)"
        except Exception as e:
            return f"❌ Brain failed to load: {e}"
        runner = AgentRunner(
            operator=self.screen,
            brain=brain,
            store_fn=lambda content, tags: self.pmv.secure_store(content, tags=tags),
            prompter=None,  # unsupervised: no human in the loop
            max_steps=15,
            confirm=True,   # local CLI = present user
            confirm_fn=None,  # ...but destructive steps are REFUSED, never assumed
            context_fn=self._mood_context_fn(),
            speak_fn=self._speak,
        )
        print(f"\n🧠 Brain engaged ({tag}), working alone: {goal}")
        print("   (failsafe active — slam mouse to a corner to abort motion)")
        self._glow_pulse("thinking", 120.0)
        finished = runner.run(AgentTask(goal, []))
        self._glow_pulse("idle", 0.1)
        self.agent_history.append(finished)
        self.agent_history = self.agent_history[-50:]
        return "\n" + finished.summary() + "\n"

    def _handle_brain_ops(self, sub, rest, raw_text):
        from saturday import custom_brain as _cb
        if sub == "status":
            s = _cb.status()
            lines = [f"🧠 Custom brain: {'TRAINED' if s['trained'] else 'untrained'} | "
                     f"mode={'CUSTOM (Ollama-free)' if s['custom_mode'] else 'teachers'} | "
                     f"net={'ONLINE' if s['online'] else 'OFFLINE'}",
                     f"   samples={s['samples']} train={s['train_acc']} test={s['test_acc']} "
                     f"skills={s['skills']} cycles={s['learn_cycles']} "
                     f"vectors={s['embeddings_cached']} decisions={s['decisions_logged']}"]
            lines.append(f"   teachers: {', '.join(s['teachers'])}")
            return "\n".join(lines)
        if sub == "train":
            print("🧠 Training intent classifier on seeds + curriculum + your history...")
            r = _cb.train_intent()
            return (f"🧠 Trained: {r['samples']} samples, {r['intents']} intents — "
                    f"train {r['train_acc']}, held-out test {r['test_acc']}. "
                    f"{'(honest gap: daily `brain learn` closes it with your real phrasings)' if r['test_acc'] < 0.9 else ''}")
        if sub == "learn":
            print("🧠 Daily consolidation: mining skills, caching vectors, retraining...")
            r = _cb.learn()
            return (f"🧠 Learned (cycle {r['cycle']}): +{r['new_decisions']} decisions, "
                    f"{r['skills']['skills']} skills (+{r['skills']['added']}), "
                    f"test acc {r['trained']['test_acc']}, "
                    f"{r['embeddings_cached']} vectors cached, {r['pruned']} stale pruned.")
        if sub == "distill":
            n = 5
            if rest:
                try:
                    n = max(1, min(20, int(rest[0])))
                except ValueError:
                    pass
            from tests.test_neural import L1
            print(f"🧠 Asking BOTH teachers about {n} cases (slow, CPU — minutes)...")
            votes = []
            for goal, _ in L1[:n]:
                v = _cb.teacher_label(goal)
                votes.append((goal[:50], v["winner"], v["disagree"]))
                _cb.log_decision(goal, "", v["winner"], {}, "teacher-ensemble", True)
            lines = [f"🧠 {len(votes)} teacher votes (kept in the log for training):"]
            lines += [f"   {g}: {w}{' ⚠️ teachers disagree' if d else ''}" for g, w, d in votes]
            return "\n".join(lines)
        if sub == "custom":
            want = (rest[0].lower() if rest else "")
            mode = _cb._read_json("mode.json", {})
            if want in ("on", "off"):
                mode["custom"] = (want == "on")
                _cb._write_json("mode.json", mode)
                return ("🧠 Custom mode ON — `brain <goal>` now runs with ZERO network calls. "
                        "Prove it: stop Ollama, it still works. `brain custom off` to return."
                        if mode["custom"] else
                        "🧠 Teacher mode — `brain <goal>` uses llama3.2 (+qwen when distilling).")
            return f"🧠 Custom mode is {'ON' if mode.get('custom') else 'off'}. Usage: brain custom on|off"
        if sub == "fairness":
            rep = _cb.fairness_probes()
            lines = [f"⚖️ Fairness probes: {rep['passed']}/{rep['total']} — {rep['verdict']}"]
            for p in rep["probes"]:
                lines.append(f"   {'✅' if p['consistent'] else '❌'} {p['ask']}: {p['intents']}")
            lines.append("   Charter: ensemble teachers · disagreements logged · "
                         "persona-free prompts · framing probes (see custom_brain.FAIRNESS_CHARTER). "
                         "Note: perfect neutrality is impossible (ICML'25); this is bias-reduced + audited.")
            return "\n".join(lines)
        return "❌ Usage: brain train|learn|status|distill [n]|custom on|off|fairness|<goal>"

    def _handle_neural(self, args, raw_text):
        cmd = (args[0].lower() if args else "")
        from saturday import neural as _neural
        if cmd == "roster" or (not args and not raw_text.split(None, 1)[1:]):
            p = _neural.probe()
            ok = [k for k, v in p.items() if v is True]
            return (f"🧬 Neural roster: {len(ok)} live — "
                    + ", ".join(k for k in
                                ("llama3.2", "moondream", "nomic-embed-text", "whisper",
                                 "piper", "diffusers", "ddgs") if p.get(k) is True or p.get(k))
                    + f" | piper voices={p.get('piper_voices')} | net={'online' if p.get('ollama') else '?'}")
        if raw_text.lower().startswith("nmulti"):
            goals = [g.strip() for g in raw_text[len("nmulti"):].split("|") if g.strip()]
            if len(goals) < 2:
                return "❌ Usage: nmulti goal one | goal two | goal three (parallel VM)"
            if not self._current_trusted:
                return "❌ Parallel runs are local-only."
            import concurrent.futures
            from saturday import agent as _agent
            print(f"🧬 Multitasking {len(goals)} goals in parallel...")
            def _one(gl):
                try:
                    return _neural.NeuralRunner(self, max_steps=6).run(gl, speak=False)
                except Exception as e:
                    return {"success": False, "goal": gl, "summary": str(e)[:150]}
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(goals))) as ex:
                results = list(ex.map(_one, goals))
            lines = [f"🧬 Multitask done ({sum(1 for r in results if r.get('success'))}/{len(results)}):"]
            for r in results:
                lines.append(f"   {'✅' if r.get('success') else '❌'} {r.get('summary', '')[:150]}")
            try:
                self._speak(f"All {len(results)} tasks finished.")
            except Exception:
                pass
            return "\n".join(lines)
        goal = raw_text[len("neural"):].strip()
        if not goal:
            return "❌ Usage: neural <goal>. Example: neural research fusion and announce it"
        if not self._current_trusted:
            return "❌ Neural runs are local-only."
        res = _neural.NeuralRunner(self).run(goal)
        lines = [f"🧬 {res.get('summary', '')}"]
        for t in res.get("transcript", [])[:8]:
            lines.append(f"   {t['cmd'][:80]} → {str(t['result'])[:120]}")
        return "\n".join(lines)

    def _handle_nsearch(self, args, raw_text):
        topic = raw_text[len("nsearch"):].strip()
        if not topic:
            return "❌ Usage: nsearch <topic>. Example: nsearch quantum batteries"
        try:
            from saturday import custom_brain as _cb
            refused = _cb.gate_online("nsearch")
            if refused:
                return refused
        except Exception:
            pass
        from saturday import neural as _neural
        print(f"🔎 Searching the real web: {topic}")
        res = _neural.web_search(topic)
        if not res.get("success"):
            return f"❌ {res.get('error')}"
        lines = [f"🔎 {res['count']} real results for '{topic}':"]
        for h in res["results"][:5]:
            lines.append(f"   • {h['title'][:90]}\n     {h['url'][:110]}")
        try:
            bundle = "\n".join(f"- {h['title']} ({h['url']}): {h['snippet'][:200]}"
                               for h in res["results"])
            self.pmv.secure_store(f"[nsearch {topic}]\n{bundle}", tags=["research"])
            lines.append("   📦 Vaulted (encrypted).")
        except Exception:
            pass
        return "\n".join(lines)

    def _handle_imagine(self, args, raw_text):
        prompt = raw_text[len("imagine"):].strip()
        if not prompt:
            return "❌ Usage: imagine <prompt>. Example: imagine a robot at sunset"
        if not self._current_trusted:
            return "❌ Imagine renders locally — remote callers cannot start it."
        from saturday import resources as _res
        g = _res.guard("imagine")
        if not g["ok"]:
            return f"🔴 {g['reason']}"
        from saturday import neural as _neural
        res = _neural.imagine(prompt)
        if not res.get("success"):
            return f"❌ Imagine failed: {res.get('error')}"
        return (f"🎨 Dreamed in {res['seconds']}s ({res['engine']}):\n"
                f"   {res['path']}\n   Open it with: open {res['path']}")

    def _handle_skills(self, args, raw_text):
        from saturday import custom_brain as _cb
        sk = _cb._read_json("skills.json", {"skills": []})["skills"]
        if not sk:
            return "🧬 No skills mined yet — run tasks (`neural ...`) then `brain learn`."
        lines = [f"🧬 {len(sk)} learned skills (replayed Ollama-free):"]
        for s in sk[:15]:
            lines.append(f"   • {s['name']} ×{s['uses']} → {s.get('steps', [])}")
        return "\n".join(lines)

    def _handle_calc(self, args, raw_text):
        verb = (args[0].lower() if args else "")
        expr = raw_text.split(None, 1)[1] if len(raw_text.split(None, 1)) > 1 else ""
        if verb in ("help", "?") or not expr:
            return "❌ Usage: calc <expression>. Example: calc 15% of 240 | calc sqrt(144) | calc solve x^2-4"
        from saturday import neural as _neural
        res = _neural.calculate(expr)
        if not res.get("success"):
            return f"❌ {res.get('error')}"
        extra = (" | " + "; ".join(res["steps"])) if res.get("steps") else ""
        return f"🔢 {res['expression']} = {res['display']}{extra}  [{res['engine']}]"

    def _handle_feel(self, args, raw_text):
        from saturday import emotion as _em
        verb = (args[0].lower() if args else "")
        if raw_text.lower().startswith("eq") and (not args or verb in ("status",)):
            s = _em.eq_status()
            return (f"💜 Emotional intelligence: lexicon {s['lexicon']} | "
                    f"playbook v{s['playbook_version']} ({s['comfort_lines']} lines) | "
                    f"{s['charter']}")
        if raw_text.lower().startswith("answer"):
            q = raw_text[len("answer"):].strip()
            if not q:
                return "❌ Usage: answer <question>. I think + feel + answer on my own."
            if not self._current_trusted:
                return "❌ Answering is local-only."
            try:
                mood_now = (getattr(getattr(self, "session", None), "last_mood", None) or {}).get("mood")
            except Exception:
                mood_now = None
            print(f"💜 Thinking + feeling: {q[:100]}")
            res = _em.answer(q, core=self, user_state={"mood": mood_now})
            if not res.get("success"):
                return f"❌ {res.get('error')}"
            lines = [f"💜 {res['answer'][:600]}",
                     f"   path={res.get('path')} conf={res.get('confidence')} "
                     f"felt={res.get('emotion_read', {}).get('label')}"]
            if res.get("dissent"):
                lines.append("   ⚠️ teachers saw two sides — ask me to dig deeper.")
            return "\n".join(lines)
        text = raw_text[len("feel"):].strip() if raw_text.lower().startswith("feel") else raw_text
        if not text:
            return "❌ Usage: feel <text>. Example: feel I'm nervous about tomorrow"
        r = _em.analyze(text)
        e = _em.empathize(r["label"], r["intensity"], r.get("cause", ""))
        return (f"💜 You feel {r['label']} ({r['intensity']}) — "
                f"valence {r['vad'][0]}, arousal {r['vad'][1]}"
                + (f" about {r['cause']}" if r.get("cause") else "") + f"\n"
                f"   {e['full'][:300]}")

    def _handle_humanoid(self, args, raw_text):
        from saturday import humanoid as _h
        verb = (args[0].lower() if args else "")
        if verb in ("status", "state", "") and len(raw_text.split()) <= 2:
            if verb == "" :
                pass  # fall through to think below when goal words present
            else:
                s = _h.status()
                lines = ["🤖 HUMANOID BRAIN — human-like + machine-exact:",
                         f"   System 1 (fast, Ollama-free): {s['s1']}",
                         f"   System 2 (slow, deliberate): {s['s2']}",
                         f"   Episodes: {s['episodes']} | sightings: {s['sightings']}"]
                if s.get("beliefs"):
                    lines.append(f"   Beliefs about you: {s['beliefs']}")
                lines.append("   Drives, ToM, arbiter, sleep: always on during `humanoid <goal>`.")
                return "\n".join(lines)
        goal = raw_text.split(None, 1)[1] if len(raw_text.split(None, 1)) > 1 else ""
        if verb == "status":
            s = _h.status()
            return (f"🤖 S1: {s['s1']}\n   S2: {s['s2']}\n"
                    f"   Episodes: {s['episodes']} | beliefs: {s.get('beliefs', {})}")
        if not goal:
            return "❌ Usage: humanoid <goal> | humanoid status. Example: humanoid research fusion and announce it"
        if not self._current_trusted:
            return "❌ Humanoid runs are local-only."
        # refresh the model-of-you + drives from live state
        try:
            facts = []
            try:
                found = self.pmv.secure_search(tag="profile-fact") or []
                facts = [str(r.get("content", ""))[:120] for r in found[-10:]]
            except Exception:
                pass
            mood_now = None
            try:
                mood_now = (getattr(getattr(self, "session", None), "last_mood", None) or {}).get("mood")
            except Exception:
                pass
            _h.update_user_model(dict(getattr(self, "cmd_counts", {})), facts, mood_now)
        except Exception:
            pass
        print(f"\n🤖 Humanoid thinking (fast + slow): {goal}")
        res = _h.think(goal)
        r = res["route"]
        lines = [f"🤖 Path: {r['path']} — {r['reason']}",
                 f"   ToM: {res['tom']} | tone: {res['drives'].get('tone')}"]
        if res.get("dissent"):
            lines.append(f"   ⚠️ Teachers disagree — both views kept: {str(res['dissent'])[:200]}")
        plan = res.get("plan", [])
        if r["path"] == "ask" or not plan:
            return "\n".join(lines + [f"   {res.get('answer', '')}"])
        # execute the S1/S2 plan as real commands (machine-exact half)
        from saturday import neural as _neural
        runner = _neural.NeuralRunner(self, max_steps=6)
        ran = runner.run(goal, speak=False)
        lines.append(f"   Ran {len(ran.get('transcript', []))} steps: "
                     f"{ran.get('summary', '')[:150]}")
        try:
            self._speak(ran.get("summary", "Done."))
        except Exception:
            pass
        return "\n".join(lines)

    # -- JARVIS hands / gaze / mind / forge (real, installed, no mocks) ----
    def _session_frame_fn(self):
        session = getattr(self, "session", None)
        try:
            if session is not None and session.camera.running:
                def _fn():
                    try:
                        return session.camera.get_frame(max_age=5.0)
                    except Exception:
                        return None
                # probe one frame
                if _fn() is not None:
                    return _fn
        except Exception:
            pass
        return None

    def _handle_hand(self, args, raw_text):
        from saturday import hands as _h
        sub = (args[0].lower() if args else "status")
        if sub in ("status", "test", "check"):
            got = self._camera_frame()
            if not got.get("success"):
                return f"❌ {got['error']}"
            res = _h.snapshot(got["frame"])
            if not res.get("success"):
                return f"❌ Hand scan failed: {res.get('error')}"
            if not res.get("hands"):
                return (f"🖐️ No hands in view ({res.get('method')}). "
                        "Hold palm to camera, good light.")
            lines = [f"🖐️ {res.get('count')} hand(s) via {res.get('method')}:"]
            for i, hd in enumerate(res["hands"][:2]):
                if hd.get("landmarks"):
                    lines.append(f"   {i+1}. {hd.get('gesture')} "
                                 f"fingers={','.join(hd.get('fingers', [])) or 'fist'} "
                                 f"pinch={hd.get('pinch_dist')}px "
                                 f"({hd.get('handedness', '')})")
                else:
                    lines.append(f"   {i+1}. {hd.get('gesture')} "
                                 f"(box {hd.get('box')})")
            lines.append("   Gestures: point=move, pinch=click, victory=right-click, fist-hold=scroll.")
            return "\n".join(lines)
        if sub in ("live", "on", "air", "control"):
            secs = 30.0
            if len(args) > 1:
                try:
                    secs = float(args[1])
                except ValueError:
                    return "❌ Usage: hand live [seconds]. Example: hand live 30"
            secs = min(max(secs, 5.0), 300.0)
            if not self._current_trusted:
                return "❌ Hand control is local-only."
            print(f"🖐️ AIR CONTROL {secs:g}s — fingertip moves, pinch clicks, victory right-clicks, Q quits.")
            print("   Failsafe: slam mouse to corner aborts.")
            res = _h.live_air_control(secs, confirm=True,
                                      use_session_frames=self._session_frame_fn())
            if not res.get("success"):
                return f"❌ Air control failed: {res.get('error')}"
            s = res["stats"]
            return (f"🖐️ Air session done: {s['moves']} moves, {s['clicks']} clicks, "
                    f"{s['right']} right-clicks, {s['frames']} frames "
                    f"(last: {res.get('last_gesture')}).")
        return ("❌ Usage: hand status | hand live [sec].\n"
                "   status = one scan (gesture + fingers). live = fingertip air-mouse.")

    def _handle_gaze(self, args, raw_text):
        from saturday import gaze as _g
        sub = (args[0].lower() if args else "status")
        if sub in ("status", "check", "look"):
            got = self._camera_frame()
            if not got.get("success"):
                return f"❌ {got['error']}"
            res = _g.snapshot(got["frame"])
            if not res.get("success"):
                return f"❌ {res.get('error')}"
            f = res["faces"][0]
            r = f.get("ratios", {}) or {}
            direction = "center"
            try:
                hx, hy = r.get("hx", 0.5), r.get("hy", 0.5)
                direction = (("left " if hx < 0.35 else "right " if hx > 0.65 else "")
                             + ("up" if hy < 0.35 else "down" if hy > 0.65 else ""))
                direction = direction.strip() or "center"
            except Exception:
                pass
            cal = "calibrated" if res.get("calibrated") else "NOT calibrated (run: gaze calibrate)"
            pt = res.get("gaze_point")
            return (f"👁️ Gaze: looking {direction} | blink={'YES' if f.get('blink') else 'no'} "
                    f"EAR={f.get('ear')} | {cal}"
                    + (f" | screen ~({pt[0]},{pt[1]})" if pt else ""))
        if sub == "calibrate":
            if not self._current_trusted:
                return "❌ Gaze calibrate is local-only."
            print("👁️ 5-point gaze calibration — look at each prompt, press SPACE.")
            res = _g.calibrate_interactive(use_session_frames=self._session_frame_fn())
            if not res.get("success"):
                return f"❌ Calibration failed: {res.get('error')}"
            return (f"✅ Gaze calibrated: mean error {res['mean_err_px']}px "
                    f"({res['note']})")
        if sub in ("live", "control", "on"):
            secs = 30.0
            if len(args) > 1:
                try:
                    secs = float(args[1])
                except ValueError:
                    return "❌ Usage: gaze live [seconds]. Example: gaze live 30"
            if not self._current_trusted:
                return "❌ Gaze control is local-only."
            print(f"👁️ GAZE CONTROL {secs:g}s — look to move, blink/dwell clicks, Q quits.")
            res = _g.live_gaze_control(min(max(secs, 5.0), 300.0), confirm=True,
                                       use_session_frames=self._session_frame_fn())
            if not res.get("success"):
                return f"❌ Gaze control failed: {res.get('error')}"
            s = res["stats"]
            return (f"👁️ Gaze session done: {s['moves']} moves, "
                    f"{s['blinks']} blink-clicks, {s['dwells']} dwell-clicks.")
        if sub in ("read", "what"):
            got = self._camera_frame()
            if not got.get("success"):
                return f"❌ {got['error']}"
            res = _g.read_at_gaze(self.screen, got["frame"])
            if not res.get("success"):
                return f"❌ Eye reading failed: {res.get('error')}"
            txt = res.get("text", "") or "(no text under your gaze)"
            return (f"👁️ You're looking at {res.get('gaze')} — I read:\n"
                    f"   {txt[:400]}")
        return ("❌ Usage: gaze status | gaze calibrate | gaze live [sec] | gaze read.\n"
                "   status=where you look, calibrate=5-point, live=eye-mouse, read=OCR under gaze.")

    def _handle_cog(self, args, raw_text):
        from saturday import cognition as _c
        sub = (args[0].lower() if args else "read")
        if sub in ("boards", "list"):
            res = _c.list_eeg_boards()
            if not res.get("success"):
                return f"❌ {res.get('error')}"
            return ("🧠 EEG boards (BrainFlow): " + ", ".join(res["boards"][:12]) + "\n"
                    f"   {res['note']}")
        if sub == "eeg":
            secs = 10.0
            board = -1
            if len(args) > 1:
                try:
                    secs = float(args[1])
                except ValueError:
                    pass
            if len(args) > 2:
                try:
                    board = int(args[2])
                except ValueError:
                    return "❌ Usage: eeg [seconds] [board_id]. Example: eeg 10 -1"
            print(f"🧠 EEG recording {secs:g}s (board {board})...")
            res = _c.eeg_session(board_id=board, seconds=min(max(secs, 3.0), 60.0))
            if not res.get("success"):
                return f"❌ {res.get('error')}"
            b = res["bands_rel"]
            return (f"🧠 EEG bands (real DSP, {res['seconds']}s, {res['channels']}ch @{res['sfreq']}Hz):\n"
                    f"   delta {b['delta']} theta {b['theta']} alpha {b['alpha']} "
                    f"beta {b['beta']} gamma {b['gamma']}\n"
                    f"   focus {res['focus']} calm {res['calm']} fatigue {res['fatigue']}\n"
                    f"   {res['disclaimer']}")
        # read / focus / mindread / think: psychology + EEG-refined snapshot
        got = self._camera_frame()
        blink_pm, hx, hy, mood_lab = None, None, None, None
        if got.get("success"):
            try:
                from saturday import gaze as _g
                gs = _g.snapshot(got["frame"])
                if gs.get("success") and gs.get("faces"):
                    f0 = gs["faces"][0]
                    r = f0.get("ratios") or {}
                    hx, hy = r.get("hx"), r.get("hy")
                    blink_pm = 4.0 if f0.get("blink") else 12.0
            except Exception:
                pass
            try:
                from saturday import senses as _s
                mr = _s.mood(got["frame"])
                if mr.get("success"):
                    mood_lab = mr.get("mood")
            except Exception:
                pass
        recent = list((getattr(self, "cmd_counts", {}) or {}).keys())[-8:]
        snap = _c.cognitive_snapshot(blink_per_min=blink_pm or 12.0,
                                     gaze_stability=0.7 if hx is not None else 0.5,
                                     hr_bpm=None, mood=mood_lab,
                                     recent_commands=recent)
        if sub in ("think", "mindread") and len(args) > 1:
            goal = raw_text.split(None, 1)[1] if len(raw_text.split(None, 1)) > 1 else ""
            if sub == "think" and goal:
                return (f"🧠 Intent: {snap['intent']} ({snap['intent_confidence']}) — {snap['why']}.\n"
                        f"   Focus {snap['focus']} ({snap['focus_level']}), load {snap['load']}.\n"
                        f"   To act on '{goal[:80]}', confirm with: do {goal[:80]}")
        return (f"🧠 Mind readout — focus {snap['focus']} ({snap['focus_level']}), "
                f"load {snap['load']} ({snap['load_level']}), calm {snap['calm']}.\n"
                f"   Intent: {snap['intent']} ({snap['intent_confidence']}) — {snap['why']}.\n"
                + (f"   Advice: {'; '.join(snap['advice'])}" if snap["advice"] else "   Steady state.")
                + f"\n   [{snap['disclaimer']}]")

    def _handle_forge(self, args, raw_text):
        from saturday import forge as _f
        cmd = (args[0].lower() if args else "")
        rest = raw_text.split(None, 1)[1] if len(raw_text.split(None, 1)) > 1 else ""
        # strip leading subcommand word for build prompts
        if cmd in ("system", "status", "probe"):
            s = _f.system_probe()
            return (f"🏭 Forge system: {s['os']} | RAM {s.get('ram_gb')}GB "
                    f"| GPU {s.get('gpu','?')[:60]} | engine {s['engine']} "
                    f"{s['resolution'][0]}x{s['resolution'][1]} | "
                    f"Blender {'OK '+s['blender'][:60] if s['blender_ok'] else 'MISSING'} | "
                    f"D: free {s.get('disk_free_gb')}GB")
        if cmd in ("list", "jobs"):
            res = _f.forge_list()
            if not res.get("success") or not res.get("jobs"):
                return "🏭 No forged models yet. Try: forge building 10 floors glass tower"
            lines = [f"🏭 {len(res['jobs'])} forged model(s):"]
            for j in res["jobs"][:8]:
                lines.append(f"   {j['job']}\n      GLB: {j['glb']}\n      PNG: {j['preview']}")
            return "\n".join(lines)
        prompt = rest
        if cmd in ("forge", "build", "model", "render", "blender") and len(args) > 1:
            # user typed e.g. `build building ...` — rest already excludes first word
            pass
        if not prompt or cmd in ("help", "?"):
            return ("❌ Usage: forge <what>. Example: forge building 12 floors glass tower\n"
                    "   forge system (this PC render path) | forge list (your models)")
        if not self._current_trusted:
            return "❌ Forge renders locally — remote callers cannot start Blender."
        from saturday import resources as _res
        g = _res.guard("forge render")
        if not g["ok"]:
            return f"🔴 {g['reason']}"
        print(f"🏭 Forging: {prompt[:100]} — Blender headless building + rendering...")
        res = _f.forge_build(prompt)
        if not res.get("success"):
            return (f"❌ Forge failed: {res.get('error')}\n"
                    f"   Spec: {res.get('spec')}\n"
                    f"   Job dir: {res.get('jobdir', '?')}")
        q = res.get("qa", {})
        return (f"🏭 Forged {res['spec']['name']}: {res['spec']['floors']} floors, "
                f"{res['spec']['style']} ({res['engine']}, {res['seconds']}s).\n"
                f"   GLB: {res['glb']} ({q.get('.glb_bytes', '?')}b)\n"
                f"   Preview: {res['preview']} (luma {q.get('preview_mean_luma', '?')})\n"
                f"   Geometry: {q.get('counts', {})}")

    def _handle_resources(self, args, raw_text):
        from saturday import resources as _res
        sub = (args[0].lower() if args else "")
        if sub == "unload":
            if not self._current_trusted:
                return "❌ Model unload is local-only."
            r = _res.unload_idle()
            if not r.get("success") and not r.get("freed_gb"):
                return f"❌ Unload failed: {r.get('error', r.get('failed'))}"
            return (f"🧹 Freed {r['freed_gb']}GB Ollama RAM"
                    + (f" (kept: {', '.join(r['kept'])})" if r["kept"] else "")
                    + (f" (failed: {r['failed']})" if r.get("failed") else ""))
        s = _res.snapshot()
        lines = [f"⚙️ {_res.status_line()}"]
        for m in s.get("ollama", {}).get("models", [])[:6]:
            lines.append(f"   🧠 {m['name']} ({m['size_gb']}GB resident)")
        for r in s.get("throttle", {}).get("reasons", []):
            lines.append(f"   ⚠️ {r}")
        return "\n".join(lines)

    def _handle_doctor(self, args, raw_text):
        """Ordered boot gates: every subsystem probed, truth printed."""
        rows = []

        def gate(name, fn):
            try:
                ok, note = fn()
                rows.append(("✅" if ok else "❌", name, note))
            except Exception as e:
                rows.append(("❌", name, str(e)[:100]))

        def _vault():
            ok = bool(self.pmv.vault_mounted)
            return ok, "mounted" if ok else "LOCKED — unlock first"
        gate("vault", _vault)

        def _mic():
            from saturday import ears
            if not ears.mic_available():
                return False, "sounddevice missing"
            devs = ears.list_mics()
            n = len(devs.get("mics", [])) if devs.get("success") else 0
            return n > 0, f"{n} input device(s)"
        gate("mic", _mic)

        def _stt():
            from saturday import ears
            ok = ears.stt_available()
            dn = "denoise on" if getattr(ears, "DENOISE_ENABLED", False) else "denoise off"
            return ok, f"whisper ready, {dn}" if ok else "faster-whisper missing"
        gate("hearing", _stt)

        def _tts():
            from saturday import kokoro_voice as _kv
            v = _kv.voices()
            if v:
                return True, f"Kokoro human voice ({len(v)} voices)"
            return True, "Kokoro missing — Piper/SAPI chain active"
        gate("voice", _tts)

        def _cam():
            try:
                got = self._camera_frame()
                return bool(got.get("success")), got.get("error", "live")[:80]
            except Exception as e:
                return False, str(e)[:80]
        gate("camera", _cam)

        def _brain():
            try:
                from saturday.brain import OllamaBrain
                ok = OllamaBrain(timeout=10).available()
                return ok, "llama3.2 ready" if ok else "Ollama down — custom brain covers routine"
            except Exception as e:
                return False, str(e)[:80]
        gate("brain", _brain)

        def _REN():
            from saturday import forge as _f
            b = _f.find_blender()
            return bool(b.get("success")), (b.get("exe", "?") or "?")[:60] if b.get("success") else b.get("error", "?")[:80]
        gate("blender", _REN)

        def _tun():
            from saturday import share as _sh
            b = _sh.find_cloudflared()
            return bool(b), b[:60] if b else "winget install Cloudflare.cloudflared"
        gate("tunnel-bin", _tun)

        def _fb():
            import os as _os
            sa = _os.getenv("FIREBASE_SERVICE_ACCOUNT", "")
            db = _os.getenv("FIREBASE_DATABASE_URL", "")
            if sa and db:
                return True, "creds present (mailbox live)"
            return False, "no creds — run: relay (setup playbook)"
        gate("firebase", _fb)

        def _disk():
            from saturday import resources as _res
            s = _res.snapshot(cpu_interval=0)
            ok = (s.get("disk_d_free_gb") or 0) > 2 and (s.get("ram_avail_gb") or 0) > 1
            return ok, (f"D: {s.get('disk_d_free_gb')}GB free, "
                        f"RAM {s.get('ram_avail_gb')}GB free, CPU {s.get('cpu_pct')}%")
        gate("resources", _disk)

        bad = sum(1 for e, _, _ in rows if e == "❌")
        lines = [f"🩺 Doctor: {len(rows)-bad}/{len(rows)} green" + (" — all systems go" if not bad else " — see red lines")]
        for e, name, note in rows:
            lines.append(f"   {e} {name}: {note}")
        return "\n".join(lines)

    def _handle_mic(self, args, raw_text):
        from saturday import ears
        sub = (args[0].lower() if args else "status")
        if sub == "status":
            devs = ears.list_mics()
            if not devs.get("success"):
                return f"❌ {devs.get('error')}"
            sel = ears.resolve_mic_device()
            lines = [f"🎙️ {len(devs['mics'])} mic(s), selected device {sel}, "
                     f"denoise {'ON' if ears.DENOISE_ENABLED else 'OFF'}, gain {ears._resolve_gain()}x:"]
            for m in devs["mics"][:8]:
                lines.append(f"   [{m['index']}] {m['name']} ({m['host_api']}, {m['default_samplerate']:.0f}Hz)")
            return "\n".join(lines)
        if sub == "level":
            secs = float(args[1]) if len(args) > 1 and args[1].replace(".", "", 1).isdigit() else 5.0
            print(f"🎙️ Speak now ({secs:g}s meter)...")
            r = ears.input_level_meter(secs)
            if not r.get("success"):
                return f"❌ {r.get('error')}"
            return f"🎙️ peak {r['peak']} — bars should have moved while you spoke."
        if sub == "denoise" and len(args) > 1:
            on = args[1].lower() in ("on", "1", "yes")
            ears.DENOISE_ENABLED = on
            return f"🎙️ Denoise {'ON (spectral gating before Whisper)' if on else 'OFF (raw audio to Whisper)'}."
        if sub == "test":
            print("🎙️ Say something (5s)...")
            res = ears.hear_once(5.0)
            if not res.get("success"):
                return f"❌ {res.get('error')}"
            if not res.get("heard_something"):
                return f"🎙️ {res.get('note', 'Silence.')}"
            dn = res.get("denoise", {})
            return (f"🎙️ Heard: {res['text']}\n"
                    f"   denoise SNR {dn.get('snr_before')}→{dn.get('snr_after')}dB "
                    f"| VAD {res.get('vad_trim', {})}")
        return "❌ Usage: mic status | mic level [sec] | mic denoise on|off | mic test"

    def _handle_mailbox(self, args, raw_text):
        """Firebase RTDB command mailbox: queued while laptop sleeps, drained on boot."""
        import os as _os
        sa = _os.getenv("FIREBASE_SERVICE_ACCOUNT", "")
        db = _os.getenv("FIREBASE_DATABASE_URL", "")
        node = _os.getenv("FIREBASE_NODE_ID", "saturday-node")
        if not sa or not db:
            return ("❌ Mailbox needs Firebase creds (free Spark plan, no card).\n"
                    "   Run `relay` for the 10-minute setup playbook.")
        sub = (args[0].lower() if args else "status")
        try:
            from realtime_bridge import RealtimeDatabaseBridge
            br = RealtimeDatabaseBridge(service_account=sa, database_url=db, node_id=node)
            cmds = br.commands_ref.get() or {}
            pend = sum(1 for v in (cmds.values() if isinstance(cmds, dict) else [])
                       if isinstance(v, dict) and v.get("status") == "pending")
            if sub == "prune":
                if not self._current_trusted:
                    return "❌ Prune is local-only."
                import time as _t
                cut = _t.time() - 24 * 3600
                n = 0
                for k, v in (cmds.items() if isinstance(cmds, dict) else []):
                    if isinstance(v, dict) and v.get("status") in ("executed", "error") \
                            and float(v.get("completed_at", 0) or 0) < cut:
                        try:
                            br.commands_ref.child(k).delete()
                            n += 1
                        except Exception:
                            pass
                return f"📬 Pruned {n} results older than 24h. {pend} pending."
            return (f"📬 Mailbox /saturday_system/{node}/commands: {pend} pending.\n"
                    "   Pending survives laptop-off (Google hosts it) and drains on next boot.")
        except Exception as e:
            return f"❌ Mailbox unreachable: {e}"[:200]

    def _handle_relay(self, args, raw_text):
        return (
            "🛰️ ALWAYS-ON TRUTH + SETUP PLAYBOOK\n"
            "   Honest physics first: a Cloudflare tunnel is an OUTBOUND pipe from THIS\n"
            "   laptop. Laptop asleep/off = tunnel dead, no software changes that.\n"
            "   What stays alive while you sleep (Google hosts it, free Spark plan):\n"
            "   • Firebase RTDB mailbox — phone/web drops commands as 'pending';\n"
            "     this laptop executes + writes results on next boot. Nothing lost.\n"
            "   • Presence heartbeat — anyone can see awake/asleep + last-seen.\n"
            "   • Encrypted vault backup (`cloudbackup`) — restorable anywhere.\n"
            "   SETUP (10 min, free, no card):\n"
            "   1. console.firebase.google.com → Create project → Build →\n"
            "      Realtime Database → Create → locked mode → copy the URL.\n"
            "   2. Project settings → Service accounts → Generate new private key.\n"
            "   3. Save the .json OUTSIDE the repo (e.g. D:\\keys\\sat-fb.json).\n"
            "   4. In SATURDAY: cloudsetup D:\\keys\\sat-fb.json <your-db-url>\n"
            "   5. Verify: `mailbox` (should show 0 pending), then `cloudbackup`.\n"
            "   LAPTOP-OFF CONTROL (optional, pick one):\n"
            "   A. Mailbox mode (free, now): queue in RTDB, drains on boot. Done.\n"
            "   B. Relay mode (~$0: Oracle Always-Free VM or a Pi at home):\n"
            "      install cloudflared there, `cloudflared tunnel run --token ...`\n"
            "      pointing at a tiny relay that only reads/writes YOUR RTDB\n"
            "      mailbox. Phone talks to relay 24/7; laptop drains on wake.\n"
            "   Tunnel on THIS laptop (`share on`) stays the fast path while awake."
        )

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
            " - mic status|level|denoise|test : mic picker, meter, denoise, loopback test.\n"
            "Health (doctor + resource governor):\n"
            " - doctor : ordered boot gates for every subsystem (truth, not vibes).\n"
            " - resources [unload] : CPU/RAM/disk/temp + Ollama RAM budget.\n"
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
            " - mailbox [prune] : RTDB command queue (survives laptop-off).\n"
            " - relay : always-on truth + free setup playbook (tunnel vs mailbox vs relay).\n"
            "JARVIS hands / eyes / mind / forge (real, installed):\n"
            " - hand status | hand live [sec] : 21-landmark air-mouse (pinch=click).\n"
            " - gaze status | gaze calibrate | gaze live [sec] | gaze read : eye-mouse + eye reading.\n"
            " - cog | focus | mindread | eeg [sec] : focus/load/intent + real EEG bands.\n"
            " - forge <building ...> | forge system | forge list : Blender headless 3D + render.\n"
            "Neural virtual system (many free open models, one mind):\n"
            " - neural <goal> : run anything end-to-end (research→act→speak).\n"
            " - nmulti <g1> | <g2> : multitask goals in parallel.\n"
            " - nsearch <topic> : real web search, vaulted. imagine <prompt> : dream it locally.\n"
            " - calc <expr> : real math (sympy). skills : learned reusable skills.\n"
            " - brain <goal> | brain train|learn|status|distill [n]|custom on|off|fairness.\n"
            " - humanoid <goal> | humanoid status : dual-process mind (fast+slow, ToM, drives).\n"
            " - feel <text> | eq | answer <question> : emotional intelligence + own answers.\n"
            " - help : Show this help text."
        )

    def _resources_snapshot(self):
        """Sub-second, never raises: HUD polls this every 2s."""
        try:
            from saturday import resources as _res
            return _res.snapshot(cpu_interval=0, light=True)
        except Exception:
            return {"throttle": {"throttled": False, "reasons": []}}

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
        try:
            mood_snapshot = getattr(self.session, "last_mood", None)
        except Exception:
            mood_snapshot = None
        return {
            "online": self.is_running,
            "version": self.pmv.settings.get("version", "?"),
            "creator": "Noah Timothy Keba",
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
            "resources": self._resources_snapshot(),
            "identity": self._identity_snapshot(),
            "session": session_snapshot,
            "mood": mood_snapshot,
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
