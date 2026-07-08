import asyncio

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
except ImportError:
    webdriver = None

import time

class InstaNavigator:

    def __init__(self):
        self.driver = None

    def start(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)
        self.driver.get("https://www.instagram.com")

    def login(self, username, password):
        time.sleep(5)
        inputs = self.driver.find_elements(By.TAG_NAME, "input")

        inputs[0].send_keys(username)
        inputs[1].send_keys(password)
        inputs[1].send_keys(Keys.ENTER)

        time.sleep(5)

    def open_dm(self, user):
        self.driver.get(f"https://www.instagram.com/{user}/")
        time.sleep(3)

        try:
            message_button = self.driver.find_element(By.XPATH, "//div[text()='Message']")
            message_button.click()
        except:
            print("[InstaNavigator] Could not find Message button.")

    async def send_message(self, message):
        await asyncio.sleep(2)

        try:
            text_area = self.driver.find_element(By.TAG_NAME, "textarea")
            text_area.send_keys(message)
            text_area.send_keys(Keys.ENTER)
        except:
            print("[InstaNavigator] Failed to send message.")
