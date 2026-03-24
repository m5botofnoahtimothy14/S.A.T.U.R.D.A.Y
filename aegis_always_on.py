#!/usr/bin/env python3
"""
AEGIS Always-On Server
======================
Keeps AEGIS running 24/7 with instant access via Tailscale/Home Network.
Health monitoring + auto-restart + instant status page.
"""
import os
import sys
import asyncio
import logging
import signal
import subprocess
import time
import socket
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

os.chdir(BASE_DIR)

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

LOG_DIR = BASE_DIR / "logs" / "always_on"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "always_on.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AEGIS.AlwaysOn")

class AEGISAlwaysOnServer:
    def __init__(self):
        self.aegis_process = None
        self.running = True
        self.restart_count = 0
        self.max_restarts = 999999
        self.health_check_interval = 10
        self.port = 8000
        self.status_port = 8001
        
        self.server_info = {
            "status": "starting",
            "aegis_status": "offline",
            "uptime": 0,
            "restarts": 0,
            "last_check": None,
            "local_ip": "",
            "tailscale_ip": "",
            "health": "healthy"
        }
        self.start_time = time.time()
        
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def get_tailscale_ip(self):
        try:
            result = subprocess.run(
                ["tailscale", "ip", "-4"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        return None
    
    def check_aegis_health(self):
        """Check if AEGIS is responding"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', self.port))
            sock.close()
            return result == 0
        except:
            return False
    
    def start_aegis(self):
        """Start AEGIS core"""
        if self.aegis_process and self.aegis_process.poll() is None:
            return
            
        logger.info("Starting AEGIS Core...")
        
        cmd = [sys.executable, str(BASE_DIR / "run_production.py"), "--mode", "standalone"]
        
        self.aegis_process = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        )
        
        self.restart_count += 1
        self.server_info["restarts"] = self.restart_count
        logger.info(f"AEGIS started with PID: {self.aegis_process.pid}")
    
    def stop_aegis(self):
        """Stop AEGIS"""
        if self.aegis_process:
            try:
                self.aegis_process.terminate()
                self.aegis_process.wait(timeout=5)
            except:
                self.aegis_process.kill()
    
    def monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            self.server_info["uptime"] = int(time.time() - self.start_time)
            self.server_info["local_ip"] = self.get_local_ip()
            self.server_info["tailscale_ip"] = self.get_tailscale_ip()
            self.server_info["last_check"] = datetime.now().isoformat()
            
            # Check AEGIS health
            if self.check_aegis_health():
                self.server_info["aegis_status"] = "online"
                self.server_info["health"] = "healthy"
                self.server_info["status"] = "running"
            else:
                self.server_info["aegis_status"] = "offline"
                self.server_info["status"] = "starting"
                logger.warning("AEGIS not responding, starting...")
                self.start_aegis()
            
            time.sleep(self.health_check_interval)
    
    def get_status_html(self):
        """Generate status page HTML"""
        ip = self.server_info["local_ip"]
        ts_ip = self.server_info["tailscale_ip"]
        status = self.server_info["status"]
        aegis_status = self.server_info["aegis_status"]
        uptime = self.server_info["uptime"]
        restarts = self.server_info["restarts"]
        
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        
        status_color = "#00ff00" if aegis_status == "online" else "#ffaa00"
        
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AEGIS AI OS - Always On</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            text-align: center;
            padding: 40px;
            max-width: 800px;
        }}
        .logo {{
            font-size: 72px;
            margin-bottom: 20px;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.05); opacity: 0.8; }}
        }}
        h1 {{
            font-size: 48px;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .status {{
            font-size: 24px;
            padding: 15px 40px;
            border-radius: 30px;
            display: inline-block;
            margin: 20px 0;
            background: {status_color}22;
            border: 2px solid {status_color};
            color: {status_color};
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-top: 40px;
            text-align: left;
        }}
        .info-box {{
            background: rgba(255,255,255,0.05);
            padding: 20px;
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .info-label {{
            color: #888;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .info-value {{
            font-size: 24px;
            color: #00d4ff;
            margin-top: 5px;
        }}
        .access-url {{
            background: rgba(0,212,255,0.1);
            padding: 20px;
            border-radius: 15px;
            margin-top: 30px;
            border: 1px solid #00d4ff;
        }}
        .url {{
            font-size: 20px;
            color: #00ff88;
            word-break: break-all;
        }}
        .progress {{
            width: 100%;
            height: 4px;
            background: rgba(255,255,255,0.1);
            margin-top: 30px;
            border-radius: 2px;
            overflow: hidden;
        }}
        .progress-bar {{
            height: 100%;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            animation: loading 2s infinite;
        }}
        @keyframes loading {{
            0% {{ width: 0%; }}
            100% {{ width: 100%; }}
        }}
    </style>
    <meta http-equiv="refresh" content="5">
</head>
<body>
    <div class="container">
        <div class="logo">⬡</div>
        <h1>AEGIS AI OS</h1>
        <p style="color:#888;font-size:18px;">Always On • Always Ready</p>
        
        <div class="status">
            ● {status.upper()}
        </div>
        
        <div class="info-grid">
            <div class="info-box">
                <div class="info-label">Server Uptime</div>
                <div class="info-value">{hours}h {minutes}m</div>
            </div>
            <div class="info-box">
                <div class="info-label">AEGIS Status</div>
                <div class="info-value">{aegis_status.upper()}</div>
            </div>
            <div class="info-box">
                <div class="info-label">Restarts</div>
                <div class="info-value">{restarts}</div>
            </div>
            <div class="info-box">
                <div class="info-label">Health</div>
                <div class="info-value" style="color:#00ff00;">HEALTHY</div>
            </div>
        </div>
        
        <div class="access-url">
            <div class="info-label" style="margin-bottom:10px;">ACCESS AEGIS</div>
            <div class="url">http://{ip}:8000</div>
            {f'<div class="url" style="margin-top:10px;color:#00d4ff;">http://{ts_ip}:8000</div>' if ts_ip else ''}
        </div>
        
        <div class="progress">
            <div class="progress-bar"></div>
        </div>
        
        <p style="color:#666;margin-top:20px;font-size:12px;">
            AEGIS Self-Owned Server • 24/7 Online
        </p>
    </div>
</body>
</html>'''
    
    def status_server(self):
        """Simple HTTP server for status page"""
        class StatusHandler(SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/' or self.path == '/status':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(self.server.get_status_html().encode())
                elif self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    import json
                    self.wfile.write(json.dumps(self.server.server_info).encode())
                elif self.path == '/api':
                    # Proxy to AEGIS
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    import json
                    self.wfile.write(json.dumps({
                        "aegis": self.server.server_info["aegis_status"],
                        "proxy": "http://localhost:8000"
                    }).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                pass
        
        StatusHandler.server = self
        
        server = HTTPServer(('', self.status_port), StatusHandler)
        logger.info(f"Status server running on port {self.status_port}")
        server.serve_forever()
    
    def run(self):
        """Run the always-on server"""
        local_ip = self.get_local_ip()
        
        logger.info("="*60)
        logger.info("AEGIS ALWAYS-ON SERVER STARTING")
        logger.info("="*60)
        logger.info(f"Local IP: {local_ip}")
        logger.info(f"Status Page: http://{local_ip}:{self.status_port}")
        logger.info(f"AEGIS: http://{local_ip}:{self.port}")
        logger.info("="*60)
        
        self.running = True
        self.start_aegis()
        
        # Start status server in background
        status_thread = threading.Thread(target=self.status_server, daemon=True)
        status_thread.start()
        
        # Start monitor loop
        try:
            self.monitor_loop()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.running = False
            self.stop_aegis()

if __name__ == "__main__":
    server = AEGISAlwaysOnServer()
    server.run()
