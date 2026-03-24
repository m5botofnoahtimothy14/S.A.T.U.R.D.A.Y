# core/window_manager.py
"""
AEGIS Window Manager
Provides intelligent window layout control, virtual workspace assignment,
focus management and background-app monitoring using pyautogui + pygetwindow.
"""
import logging
import threading
import time
import psutil
import pygetwindow as gw
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.WindowManager")


class WindowManager:
    """
    AEGIS multi-window and workspace manager.
    - Track, snap and tile active windows
    - Monitor CPU/RAM per process and throttle background hogs
    - Voice-command aware: listens for layout intents on the event bus
    """

    LAYOUTS = {
        "focus":   [(0, 0, 1.0, 1.0)],                             # Full-screen single
        "split":   [(0, 0, 0.5, 1.0), (0.5, 0, 0.5, 1.0)],        # Side by side
        "grid4":   [(0, 0, 0.5, 0.5), (0.5, 0, 0.5, 0.5),
                    (0, 0.5, 0.5, 0.5), (0.5, 0.5, 0.5, 0.5)],    # 2×2 grid
        "sidebar": [(0, 0, 0.7, 1.0), (0.7, 0, 0.3, 1.0)],        # Main + sidebar
    }

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._monitor_running = False
        self._last_security_alert_time = 0.0
        self._last_security_alert_key = ""
        self._screen_w = 1920   # Will be auto-detected
        self._screen_h = 1080
        self._detect_resolution()
        self.event_bus.subscribe("voice_command", self._on_voice_command)
        self.event_bus.subscribe("screen_layout", self.apply_layout)
        logger.info(f"Window Manager initialized ({self._screen_w}×{self._screen_h}).")

    def _detect_resolution(self):
        try:
            import pyautogui
            self._screen_w, self._screen_h = pyautogui.size()
        except Exception:
            pass  # Use defaults

    # ------------------------------------------------------------------
    # Layout engine
    # ------------------------------------------------------------------
    def apply_layout(self, layout_name: str):
        """Apply a named layout to the currently visible windows."""
        slots = self.LAYOUTS.get(layout_name)
        if not slots:
            logger.warning(f"Unknown layout: {layout_name!r}")
            return

        windows = self._get_active_windows()
        for i, win in enumerate(windows[:len(slots)]):
            rx, ry, rw, rh = slots[i]
            try:
                x = int(rx * self._screen_w)
                y = int(ry * self._screen_h)
                w = int(rw * self._screen_w)
                h = int(rh * self._screen_h)
                win.moveTo(x, y)
                win.resizeTo(w, h)
                logger.info(f"  → {win.title[:30]!r}: ({x},{y}) {w}×{h}")
            except Exception as e:
                logger.warning(f"Could not move window: {e}")

        self.event_bus.publish("voice_response",
                               f"Applied {layout_name} layout to {len(windows)} windows.")

    def focus_window(self, title_fragment: str):
        """Bring a window matching the title fragment to the foreground."""
        for win in self._get_active_windows():
            if title_fragment.lower() in win.title.lower():
                try:
                    win.activate()
                    logger.info(f"Focused: {win.title!r}")
                    return True
                except Exception as e:
                    logger.warning(f"Focus failed: {e}")
        return False

    def _get_active_windows(self):
        try:
            return [w for w in gw.getAllWindows() if w.title.strip() and w.visible]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Background process monitor
    # ------------------------------------------------------------------
    def start_process_monitor(self, interval: float = 10.0, cpu_threshold: float = 80.0):
        """Start a daemon thread watching for CPU/memory hogs."""
        self._monitor_running = True
        threading.Thread(target=self._monitor_loop,
                         args=(interval, cpu_threshold), daemon=True).start()
        logger.info("Process monitor started.")

    def _monitor_loop(self, interval: float, cpu_threshold: float):
        # Skip checking System Idle Process and other system processes
        skip_processes = {"System Idle Process", "System", "Registry", "smss.exe", 
                         "csrss.exe", "wininit.exe", "services.exe", "lsass.exe"}
        
        alert_cooldown_sec = 30.0
        while self._monitor_running:
            hogs = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    proc_name = proc.info.get("name", "")
                    # Skip system processes and very short-lived processes
                    if proc_name in skip_processes:
                        continue
                    if proc.info["cpu_percent"] > cpu_threshold:
                        hogs.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Only alert if we have real hogs (not just system noise)
            if hogs and len(hogs) <= 3:
                # Filter out any remaining system processes
                real_hogs = [h for h in hogs if h.get("name", "") not in skip_processes]
                if real_hogs:
                    names = ", ".join(h["name"] for h in real_hogs[:3])
                    now = time.monotonic()
                    alert_key = ",".join(sorted(h.get("name", "") for h in real_hogs[:3]))
                    if (now - self._last_security_alert_time) >= alert_cooldown_sec or alert_key != self._last_security_alert_key:
                        self._last_security_alert_time = now
                        self._last_security_alert_key = alert_key
                        logger.info(f"High-CPU processes detected: {names}")
                        self.event_bus.publish("security_alert",
                                               {"type": "cpu_hog", "processes": real_hogs})
            time.sleep(interval)

    def stop_process_monitor(self):
        self._monitor_running = False

    # ------------------------------------------------------------------
    # Voice command handler
    # ------------------------------------------------------------------
    def _on_voice_command(self, command: str):
        cmd = command.lower()
        if "layout" in cmd:
            for name in self.LAYOUTS:
                if name in cmd:
                    self.apply_layout(name)
                    return
        if "focus" in cmd:
            # e.g. "focus chrome"
            words = cmd.split()
            idx = words.index("focus") if "focus" in words else -1
            if idx >= 0 and idx + 1 < len(words):
                self.focus_window(words[idx + 1])
