                               
import pyautogui

class EmbodiedScreenNav:
    def move_cursor(self, x, y):
        pyautogui.moveTo(x, y)

    def click(self):
        pyautogui.click()
