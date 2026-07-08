                     
import threading
import logging
import os
import sys
import webbrowser
import subprocess

logger = logging.getLogger("SATURDAY.SystemTray")

SATURDAY_URL = "http://localhost:8000"

class SystemTray:
    
    def __init__(self, saturday_core=None):
        self.saturday_core = saturday_core
        self.tray = None
        self.running = False
        self._tray_thread = None
        
    def start(self):
        
        if self.running:
            logger.warning("System tray already running")
            return
            
        self.running = True
        self._tray_thread = threading.Thread(target=self._run_tray, daemon=True, name="SATURDAY-SystemTray")
        self._tray_thread.start()
        logger.info("System tray started")
        
    def _run_tray(self):
        
        try:
            from pystray import Icon, Menu, MenuItem
            from PIL import Image, ImageDraw
        except ImportError as e:
            logger.error(f"pystray or PIL not available: {e}")
            self.running = False
            return
            
        icon_image = self._create_icon()
        
        menu = Menu(
            MenuItem("Open SATURDAY Dashboard", self._show_window),
            Menu.SEPARATOR,
            MenuItem("Wake SATURDAY", self._wake_saturday),
            MenuItem("Start Voice Recognition", self._start_voice),
            MenuItem("Start Camera", self._start_camera),
            MenuItem("Toggle Security Mode", self._toggle_security),
            Menu.SEPARATOR,
            MenuItem("System Status", self._show_status),
            MenuItem("View Logs", self._view_logs),
            Menu.SEPARATOR,
            MenuItem("Restart SATURDAY", self._restart_saturday),
            MenuItem("Quit SATURDAY", self._quit)
        )
        
        try:
            self.tray = Icon("SATURDAY", icon_image, "SATURDAY AI OS", menu)
            logger.info("System tray icon created, starting tray loop...")
            self.tray.run()
        except Exception as e:
            logger.error(f"Failed to run system tray: {e}")
            self.running = False
        
    def _create_icon(self):
        
        from PIL import Image, ImageDraw
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), 'black')
        dc = ImageDraw.Draw(image)
        
        dc.polygon([
            (32, 4), (56, 18), (56, 46), (32, 60), (8, 46), (8, 18)
        ], fill=(0, 200, 255), outline=(255, 255, 255))
        
        dc.text((22, 18), "A", fill=(0, 0, 0))
        
        return image
            
    def _show_window(self):
        logger.info(f"Opening SATURDAY dashboard at {SATURDAY_URL}")
        try:
            webbrowser.open(SATURDAY_URL)
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")
        
    def _wake_saturday(self):
        
        logger.info("Wake SATURDAY triggered from tray")
        if self.saturday_core:
            self.saturday_core.event_bus.publish("wake_command", {})
                               
            try:
                self.saturday_core.speech.speak("SATURDAY is awake")
            except:
                pass
        
    def _start_voice(self):
        
        logger.info("Voice start triggered from tray")
        if self.saturday_core:
            self.saturday_core.event_bus.publish("voice_start", {})
                                   
            try:
                if hasattr(self.saturday_core.voice_id, 'start_listening'):
                    self.saturday_core.voice_id.start_listening()
            except Exception as e:
                logger.error(f"Failed to start voice: {e}")
        
    def _start_camera(self):
        
        logger.info("Camera start triggered from tray")
        if self.saturday_core:
            self.saturday_core.event_bus.publish("camera_start", {})
            self.saturday_core.camera_active = True
        
    def _toggle_security(self):
        
        if self.saturday_core:
            self.saturday_core.security_enabled = not self.saturday_core.security_enabled
            status = "enabled" if self.saturday_core.security_enabled else "disabled"
            logger.info(f"Security mode {status}")
            try:
                self.saturday_core.speech.speak(f"Security mode {status}")
            except:
                pass
        
    def _show_status(self):
        
        import psutil
        logger.info("Status check requested from tray")
        
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        
        status_msg = f"CPU: {cpu}% | Memory: {mem}% | Disk: {disk}%"
        
        if self.saturday_core:
            status_msg += f" | Security: {'ON' if self.saturday_core.security_enabled else 'OFF'}"
            status_msg += f" | Vision: {'ON' if self.saturday_core.vision_enabled else 'OFF'}"
            status_msg += f" | Voice: {'ON' if self.saturday_core.voice_enabled else 'OFF'}"
        
        logger.info(f"System Status: {status_msg}")
        
        try:
            self.saturday_core.speech.speak(f"System status: {status_msg}")
        except:
            pass
        
    def _view_logs(self):
        log_path = os.path.abspath("logs")
        logger.info(f"Opening logs folder: {log_path}")
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(["open", log_path])
            elif sys.platform == 'win32':
                os.startfile(log_path)
            else:
                subprocess.Popen(["xdg-open", log_path])
        except:
            webbrowser.open(log_path)
        
    def _restart_saturday(self):
        
        logger.info("Restart triggered from tray")
        if self.saturday_core:
            try:
                self.saturday_core.speak("Restarting SATURDAY systems")
            except:
                pass
            self.saturday_core.event_bus.publish("restart_command", {})
        
    def _quit(self):
        
        logger.info("Quit requested from system tray")
        self.running = False
        if self.tray:
            try:
                self.tray.stop()
            except:
                pass
        if self.saturday_core:
            self.saturday_core.running = False
            
    def stop(self):
        
        self._quit()
        if self._tray_thread and self._tray_thread.is_alive():
            self._tray_thread.join(timeout=2)
        logger.info("System tray stopped")

def create_system_tray(saturday_core=None):
    
    return SystemTray(saturday_core)
