# ui/screen_navigation.py
import pyautogui
import time
import logging

logger = logging.getLogger("AEGIS.ScreenNav")
logger.setLevel(logging.INFO)

class ScreenNavigator:
    def __init__(self):
        pyautogui.FAILSAFE = True

    def open_app(self, app_name):
        """Open applications by name (Windows only)"""
        try:
            pyautogui.press('win')
            time.sleep(0.5)
            pyautogui.typewrite(app_name)
            pyautogui.press('enter')
            logger.info(f"Opened app: {app_name}")
        except Exception as e:
            logger.error(f"Failed to open {app_name}: {e}")

    def click_position(self, x, y):
        """Click at screen coordinates"""
        pyautogui.click(x, y)
        logger.info(f"Clicked at ({x},{y})")

    def type_text(self, text):
        """Type text anywhere"""
        pyautogui.typewrite(text)
        logger.info(f"Typed text: {text}")

    def send_message_whatsapp(self, contact, message):
        """IRL send WhatsApp message by navigating screen"""
        self.open_app("WhatsApp")
        time.sleep(3)
        pyautogui.hotkey('ctrl', 'f')
        pyautogui.typewrite(contact)
        pyautogui.press('enter')
        time.sleep(1)
        self.type_text(message)
        pyautogui.press('enter')
        logger.info(f"Sent WhatsApp message to {contact}")
