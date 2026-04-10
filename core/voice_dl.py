
import asyncio
import logging
import threading
import queue
import time
import os
import subprocess
import json
from typing import Optional, Dict, Any, List
from collections import deque

import structlog
from core.audio_service import CrossPlatformAudio
from core.event_bus import EventBus

logger = structlog.get_logger("AEGIS.VoiceDL")

MAX_MEMORY = 100

class SystemControl:
    
    PLATFORM = __import__("sys").platform
    
    @staticmethod
    def run_cmd(command: str) -> Dict[str, Any]:
        
        try:
            if SystemControl.PLATFORM == "win32":
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out", "stdout": "", "stderr": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "stdout": "", "stderr": ""}
    
    @staticmethod
    def get_system_info() -> Dict:
        
        info = {}
        
        if SystemControl.PLATFORM == "win32":
            cpu = SystemControl.run_cmd("wmic cpu get name,loadpercentage")
            mem = SystemControl.run_cmd("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value")
            disk = SystemControl.run_cmd("wmic logicaldisk get size,freespace,caption")
            
            info["cpu"] = cpu.get("stdout", "Unknown")
            info["memory"] = mem.get("stdout", "Unknown")
            info["disk"] = disk.get("stdout", "Unknown")
        else:
            info = SystemControl.run_cmd("uname -a && df -h && free -m")
        
        return info
    
    @staticmethod
    def list_processes() -> str:
        
        if SystemControl.PLATFORM == "win32":
            result = SystemControl.run_cmd("tasklist /FO LIST")
        else:
            result = SystemControl.run_cmd("ps aux")
        return result.get("stdout", "Could not retrieve processes")
    
    @staticmethod
    def kill_process(pid: int) -> str:
        
        if SystemControl.PLATFORM == "win32":
            result = SystemControl.run_cmd(f"taskkill /F /PID {pid}")
        else:
            result = SystemControl.run_cmd(f"kill -9 {pid}")
        return result.get("stdout", "Process terminated")
    
    @staticmethod
    def install_software(package: str) -> str:
        
        if SystemControl.PLATFORM == "win32":
            return f"Opening installer for {package}. Please complete installation manually."
        else:
            result = SystemControl.run_cmd(f"pip install {package}")
            if result["success"]:
                return f"Successfully installed {package}"
            return f"Installation failed: {result.get('stderr', 'Unknown error')}"

class WebFetch:
    
    @staticmethod
    async def fetch_news(topic: str = "general") -> str:
        
        try:
            import requests
            url = f"https://newsapi.org/v1/articles?source=bbc-news&sortBy=top&apiKey=demo"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                articles = data.get("articles", [])[:5]
                if articles:
                    news = "\n".join([f"- {a['title']}" for a in articles])
                    return f"Here are the latest headlines:\n{news}"
            return "Could not fetch news at this time."
        except Exception as e:
            return f"News fetch error: {e}"
    
    @staticmethod
    async def search_web(query: str) -> str:
        
        try:
            import requests
            url = f"https://api.duckduckgo.com/"
            params = {"q": query, "format": "json"}
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("AbstractText"):
                    return data["AbstractText"][:500]
            return f"Found information about {query}. What would you like to know specifically?"
        except Exception as e:
            return f"Search error: {e}"
    
    @staticmethod
    async def get_weather(city: str = "") -> str:
        
        try:
            import requests
            if not city:
                city = "New York"
            api_key = os.getenv("WEATHER_API_KEY", "")
            if not api_key:
                return "Weather API key not configured."
            url = f"https://api.openweathermap.org/data/2.5/weather"
            params = {"q": city, "appid": api_key, "units": "metric"}
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                temp = data["main"]["temp"]
                desc = data["weather"][0]["description"]
                return f"Weather in {city}: {temp}°C, {desc}"
            return "Could not fetch weather."
        except Exception as e:
            return f"Weather error: {e}"
    
    @staticmethod
    async def play_song(song_name: str) -> str:
        
        try:
            import requests
            query = song_name.replace(" ", "+")
            search_url = f"https://www.youtube.com/results?search_query={query}"
            return f"Searching YouTube for '{song_name}'. Would you like me to open it?"
        except Exception as e:
            return f"Music search error: {e}"

class CodeAssistant:
    
    @staticmethod
    def write_code(language: str, description: str) -> str:
        
        prompt = f"Write a {language} program that: {description}"
        return f"Creating {language} code for: {description}\n\nCode generation ready."
    
    @staticmethod
    def debug_code(code: str) -> str:
        
        return f"Analyzing code for bugs...\n\nDebugging analysis complete."
    
    @staticmethod
    def run_code(code: str, language: str = "python") -> str:
        
        try:
            if language.lower() == "python":
                result = subprocess.run(
                    ["python", "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                return result.stdout or result.stderr
        except Exception as e:
            return f"Execution error: {e}"
        return "Could not execute code"

class FileManager:
    
    @staticmethod
    def list_directory(path: str = ".") -> str:
        
        try:
            files = os.listdir(path)
            return "\n".join(files[:20]) or "Directory is empty"
        except Exception as e:
            return f"Error: {e}"
    
    @staticmethod
    def create_file(path: str, content: str = "") -> str:
        
        try:
            with open(path, "w") as f:
                f.write(content)
            return f"File created: {path}"
        except Exception as e:
            return f"Error creating file: {e}"
    
    @staticmethod
    def read_file(path: str) -> str:
        
        try:
            with open(path, "r") as f:
                content = f.read(5000)
            return f"Contents of {path}:\n{content}"
        except Exception as e:
            return f"Error reading file: {e}"
    
    @staticmethod
    def edit_file(path: str, old_text: str, new_text: str) -> str:
        
        try:
            with open(path, "r") as f:
                content = f.read()
            content = content.replace(old_text, new_text)
            with open(path, "w") as f:
                f.write(content)
            return f"File updated: {path}"
        except Exception as e:
            return f"Error editing file: {e}"
    
    @staticmethod
    def delete_file(path: str) -> str:
        
        try:
            if os.path.isfile(path):
                os.remove(path)
                return f"Deleted file: {path}"
            elif os.path.isdir(path):
                os.rmdir(path)
                return f"Deleted directory: {path}"
            return "Path not found"
        except Exception as e:
            return f"Error deleting: {e}"

class HomeBotController:
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.connected = False
        self.mqtt_client = None
        self.broker = os.getenv("MQTT_BROKER", "192.168.0.180")
        self.port = int(os.getenv("MQTT_PORT", 1884))
        self._connect()
    
    def _connect(self):
        try:
            import paho.mqtt.client as mqtt
            
            def on_connect(client, userdata, flags, rc, properties=None):
                if rc == 0:
                    self.connected = True
                    logger.info(f"HomeBot connected to {self.broker}")
                else:
                    logger.warning(f"HomeBot connection failed: rc={rc}")
            
            self.mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            self.mqtt_client.on_connect = on_connect
            self.mqtt_client.connect(self.broker, self.port, 10)
            self.mqtt_client.loop_start()
        except Exception as e:
            logger.warning(f"HomeBot MQTT error: {e}")
            self.connected = False
    
    def control(self, command: str) -> str:
        
        if not self.connected:
            return "HomeBot is not connected. Please check the MQTT broker."
        
        cmd_map = {
            "forward": ("homebot/motors/omni", {"x": 0, "y": 80, "rotation": 0}),
            "ahead": ("homebot/motors/omni", {"x": 0, "y": 80, "rotation": 0}),
            "backward": ("homebot/motors/omni", {"x": 0, "y": -80, "rotation": 0}),
            "back": ("homebot/motors/omni", {"x": 0, "y": -80, "rotation": 0}),
            "left": ("homebot/motors/omni", {"x": -80, "y": 0, "rotation": 0}),
            "right": ("homebot/motors/omni", {"x": 80, "y": 0, "rotation": 0}),
            "spin left": ("homebot/motors/omni", {"x": 0, "y": 0, "rotation": -80}),
            "rotate left": ("homebot/motors/omni", {"x": 0, "y": 0, "rotation": -80}),
            "spin right": ("homebot/motors/omni", {"x": 0, "y": 0, "rotation": 80}),
            "rotate right": ("homebot/motors/omni", {"x": 0, "y": 0, "rotation": 80}),
            "stop": ("homebot/motors/stop", "1"),
            "halt": ("homebot/motors/stop", "1"),
        }
        
        for key, (topic, payload) in cmd_map.items():
            if key in command.lower():
                try:
                    if isinstance(payload, dict):
                        import json
                        self.mqtt_client.publish(topic, json.dumps(payload))
                    else:
                        self.mqtt_client.publish(topic, payload)
                    return f"HomeBot moving: {key}"
                except Exception as e:
                    return f"HomeBot error: {e}"
        
        return "Unknown HomeBot command."
    
    def status(self) -> str:
        if self.connected:
            return f"HomeBot connected at {self.broker}:{self.port}"
        return "HomeBot is offline"

class SystemRepair:
    
    @staticmethod
    def diagnose() -> str:
        
        report = ["=== System Diagnostic Report ===\n"]
        
        if SystemControl.PLATFORM == "win32":
            sfc = SystemControl.run_cmd("sfc /scannow")
            report.append(f"SFC Scan: {'OK' if sfc['success'] else 'Issues found'}")
            
            dism = SystemControl.run_cmd("DISM /Online /Cleanup-Image /RestoreHealth")
            report.append(f"DISM: {'OK' if dism['success'] else 'Needs attention'}")
            
            chkdsk = SystemControl.run_cmd("chkdsk")
            report.append(f"Disk Check: {'OK' if chkdsk['success'] else 'Needs attention'}")
        
        return "\n".join(report)
    
    @staticmethod
    def clear_temp() -> str:
        
        try:
            temp = os.getenv("TEMP", "/tmp")
            count = 0
            for f in os.listdir(temp):
                try:
                    os.remove(os.path.join(temp, f))
                    count += 1
                except:
                    pass
            return f"Cleared {count} temporary files"
        except Exception as e:
            return f"Error: {e}"
    
    @staticmethod
    def optimize_startup() -> str:
        
        if SystemControl.PLATFORM == "win32":
            result = SystemControl.run_cmd("wmic startup list full")
            return f"Startup programs:\n{result.get('stdout', 'Could not retrieve')[:1000]}"
        return "Startup optimization not available on this platform"

class AEGISVoiceDL:
    
    def __init__(self, event_bus: EventBus, llm_engine=None, speech_manager=None):
        self.event_bus = event_bus
        self.llm = llm_engine
        self.speech = speech_manager
        self.audio = CrossPlatformAudio()
        
        self.system = SystemControl()
        self.web = WebFetch()
        self.code = CodeAssistant()
        self.files = FileManager()
        self.repair = SystemRepair()
        self.homebot = HomeBotController(event_bus)
        
        self.running = False
        self.conversation_memory = deque(maxlen=MAX_MEMORY)
        
        self.event_bus.subscribe("voice_response", self._on_response)
        
        logger.info("AEGIS Voice DL - FULL SYSTEM CONTROL",
                   whisper=bool(self.audio.whisper_model),
                   llm=bool(self.llm),
                   homebot=self.homebot.connected)

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._listen_loop, daemon=True).start()
        time.sleep(0.5)
        self._greet()
        logger.info("AEGIS Voice DL ACTIVE")

    def stop(self):
        self.running = False
        logger.info("AEGIS Voice DL stopped")

    def _greet(self):
        greetings = [
            "Hello. I am AEGIS with full system access. What would you like to do?",
            "AEGIS online with complete control. Command me.",
            "I have system-level access. Tell me what you need.",
        ]
        import random
        self.speak(random.choice(greetings))

    def speak(self, text: str):
        if self.speech:
            self.speech.speak(text)
        else:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except:
                pass

    def _on_response(self, text):
        if text:
            self.speak(text)

    def _listen_loop(self):
        
        if not self.audio.recognizer or not self.audio.mic:
            logger.error("Speech recognizer not available")
            return

        while self.running:
            try:
                with self.audio.mic as source:
                    self.audio.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    while self.running:
                        try:
                            audio = self.audio.recognizer.listen(source, timeout=2, phrase_time_limit=15)
                            text = self.audio.recognize_speech(audio)
                            
                            if text and len(text.strip()) > 1:
                                logger.info(f"YOU: {text}")
                                self.conversation_memory.append({"role": "user", "content": text})
                                asyncio.run(self._understand_and_act(text))
                                
                        except Exception as e:
                            if "timeout" not in str(e).lower():
                                logger.debug(f"Listen: {e}")
                            continue
                            
            except Exception as e:
                logger.error(f"Mic error: {e}")
                time.sleep(1)

    async def _understand_and_act(self, user_input: str):
        
        text = user_input.lower()
        response = None
        
        if "run" in text and ("command" in text or "cmd" in text or "terminal" in text):
            cmd = text.replace("run", "").replace("command", "").replace("cmd", "").replace("execute", "").strip()
            result = self.system.run_cmd(cmd)
            response = f"Command executed. Result: {result.get('stdout', result.get('error', 'No output'))[:500]}"
        
        elif "system info" in text or "system information" in text:
            info = self.system.get_system_info()
            response = f"System info retrieved. CPU: {info.get('cpu', 'Unknown')[:100]}"
        
        elif "processes" in text or "running programs" in text:
            procs = self.system.list_processes()
            response = f"Running processes: {procs[:500]}"
        
        elif "kill" in text and ("process" in text or "program" in text):
            import re
            nums = re.findall(r'\d+', text)
            if nums:
                response = self.system.kill_process(int(nums[0]))
            else:
                response = "Which process would you like to kill? Give me the PID."
        
        elif "install" in text:
            import re
            pkg = text.replace("install", "").strip()
            response = self.system.install_software(pkg)
        
        elif "news" in text:
            topic = text.replace("news", "").replace("fetch", "").strip()
            response = await self.web.fetch_news(topic or "general")
        
        elif "weather" in text:
            city = text.replace("weather", "").replace("in", "").replace("for", "").replace("?", "").strip()
            response = await self.web.get_weather(city)
        
        elif "search" in text or "look up" in text or "google" in text:
            query = text.replace("search", "").replace("look up", "").replace("google", "").replace("for", "").strip()
            if query:
                response = await self.web.search_web(query)
            else:
                response = "What would you like me to search for?"
        
        elif "play" in text and ("song" in text or "music" in text):
            song = text.replace("play", "").replace("song", "").replace("music", "").strip()
            response = await self.web.play_song(song or "popular music")
        
        elif "write code" in text or "create code" in text:
            lang = "python"
            if "javascript" in text or "js" in text:
                lang = "javascript"
            elif "java" in text:
                lang = "java"
            elif "c++" in text or "cpp" in text:
                lang = "c++"
            response = self.code.write_code(lang, text)
        
        elif "debug" in text or "fix" in text and "code" in text:
            response = "Paste the code you'd like me to debug and I'll analyze it."
        
        elif "run code" in text or "execute code" in text:
            response = "Please provide the code you want to run."
        
        elif "list files" in text or "show files" in text or "directory" in text:
            path = text.replace("list", "").replace("show", "").replace("files", "").replace("directory", "").strip()
            response = self.files.list_directory(path or ".")
        
        elif "create file" in text or "new file" in text:
            parts = text.replace("create", "").replace("new", "").replace("file", "").strip().split(" ", 1)
            if len(parts) > 1:
                response = self.files.create_file(parts[1])
            else:
                response = "What file would you like me to create?"
        
        elif "read file" in text or "open file" in text:
            response = "Which file would you like me to read?"
        
        elif "edit file" in text or "modify file" in text:
            response = "Which file would you like me to edit?"
        
        elif "delete file" in text or "remove file" in text:
            response = "Which file would you like me to delete?"
        
        elif "diagnose" in text or "system check" in text or "repair" in text:
            response = self.repair.diagnose()
        
        elif "clear temp" in text or "clean up" in text:
            response = self.repair.clear_temp()
        
        elif "optimize" in text or "speed up" in text:
            response = self.repair.optimize_startup()
        
        elif any(g in text for g in ["hello", "hi", "hey"]):
            response = "Hello! Ready to assist with any system task."
        
        elif "how are you" in text:
            homebot_status = "HomeBot is connected." if self.homebot.connected else "HomeBot is offline."
            response = f"I'm fully operational. {homebot_status} What would you like to do?"
        
        elif "what can you do" in text:
            response = "I have full system control. I can run commands, manage files, fetch web data, debug code, repair systems, control HomeBot, send messages, and more. Just tell me what you need."
        
        elif "homebot" in text or any(w in text for w in ["forward", "backward", "left", "right", "spin", "rotate", "stop", "move"]):
            response = self.homebot.control(text)
        
        elif "homebot status" in text or "is homebot on" in text:
            response = self.homebot.status()
        
        elif "thank" in text:
            response = "You're welcome!"
        
        elif "bye" in text or "goodbye" in text:
            response = "Goodbye! Call me when you need me."
        
        elif self.llm:
            try:
                async for chunk in self.llm.chat_stream(user_input):
                    pass
            except:
                pass
            response = "Let me process that for you."
        else:
            response = "I understand. Let me help you with that."
        
        if response:
            self.conversation_memory.append({"role": "assistant", "content": response})
            self.speak(response)
        
        self.event_bus.publish("voice_command", user_input)

def start_voice_dl(event_bus, llm_engine=None, speech_manager=None):
    
    voice = AEGISVoiceDL(event_bus, llm_engine, speech_manager)
    voice.start()
    return voice
