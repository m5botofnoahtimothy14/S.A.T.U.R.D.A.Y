                                 
import asyncio
import logging
import structlog
import threading
import time
from typing import Dict, Optional, Callable
from pathlib import Path
from core.event_bus import EventBus

logger = structlog.get_logger("SATURDAY.SocialManager")

class SocialManager:
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.drivers = {}
        self.running = False
        self.threads = {}
        
        self.platforms = {
            "whatsapp": {
                "url": "https://web.whatsapp.com",
                "title": "WhatsApp"
            },
            "instagram": {
                "url": "https://www.instagram.com",
                "title": "Instagram"
            },
            "twitter": {
                "url": "https://twitter.com/home",
                "title": "X"
            }
        }
        
        self.auto_reply_rules = {}
        self.event_bus.subscribe("social_send", self.handle_send_message)
        self.event_bus.subscribe("social_reply", self.handle_auto_reply)
        
    def start_platform(self, platform: str) -> bool:
        
        if platform not in self.platforms:
            logger.warning(f"Unknown platform: {platform}")
            return False
            
        if platform in self.drivers and self.drivers[platform]:
            logger.info(f"{platform} already running")
            return True
            
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            driver = webdriver.Chrome(options=options)
            driver.get(self.platforms[platform]["url"])
            
            self.drivers[platform] = driver
            logger.info(f"Started {platform} in background")
            
            self.event_bus.publish("voice_response", f"{platform.capitalize()} is now running in background.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start {platform}: {e}")
            return False
    
    def stop_platform(self, platform: str):
        
        if platform in self.drivers and self.drivers[platform]:
            try:
                self.drivers[platform].quit()
            except:
                pass
            self.drivers[platform] = None
            logger.info(f"Stopped {platform}")
    
    def stop_all(self):
        
        for platform in list(self.drivers.keys()):
            self.stop_platform(platform)
    
    def is_running(self, platform: str) -> bool:
        
        return platform in self.drivers and self.drivers[platform] is not None
    
    def get_status(self) -> Dict:
        
        return {
            platform: {
                "running": self.is_running(platform),
                "url": config["url"]
            }
            for platform, config in self.platforms.items()
        }
    
    def handle_send_message(self, data: dict):
        
        platform = data.get("platform")
        recipient = data.get("recipient")
        message = data.get("message")
        
        if platform == "whatsapp":
            self._send_whatsapp(recipient, message)
        elif platform == "instagram":
            self._send_instagram(recipient, message)
        elif platform == "twitter":
            self._send_tweet(message)
    
    def _send_whatsapp(self, contact: str, message: str):
        
        try:
            driver = self.drivers.get("whatsapp")
            if not driver:
                logger.warning("WhatsApp not running")
                return False
                
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            import time
            
            search_box = driver.find_element(By.XPATH, "//div[@title='Search input textbox']")
            search_box.click()
            search_box.send_keys(contact)
            time.sleep(2)
            search_box.send_keys(Keys.ENTER)
            time.sleep(1)
            
            msg_box = driver.find_element(By.XPATH, "//div[@title='Type a message']")
            msg_box.click()
            msg_box.send_keys(message)
            msg_box.send_keys(Keys.ENTER)
            
            logger.info(f"Sent WhatsApp message to {contact}")
            return True
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            return False
    
    def _send_instagram(self, recipient: str, message: str):
        
        try:
            driver = self.drivers.get("instagram")
            if not driver:
                logger.warning("Instagram not running")
                return False
                
            from selenium.webdriver.common.by import By
            import time
            
            driver.get(f"https://www.instagram.com/direct/t/{recipient}")
            time.sleep(3)
            
            msg_box = driver.find_element(By.XPATH, "//textarea")
            msg_box.send_keys(message)
            msg_box.send_keys(Keys.ENTER)
            
            logger.info(f"Sent Instagram DM to {recipient}")
            return True
        except Exception as e:
            logger.error(f"Instagram send failed: {e}")
            return False
    
    def _send_tweet(self, message: str):
        
        try:
            driver = self.drivers.get("twitter")
            if not driver:
                logger.warning("Twitter not running")
                return False
                
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            import time
            
            tweet_box = driver.find_element(By.XPATH, "//div[@data-testid='tweetTextarea']")
            tweet_box.click()
            tweet_box.send_keys(message)
            time.sleep(1)
            
            driver.find_element(By.XPATH, "//div[@data-testid='tweetButton']").click()
            
            logger.info(f"Sent tweet: {message[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Tweet failed: {e}")
            return False
    
    def handle_auto_reply(self, data: dict):
        
        platform = data.get("platform")
        rules = data.get("rules", {})
        
        self.auto_reply_rules[platform] = rules
        logger.info(f"Auto-reply enabled for {platform}: {rules}")
        
        if platform == "whatsapp":
            self._start_whatsapp_monitor()
    
    def _start_whatsapp_monitor(self):
        
        def monitor():
            while self.is_running("whatsapp"):
                try:
                    driver = self.drivers.get("whatsapp")
                    if not driver:
                        break
                        
                    from selenium.webdriver.common.by import By
                    import time
                    
                    unread = driver.find_elements(By.XPATH, "//span[@aria-label='Unread']")
                    
                    for msg in unread[:3]:
                        try:
                            msg.click()
                            time.sleep(1)
                            
                            last_msg = driver.find_elements(By.XPATH, "//div[@class='_a9-- _a9_0']")[-1]
                            text = last_msg.text
                            
                            if text in self.auto_reply_rules.get("whatsapp", {}):
                                reply = self.auto_reply_rules["whatsapp"][text]
                                self._send_whatsapp(None, reply)
                                
                        except:
                            continue
                            
                except Exception as e:
                    logger.debug(f"WhatsApp monitor: {e}")
                    
                time.sleep(5)
        
        if "whatsapp" not in self.threads or not self.threads["whatsapp"].is_alive():
            t = threading.Thread(target=monitor, daemon=True)
            t.start()
            self.threads["whatsapp"] = t
    
    def get_unread_messages(self, platform: str) -> list:
        
        try:
            driver = self.drivers.get(platform)
            if not driver:
                return []
                
            if platform == "whatsapp":
                from selenium.webdriver.common.by import By
                import time
                
                driver.get("https://web.whatsapp.com")
                time.sleep(2)
                
                unread = driver.find_elements(By.XPATH, "//span[@aria-label='Unread']")
                return [f"{unread[i].text} unread" for i in range(min(len(unread), 5))]
                
        except Exception as e:
            logger.debug(f"Get unread failed: {e}")
            
        return []
    
    def check_notifications(self) -> Dict:
        
        notifications = {}
        
        for platform in self.platforms:
            if self.is_running(platform):
                try:
                    unread = self.get_unread_messages(platform)
                    if unread:
                        notifications[platform] = unread
                except:
                    pass
        
        return notifications
