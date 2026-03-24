# core/system_tray.py
import threading
import logging
import os
import sys
import webbrowser
import subprocess

logger = logging.getLogger("AEGIS.SystemTray")

AEGIS_URL = "http://localhost:8000"

class SystemTray:
    """System tray icon and menu for AEGIS"""
    
    def __init__(self, aegis_core=None):
        self.aegis_core = aegis_core
        self.tray = None
        self.running = False
        self._tray_thread = None
        
    def start(self):
        """Start system tray"""
        if self.running:
            logger.warning("System tray already running")
            return
            
        self.running = True
        self._tray_thread = threading.Thread(target=self._run_tray, daemon=True, name="AEGIS-SystemTray")
        self._tray_thread.start()
        logger.info("System tray started")
        
    def _run_tray(self):
        """Run system tray in background"""
        try:
            from pystray import Icon, Menu, MenuItem
            from PIL import Image, ImageDraw
        except ImportError as e:
            logger.error(f"pystray or PIL not available: {e}")
            self.running = False
            return
            
        # Create icon image
        icon_image = self._create_icon()
        
        # Define menu with proper callbacks
        menu = Menu(
            MenuItem("Open AEGIS Dashboard", self._show_window),
            Menu.SEPARATOR,
            MenuItem("Wake AEGIS", self._wake_aegis),
            MenuItem("Start Voice Recognition", self._start_voice),
            MenuItem("Start Camera", self._start_camera),
            MenuItem("Toggle Security Mode", self._toggle_security),
            Menu.SEPARATOR,
            MenuItem("System Status", self._show_status),
            MenuItem("View Logs", self._view_logs),
            Menu.SEPARATOR,
            MenuItem("Restart AEGIS", self._restart_aegis),
            MenuItem("Quit AEGIS", self._quit)
        )
        
        try:
            self.tray = Icon("AEGIS", icon_image, "AEGIS AI OS", menu)
            logger.info("System tray icon created, starting tray loop...")
            self.tray.run()
        except Exception as e:
            logger.error(f"Failed to run system tray: {e}")
            self.running = False
        
    def _create_icon(self):
        """Create AEGIS icon"""
        from PIL import Image, ImageDraw
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), 'black')
        dc = ImageDraw.Draw(image)
        
        # Draw hexagon shape (AEGIS logo)
        dc.polygon([
            (32, 4), (56, 18), (56, 46), (32, 60), (8, 46), (8, 18)
        ], fill=(0, 200, 255), outline=(255, 255, 255))
        
        # Draw "A" letter
        dc.text((22, 18), "A", fill=(0, 0, 0))
        
        return image
            
    def _show_window(self):
        """Show AEGIS dashboard in browser"""
        logger.info(f"Opening AEGIS dashboard at {AEGIS_URL}")
        try:
            # Try to open in existing browser
            webbrowser.open(AEGIS_URL)
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")
            # Fallback - try direct URL
            try:
                os.startfile(AEGIS_URL)
            except:
                pass
        
    def _wake_aegis(self):
        """Wake AEGIS"""
        logger.info("Wake AEGIS triggered from tray")
        if self.aegis_core:
            self.aegis_core.event_bus.publish("wake_command", {})
            # Also try to speak
            try:
                self.aegis_core.speech.speak("AEGIS is awake")
            except:
                pass
        
    def _start_voice(self):
        """Start voice recognition"""
        logger.info("Voice start triggered from tray")
        if self.aegis_core:
            self.aegis_core.event_bus.publish("voice_start", {})
            # Try to start voice ID
            try:
                if hasattr(self.aegis_core.voice_id, 'start_listening'):
                    self.aegis_core.voice_id.start_listening()
            except Exception as e:
                logger.error(f"Failed to start voice: {e}")
        
    def _start_camera(self):
        """Start camera"""
        logger.info("Camera start triggered from tray")
        if self.aegis_core:
            self.aegis_core.event_bus.publish("camera_start", {})
            self.aegis_core.camera_active = True
        
    def _toggle_security(self):
        """Toggle security mode"""
        if self.aegis_core:
            self.aegis_core.security_enabled = not self.aegis_core.security_enabled
            status = "enabled" if self.aegis_core.security_enabled else "disabled"
            logger.info(f"Security mode {status}")
            try:
                self.aegis_core.speech.speak(f"Security mode {status}")
            except:
                pass
        
    def _show_status(self):
        """Show system status"""
        import psutil
        logger.info("Status check requested from tray")
        
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage(os.getenv('SystemDrive', 'C:\\')).percent
        
        status_msg = f"CPU: {cpu}% | Memory: {mem}% | Disk: {disk}%"
        
        if self.aegis_core:
            status_msg += f" | Security: {'ON' if self.aegis_core.security_enabled else 'OFF'}"
            status_msg += f" | Vision: {'ON' if self.aegis_core.vision_enabled else 'OFF'}"
            status_msg += f" | Voice: {'ON' if self.aegis_core.voice_enabled else 'OFF'}"
        
        logger.info(f"System Status: {status_msg}")
        
        try:
            self.aegis_core.speech.speak(f"System status: {status_msg}")
        except:
            pass
        
    def _view_logs(self):
        """Open logs folder"""
        log_path = os.path.abspath("logs")
        logger.info(f"Opening logs folder: {log_path}")
        try:
            os.startfile(log_path)
        except:
            webbrowser.open(log_path)
        
    def _restart_aegis(self):
        """Restart AEGIS"""
        logger.info("Restart triggered from tray")
        if self.aegis_core:
            try:
                self.aegis_core.speak("Restarting AEGIS systems")
            except:
                pass
            self.aegis_core.event_bus.publish("restart_command", {})
        
    def _quit(self):
        """Quit AEGIS"""
        logger.info("Quit requested from system tray")
        self.running = False
        if self.tray:
            try:
                self.tray.stop()
            except:
                pass
        if self.aegis_core:
            self.aegis_core.running = False
            
    def stop(self):
        """Stop system tray"""
        self._quit()
        if self._tray_thread and self._tray_thread.is_alive():
            self._tray_thread.join(timeout=2)
        logger.info("System tray stopped")


def create_system_tray(aegis_core=None):
    """Factory function to create system tray"""
    return SystemTray(aegis_core)
