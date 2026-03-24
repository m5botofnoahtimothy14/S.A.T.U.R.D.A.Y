# communication/screen_navigator.py
import logging
import asyncio
import os
from typing import Optional

try:
    import pyautogui
    pyautogui.FAILSAFE = True
except ImportError:
    pyautogui = None

try:
    import win32gui
except ImportError:
    win32gui = None

logger = logging.getLogger("AEGIS.Screen")

class ScreenNavigator:
    """Handles autonomous screen interaction and app management."""
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.active = True
        
        if not pyautogui:
            logger.warning("pyautogui not installed. Screen navigation DISABLED.")
            
        logger.info("Screen Navigator initialized.")

    async def open_app(self, app_name: str):
        """Attempts to open an application using Windows search."""
        if not pyautogui: return
        
        logger.info(f"Navigating screen to open: {app_name}")
        pyautogui.press('win')
        await asyncio.sleep(0.5)
        pyautogui.write(app_name, interval=0.1)
        await asyncio.sleep(0.5)
        pyautogui.press('enter')
        
    async def play_music_autonomous(self):
        """Autonomous action to play music."""
        logger.info("Autonomous action: Playing music.")
        # Try to open Spotify or YouTube
        await self.open_app("spotify")
        await asyncio.sleep(3)
        pyautogui.press('space') # Play/Pause toggle

    async def search_on_screen(self, query: str):
        """Autonomous screen search."""
        if not pyautogui: return
        logger.info(f"Searching on screen for: {query}")
        pyautogui.hotkey('ctrl', 't') # Assume a browser is open
        await asyncio.sleep(0.5)
        pyautogui.write(query)
        pyautogui.press('enter')

    def check_screen_status(self):
        """Return the active foreground window when available."""
        foreground = "unknown"
        if win32gui:
            try:
                hwnd = win32gui.GetForegroundWindow()
                foreground = win32gui.GetWindowText(hwnd) or "unknown"
            except Exception as e:
                logger.debug("Foreground window lookup failed: %s", e)
        return {"status": "active", "foreground": foreground}
