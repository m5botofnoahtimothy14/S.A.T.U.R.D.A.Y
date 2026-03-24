# whatsapp_navigator.py

import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time


class WhatsAppNavigator:

    def __init__(self):
        self.driver = None

    def start(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)
        self.driver.get("https://web.whatsapp.com")
        print("Scan QR code to continue...")
        time.sleep(15)

    def open_chat(self, contact_name):
        search_box = self.driver.find_element(By.XPATH, "//div[@title='Search input textbox']")
        search_box.click()
        search_box.send_keys(contact_name)
        time.sleep(2)
        search_box.send_keys(Keys.ENTER)

    async def send_message(self, message):
        await asyncio.sleep(1)

        message_box = self.driver.find_element(By.XPATH, "//div[@title='Type a message']")
        message_box.send_keys(message)
        message_box.send_keys(Keys.ENTER)
