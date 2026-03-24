# communication/oauth_manager.py
"""
OAuth2 Integration Manager for AEGIS
Supports: Google, GitHub (API-based)
Note: WhatsApp, Instagram, X - handled by EDITH browser automation (no API needed)
"""
import os
import json
import structlog
from pathlib import Path
from typing import Optional, Dict, Any
from core.event_bus import EventBus

logger = structlog.get_logger("AEGIS.OAuth")

class OAuthManager:
    """
    Manages OAuth2 authentication for API-based services.
    Browser-based services (WhatsApp, Instagram, X) handled by EDITH.
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        
        self.services = {
            "google": {
                "name": "Google (Calendar, Gmail, Drive)",
                "scopes": [
                    "https://www.googleapis.com/auth/calendar.readonly",
                    "https://www.googleapis.com/auth/gmail.readonly",
                    "https://www.googleapis.com/auth/drive.readonly"
                ],
                "credentials_file": "data/google_credentials.json",
                "token_file": "data/google_token.json"
            },
            "github": {
                "name": "GitHub",
                "scopes": ["user:email", "repo", "read:org"],
                "credentials_file": "data/github_credentials.json",
                "token_file": "data/github_token.json"
            }
        }
        
        self.tokens = {}
        self._load_tokens()
        
    def _load_tokens(self):
        for service, config in self.services.items():
            token_file = config.get("token_file")
            if token_file and os.path.exists(token_file):
                try:
                    with open(token_file) as f:
                        self.tokens[service] = json.load(f)
                except:
                    pass
    
    def is_connected(self, service: str) -> bool:
        return service in self.tokens and bool(self.tokens[service])
    
    def get_status(self) -> Dict[str, Any]:
        status = {}
        for service, config in self.services.items():
            status[service] = {
                "name": config["name"],
                "connected": self.is_connected(service),
                "needs_setup": not os.path.exists(config.get("credentials_file", ""))
            }
        status["whatsapp"] = {"name": "WhatsApp", "connected": "via EDITH", "needs_setup": False}
        status["instagram"] = {"name": "Instagram", "connected": "via EDITH", "needs_setup": False}
        status["twitter"] = {"name": "X (Twitter)", "connected": "via EDITH", "needs_setup": False}
        return status
    
    def get_auth_url(self, service: str) -> Optional[str]:
        config = self.services.get(service)
        if not config:
            return None
            
        if not os.path.exists(config.get("credentials_file", "")):
            return None
            
        try:
            creds = json.load(open(config["credentials_file"]))
            client_id = creds.get("client_id")
            
            if service == "google":
                from google_auth_oauthlib.flow import Flow
                flow = Flow.from_client_secrets_file(
                    config["credentials_file"], scopes=config["scopes"]
                )
                flow.redirect_uri = "http://localhost:8888/callback"
                auth_url, _ = flow.authorization_url(access_type='offline', prompt='consent')
                return auth_url
                
            elif service == "github":
                import urllib.parse
                params = {
                    "client_id": client_id,
                    "redirect_uri": "http://localhost:8888/callback",
                    "scope": " ".join(config["scopes"]),
                    "state": service
                }
                return f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
                
        except Exception as e:
            logger.error(f"Auth URL failed: {e}")
            return None
    
    def exchange_code(self, service: str, code: str) -> bool:
        config = self.services.get(service)
        if not config:
            return False
            
        try:
            creds = json.load(open(config["credentials_file"]))
            client_id = creds.get("client_id")
            client_secret = creds.get("client_secret", "")
            
            if service == "google":
                from google.oauth2.credentials import Credentials
                from google_auth_oauthlib.flow import Flow
                flow = Flow.from_client_secrets_file(
                    config["credentials_file"], scopes=config["scopes"]
                )
                flow.redirect_uri = "http://localhost:8888/callback"
                flow.fetch_token(code=code)
                token_data = {
                    "token": flow.credentials.token,
                    "refresh_token": flow.credentials.refresh_token,
                }
                with open(config["token_file"], 'w') as f:
                    json.dump(token_data, f)
                self.tokens[service] = token_data
                return True
                
            elif service == "github":
                import requests
                resp = requests.post("https://github.com/login/oauth/access_token", data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": "http://localhost:8888/callback"
                }, headers={"Accept": "application/json"})
                token_data = resp.json()
                with open(config["token_file"], 'w') as f:
                    json.dump(token_data, f)
                self.tokens[service] = token_data
                return True
                
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            
        return False
    
    def make_request(self, service: str, endpoint: str, method: str = "GET") -> Optional[Dict]:
        if not self.is_connected(service):
            return None
            
        token = self.tokens.get(service, {}).get("token")
        if not token:
            return None
            
        try:
            import requests
            
            if service == "google":
                resp = requests.get(f"https://www.googleapis.com/{endpoint}", 
                                  headers={"Authorization": f"Bearer {token}"})
                return resp.json() if resp.ok else None
                
            elif service == "github":
                resp = requests.get(f"https://api.github.com/{endpoint}",
                                  headers={"Authorization": f"Bearer {token}", 
                                         "Accept": "application/vnd.github.v3+json"})
                return resp.json() if resp.ok else None
                
        except:
            pass
        return None
