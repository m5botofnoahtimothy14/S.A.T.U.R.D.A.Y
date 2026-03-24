"""
MusicManager
------------
Mood-based playlist suggester/launcher + local VLC playback.
"""
import logging
import subprocess
import os
from urllib.parse import quote_plus
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.Services.MusicManager")

class MusicManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe("voice_command", self._on_voice_command)
        self.event_bus.subscribe("music_play", self._on_music_play)
        self.event_bus.subscribe("music_stop", self._on_music_stop)
        
        self.vlc_process = None
        self.playlists = {
            "happy": [
                "https://open.spotify.com/playlist/37i9dQZF1DXdPec7aLTmlC",
                "https://youtu.be/fLexgOxsZu0"
            ],
            "focus": [
                "https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO",
                "https://youtu.be/jfKfPfyJRdk"
            ],
            "chill": [
                "https://open.spotify.com/playlist/37i9dQZF1DX4WYpdgoIcn6",
                "https://youtu.be/21qNCS8WU"
            ],
            "sleep": [
                "https://open.spotify.com/playlist/37i9dQZF1DWZd79rJ6a7lp",
                "https://youtu.be/1ZYbU82GVz4"
            ],
            "workout": [
                "https://open.spotify.com/playlist/37i9dQZF1DX76Wlfdnj7AP",
                "https://youtu.be/aJOTlE1K90k"
            ],
            "sad": [
                "https://open.spotify.com/playlist/37i9dQZF1DX3YSRoSdA634",
                "https://youtu.be/d-diB65scQU"
            ],
        }
        
        self.local_music_path = "D:/Music"
        self.provider = os.getenv("AEGIS_MUSIC_PROVIDER", "youtube").strip().lower()
        logger.info("MusicManager ready with mood playlists.")

    def _on_voice_command(self, text: str):
        if not text:
            return
        lower = text.lower()

        if "music" not in lower and "play" not in lower:
            return

        action = "pause" if ("pause music" in lower or "stop music" in lower) else "play"
        result = self.play_request(lower, action=action)
        message = self._result_message(result)
        if message:
            self.event_bus.publish("voice_response", message)

    def _on_music_play(self, data: dict):
        url = data.get("url")
        if url:
            self._open_url(url)

    def _on_music_stop(self, data: dict = None):
        self._stop_playback()

    def play_request(self, query: str = "", action: str = "play") -> dict:
        action = (action or "play").strip().lower()
        query = (query or "").strip()
        lower = query.lower()

        if action in {"pause", "stop"}:
            self.stop()
            return {"status": "stopped", "action": action}

        if action in {"skip", "next", "previous"}:
            return {
                "status": "unavailable",
                "action": action,
                "reason": "Next or previous track control requires a controllable player session.",
            }

        if "local" in lower or "my music" in lower or "play from" in lower:
            return self._play_local_music()

        mood = self._detect_mood(lower)
        if mood:
            urls = self.playlists.get(mood, [])
            url = urls[0] if urls else None
            if not url:
                return {"status": "unavailable", "action": action, "reason": f"No playlist configured for mood '{mood}'."}
            self.event_bus.publish("music_playlist", {"mood": mood, "tracks": urls})
            self._open_url(url)
            return {"status": "playing", "action": action, "mood": mood, "url": url}

        if not query:
            return {"status": "unavailable", "action": action, "reason": "No music query was provided."}

        url = self._build_search_url(query)
        self._open_url(url)
        return {"status": "playing", "action": action, "query": query, "url": url, "provider": self.provider}

    def stop(self) -> dict:
        self._stop_playback()
        return {"status": "stopped", "action": "stop"}

    def _result_message(self, result: dict) -> str:
        status = result.get("status")
        if status == "playing" and result.get("mood"):
            return f"Playing the {result['mood']} playlist."
        if status == "playing" and result.get("query"):
            return f"Opening music for {result['query']}."
        if status == "playing":
            return "Playing music."
        if status == "stopped":
            return "Music stopped."
        return result.get("reason", "Music action unavailable.")

    def _build_search_url(self, query: str) -> str:
        encoded = quote_plus(query)
        if self.provider == "spotify":
            return f"https://open.spotify.com/search/{encoded}"
        return f"https://www.youtube.com/results?search_query={encoded}"

    def _open_url(self, url: str):
        if not url:
            return
        try:
            if os.name == 'nt':
                subprocess.Popen(["cmd", "/c", "start", "", url], shell=True)
            else:
                subprocess.Popen(["xdg-open", url])
            logger.info(f"Opened: {url}")
        except Exception as e:
            logger.warning(f"Could not open playlist: {e}")

    def _play_local_music(self):
        music_dir = self.local_music_path
        if not os.path.exists(music_dir):
            return {"status": "unavailable", "reason": f"Music folder not found: {music_dir}"}
            
        music_files = [f for f in os.listdir(music_dir) if f.endswith(('.mp3', '.wav', '.m4a', '.flac'))]
        if not music_files:
            return {"status": "unavailable", "reason": "No music files found in the local music folder."}
            
        path = os.path.join(music_dir, music_files[0])
        self._play_vlc(path)
        return {"status": "playing", "action": "play", "path": path}

    def _play_vlc(self, filepath: str):
        self._stop_playback()
        
        vlc_paths = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]
        
        vlc_exe = None
        for p in vlc_paths:
            if os.path.exists(p):
                vlc_exe = p
                break
        
        if not vlc_exe:
            logger.warning("VLC not found, using default handler")
            self._open_url(filepath)
            return
            
        try:
            self.vlc_process = subprocess.Popen(
                [vlc_exe, "--play-and-pause", filepath],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.event_bus.publish("voice_response", "Playing local music.")
            logger.info(f"Playing: {filepath}")
        except Exception as e:
            logger.warning(f"VLC playback failed: {e}")
            self._open_url(filepath)

    def _stop_playback(self):
        if self.vlc_process:
            try:
                self.vlc_process.terminate()
                self.vlc_process = None
            except:
                pass
        try:
            subprocess.Popen(["taskkill", "/F", "/IM", "vlc.exe"], 
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

    def _detect_mood(self, text: str):
        mapping = {
            "happy": ["happy", "upbeat", "joy", "party", "cheerful"],
            "focus": ["focus", "study", "deep work", "concentrate"],
            "chill": ["chill", "lofi", "relax", "calm", "ambient"],
            "sleep": ["sleep", "bed", "relax to sleep", "night", "lullaby"],
            "workout": ["workout", "gym", "run", "energy", "pump", "exercise"],
            "sad": ["sad", "blue", "down", "depressed", "melancholy"],
        }
        for mood, keywords in mapping.items():
            if any(k in text for k in keywords):
                return mood
        return None
