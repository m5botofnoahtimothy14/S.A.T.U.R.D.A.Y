# hybrid/edith/social_handler.py
"""
EDITH Social Media Handler
Controls WhatsApp, Instagram, X (Twitter) - handles messages, DMs, uploads, replies
"""
import logging
import structlog
import threading
import time
from core.event_bus import EventBus

logger = structlog.get_logger("AEGIS.EDITH.Social")

class EdithSocialHandler:
    """
    EDITH's social media control center.
    Manages WhatsApp, Instagram, X (Twitter) through voice commands
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.social_manager = None
        self.auto_reply_enabled = {}
        self.last_check = {}
        
        self.event_bus.subscribe("voice_command", self._handle_command)
        self.event_bus.subscribe("edith_social_start", self._start_platform)
        self.event_bus.subscribe("edith_social_stop", self._stop_platform)
        
        self._init_social_manager()
        self._start_monitoring()
        
    def _init_social_manager(self):
        """Initialize social manager"""
        try:
            from communication.social_manager import SocialManager
            self.social_manager = SocialManager(self.event_bus)
            logger.info("EDITH Social Manager initialized")
        except Exception as e:
            logger.warning(f"Social manager not available: {e}")
    
    def _handle_command(self, command: str):
        """Handle voice commands for social media"""
        command = command.lower()
        
        if not any(x in command for x in ["whatsapp", "instagram", "twitter", "tweet", "x", "social", "message", "dm"]):
            return
            
        if "start" in command and "whatsapp" in command:
            self._start_platform("whatsapp")
        elif "start" in command and "instagram" in command:
            self._start_platform("instagram")
        elif "start" in command and ("twitter" in command or "tweet" in command or " x " in command):
            self._start_platform("twitter")
        elif "start" in command and "social" in command:
            self._start_all()
            
        elif "stop" in command and "whatsapp" in command:
            self._stop_platform("whatsapp")
        elif "stop" in command and "instagram" in command:
            self._stop_platform("instagram")
        elif "stop" in command and "twitter" in command:
            self._stop_platform("twitter")
            
        elif "send message" in command or "send whatsapp" in command:
            self._parse_send_message(command)
        elif "send tweet" in command or "post tweet" in command:
            self._parse_send_tweet(command)
            
        elif "check" in command or "unread" in command or "notifications" in command:
            self._check_notifications()
            
        elif "auto reply" in command or "autoreply" in command:
            self._enable_auto_reply(command)
            
        elif "status" in command and ("whatsapp" in command or "instagram" in command or "twitter" in command):
            self._get_status()
    
    def _start_platform(self, platform: str):
        """Start a social platform"""
        if not self.social_manager:
            self.event_bus.publish("voice_response", "Social manager not available.")
            return
            
        if isinstance(platform, dict):
            platform = platform.get("platform", "whatsapp")
            
        success = self.social_manager.start_platform(platform)
        if success:
            self.event_bus.publish("voice_response", f"{platform.capitalize()} is now active, Sir.")
        else:
            self.event_bus.publish("voice_response", f"Failed to start {platform}.")
    
    def _stop_platform(self, platform: str):
        """Stop a social platform"""
        if not self.social_manager:
            return
            
        if isinstance(platform, dict):
            platform = platform.get("platform", "whatsapp")
            
        self.social_manager.stop_platform(platform)
        self.event_bus.publish("voice_response", f"{platform.capitalize()} stopped.")
    
    def _start_all(self):
        """Start all social platforms"""
        for platform in ["whatsapp", "instagram", "twitter"]:
            if self.social_manager:
                self.social_manager.start_platform(platform)
        self.event_bus.publish("voice_response", "All social platforms active, Sir.")
    
    def _parse_send_message(self, command: str):
        """Parse and send message from voice command"""
        if not self.social_manager:
            self.event_bus.publish("voice_response", "Social manager not available.")
            return
            
        parts = command.replace("send message to ", "").replace("send whatsapp message to ", "")
        parts = parts.split(" say ")
        
        if len(parts) == 2:
            recipient = parts[0].strip()
            message = parts[1].strip()
            
            self.social_manager._send_whatsapp(recipient, message)
            self.event_bus.publish("voice_response", f"Message sent to {recipient}.")
        else:
            self.event_bus.publish("voice_response", "Specify recipient and message.")
    
    def _parse_send_tweet(self, command: str):
        """Parse and send tweet from voice command"""
        if not self.social_manager:
            self.event_bus.publish("voice_response", "Social manager not available.")
            return
            
        tweet = command.replace("send tweet", "").replace("post tweet", "").replace("tweet", "").strip()
        
        if tweet:
            self.social_manager._send_tweet(tweet)
            self.event_bus.publish("voice_response", f"Tweet posted, Sir: {tweet[:50]}...")
        else:
            self.event_bus.publish("voice_response", "What should I tweet?")
    
    def _check_notifications(self):
        """Check for notifications across all platforms"""
        if not self.social_manager:
            self.event_bus.publish("voice_response", "Social manager not available.")
            return
            
        notifications = self.social_manager.check_notifications()
        
        if notifications:
            for platform, msgs in notifications.items():
                self.event_bus.publish("voice_response", f"{platform.capitalize()}: {len(msgs)} new messages.")
        else:
            self.event_bus.publish("voice_response", "No new notifications, Sir.")
    
    def _enable_auto_reply(self, command: str):
        """Enable auto-reply for specific triggers"""
        rules = {}
        
        if "whatsapp" in command:
            rules = {
                "hello": "Hi! This is EDITH. Noah is currently unavailable. I'll pass along your message.",
                "hi": "Hello! EDITH here. Leave a message.",
                "where": "Noah is currently at location. I'll notify him of your inquiry.",
            }
            self.auto_reply_enabled["whatsapp"] = rules
            self.social_manager.handle_auto_reply({"platform": "whatsapp", "rules": rules})
            self.event_bus.publish("voice_response", "WhatsApp auto-reply enabled, Sir.")
        
        elif "instagram" in command:
            self.event_bus.publish("voice_response", "Instagram auto-reply configured.")
            
        elif "twitter" in command:
            self.event_bus.publish("voice_response", "Twitter auto-reply configured.")
    
    def _get_status(self):
        """Get status of all platforms"""
        if not self.social_manager:
            return
            
        status = self.social_manager.get_status()
        for platform, info in status.items():
            if info["running"]:
                self.event_bus.publish("voice_response", f"{platform.capitalize()} is active.")
            else:
                self.event_bus.publish("voice_response", f"{platform.capitalize()} is offline.")
    
    def _start_monitoring(self):
        """Start background monitoring thread"""
        def monitor():
            while True:
                try:
                    if self.social_manager:
                        notifications = self.social_manager.check_notifications()
                        if notifications:
                            for platform, msgs in notifications.items():
                                self.event_bus.publish("voice_response", f"New {platform} messages: {len(msgs)}")
                                self.last_check[platform] = time.time()
                except:
                    pass
                time.sleep(30)
        
        t = threading.Thread(target=monitor, daemon=True)
        t.start()
    
    def upload_to_instagram(self, image_path: str, caption: str = ""):
        """Upload image to Instagram"""
        if not self.social_manager:
            return False
            
        try:
            driver = self.social_manager.drivers.get("instagram")
            if not driver:
                return False
                
            from selenium.webdriver.common.by import By
            import time
            
            driver.get("https://www.instagram.com/")
            time.sleep(3)
            
            create_btn = driver.find_element(By.XPATH, "//svg[@aria-label='New post']")
            create_btn.click()
            time.sleep(2)
            
            file_input = driver.find_element(By.XPATH, "//input[@type='file']")
            file_input.send_keys(image_path)
            time.sleep(3)
            
            driver.find_element(By.XPATH, "//button[contains(text(),'Share')]").click()
            time.sleep(2)
            
            if caption:
                caption_box = driver.find_element(By.XPATH, "//textarea[@aria-label='Write a caption...']")
                caption_box.send_keys(caption)
                
            driver.find_element(By.XPATH, "//button[contains(text(),'Share')]").click()
            
            logger.info(f"Posted to Instagram: {caption[:30]}...")
            return True
        except Exception as e:
            logger.error(f"Instagram upload failed: {e}")
            return False
    
    def handle_dm_request(self, platform: str, recipient: str, message: str):
        """Handle DM request"""
        if not self.social_manager:
            return False
            
        if platform == "whatsapp":
            return self.social_manager._send_whatsapp(recipient, message)
        elif platform == "instagram":
            return self.social_manager._send_instagram(recipient, message)
        return False
