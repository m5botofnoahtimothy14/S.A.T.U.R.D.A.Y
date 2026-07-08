try:
    import pyautogui
except (ImportError, Exception):
    pyautogui = None

class EmbodiedScreenNav:
    def move_cursor(self, x, y):
        if pyautogui:
            pyautogui.moveTo(x, y)

    def click(self):
        if pyautogui:
            pyautogui.click()
