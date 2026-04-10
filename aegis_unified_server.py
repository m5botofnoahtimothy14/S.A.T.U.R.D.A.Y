#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
import signal
import subprocess
import time
import socket
import threading
import json
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import ssl
import firebase_admin
from firebase_admin import credentials, firestore
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")
LOG_DIR = BASE_DIR / "logs" / "unified"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "unified.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AEGIS.Unified")
AEGIS_PORT = 8000
CONTROL_PORT = 8001
class AEGISUnifiedServer:
    def __init__(self):
        self.running = True
        self.aegis_process = None
        self.aegis_start_time = 0
        self.server_info = {
            "status": "starting",
            "aegis_online": False,
            "uptime": 0,
            "local_ip": "",
            "start_time": time.time()
        }
        self.node_id = os.getenv("AEGIS_NODE_ID", "aegis-primary")
        self._init_firebase()
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    def check_aegis(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', AEGIS_PORT))
            sock.close()
            return result == 0
        except:
            return False
    def start_aegis(self):
        if self.aegis_process and self.aegis_process.poll() is None:
            return True
        if self.aegis_start_time > 0 and time.time() - self.aegis_start_time < 60:
            return False
        logger.info("Starting AEGIS Core...")
        cmd = [sys.executable, str(BASE_DIR / "run_production.py"), "--mode", "standalone"]
        self.aegis_process = subprocess.Popen(
            cmd, cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        )
        self.aegis_start_time = time.time()
        logger.info(f"AEGIS started with PID: {self.aegis_process.pid}")
        return True
    def _init_firebase(self):
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app(options={"projectId": os.getenv("FIREBASE_PROJECT_ID")})
            self.db = firestore.client()
            logger.info("Unified Server: Firebase initialized.")
        except Exception as e:
            logger.error(f"Unified Server: Firebase failed: {e}")
            self.db = None
    def start_cloud_watcher(self):
        if not self.db: return
        def on_snapshot(doc_snapshot, changes, read_time):
            for doc in doc_snapshot:
                data = doc.to_dict()
                if data.get("command") == "wake" and data.get("status") == "pending":
                    logger.info("REMOTE CLOUD WAKE DETECTED!")
                    self.start_aegis()
                    doc.reference.update({"status": "executed", "woken_at": time.time()})
        self.db.collection("telemetry_nodes").document(self.node_id).collection("remote_commands").where("command", "==", "wake").on_snapshot(on_snapshot)
        logger.info("Unified Server: Cloud Watcher active.")
    def proxy_to_aegis(self, path, method="GET", body=None):
        import http.client
        try:
            conn = http.client.HTTPConnection("127.0.0.1", AEGIS_PORT, timeout=10)
            headers = {"Content-Type": "application/json"}
            if body:
                conn.request(method, path, body, headers)
            else:
                conn.request(method, path)
            response = conn.getresponse()
            data = response.read()
            conn.close()
            return response.status, data.decode('utf-8', errors='ignore')
        except Exception as e:
            return 502, json.dumps({"error": str(e)})
    def get_control_panel_html(self):
        local_ip = self.server_info["local_ip"]
        aegis_status = "🟢 Online" if self.server_info["aegis_online"] else "🔴 Offline"
        uptime = int(time.time() - self.server_info["start_time"])
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AEGIS Control Panel</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
        }}
        .header {{
            background: rgba(0,212,255,0.1);
            border-bottom: 1px solid rgba(0,212,255,0.3);
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 28px;
        }}
        .status-badge {{
            background: rgba(0,255,0,0.2);
            border: 1px solid #00ff00;
            padding: 8px 20px;
            border-radius: 20px;
            color: #00ff00;
        }}
        .nav {{
            background: rgba(255,255,255,0.05);
            padding: 15px 40px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .nav button {{
            background: rgba(0,212,255,0.1);
            border: 1px solid rgba(0,212,255,0.3);
            color: #00d4ff;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .nav button:hover {{
            background: rgba(0,212,255,0.2);
            border-color: #00d4ff;
        }}
        .content {{
            padding: 40px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .panel {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
        }}
        .panel h2 {{
            color: #00d4ff;
            margin-bottom: 20px;
            font-size: 24px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .info-box {{
            background: rgba(0,0,0,0.3);
            padding: 20px;
            border-radius: 10px;
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
        .url-box {{
            background: rgba(0,212,255,0.1);
            border: 1px solid #00d4ff;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }}
        .url-box a {{
            color: #00ff88;
            font-size: 18px;
            text-decoration: none;
        }}
        .api-section {{
            margin-top: 30px;
        }}
        .api-endpoint {{
            background: rgba(0,0,0,0.5);
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            font-family: monospace;
        }}
        .method {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            margin-right: 10px;
        }}
        .get {{ background: #00ff00; color: #000; }}
        .post {{ background: #00d4ff; color: #000; }}
        .delete {{ background: #ff4444; color: #fff; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⬡ AEGIS Control Panel</h1>
        <div class="status-badge">{aegis_status}</div>
    </div>
    <div class="nav">
        <button onclick="location.reload()">🔄 Refresh</button>
        <button onclick="fetch('/api/control/restart',{{method:'POST'}}).then(()=>location.reload())">♻️ Restart AEGIS</button>
        <button onclick="fetch('/api/control/wake/aegis',{{method:'POST'}}).then(r=>r.json()).then(d=>alert(d.message||JSON.stringify(d)))">⚡ Wake AEGIS</button>
        <button onclick="fetch('/api/vision/start',{{method:'POST'}}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">📷 Start Camera</button>
        <button onclick="fetch('/api/vision/stop',{{method:'POST'}}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">⏹ Stop Camera</button>
    </div>
    <div class="content">
        <div class="panel">
            <h2>📊 Server Status</h2>
            <div class="info-grid">
                <div class="info-box">
                    <div class="info-label">Uptime</div>
                    <div class="info-value">{hours}h {minutes}m</div>
                </div>
                <div class="info-box">
                    <div class="info-label">AEGIS Status</div>
                    <div class="info-value">{aegis_status}</div>
                </div>
                <div class="info-box">
                    <div class="info-label">Local IP</div>
                    <div class="info-value">{local_ip}</div>
                </div>
                <div class="info-box">
                    <div class="info-label">Control Panel</div>
                    <div class="info-value">:8001</div>
                </div>
            </div>
        </div>
        <div class="panel">
            <h2>🔗 Access Links</h2>
            <div class="url-box">
                <p style="color:#888;margin-bottom:10px;">AEGIS Core API:</p>
                <a href="http://{local_ip}:{AEGIS_PORT}">http://{local_ip}:{AEGIS_PORT}</a>
            </div>
            <div class="url-box">
                <p style="color:#888;margin-bottom:10px;">Control Panel (this page):</p>
                <a href="http://{local_ip}:{CONTROL_PORT}">http://{local_ip}:{CONTROL_PORT}</a>
            </div>
        </div>
        <div class="panel">
            <h2>🛠️ Quick API Endpoints</h2>
            <div class="api-section">
                <div class="api-endpoint">
                    <span class="method get">GET</span>
                    /api/status - System Status
                </div>
                <div class="api-endpoint">
                    <span class="method get">GET</span>
                    /api/health - Health Data
                </div>
                <div class="api-endpoint">
                    <span class="method post">POST</span>
                    /api/control/wake/aegis - Wake AEGIS
                </div>
                <div class="api-endpoint">
                    <span class="method post">POST</span>
                    /api/vision/start - Start Camera
                </div>
                <div class="api-endpoint">
                    <span class="method get">GET</span>
                    /api/face/list - List Faces
                </div>
                <div class="api-endpoint">
                    <span class="method post">POST</span>
                    /api/conversation/chat - Chat with AEGIS
                </div>
            </div>
        </div>
    </div>
    <script>
        // Auto-refresh status every 10 seconds
        setInterval(() => {{
            fetch('/api/server/status').then(r=>r.json()).then(d => {{
                if(d.aegis_online) {{
                    document.querySelector('.status-badge').textContent = '🟢 Online';
                    document.querySelector('.status-badge').style.background = 'rgba(0,255,0,0.2)';
                }} else {{
                    document.querySelector('.status-badge').textContent = '🔴 Offline';
                    document.querySelector('.status-badge').style.background = 'rgba(255,0,0,0.2)';
                }}
            }});
        }}, 10000);
    </script>
</body>
</html>'''
    def _send_cors(self, handler):
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    def handle_request(self, handler):
        path = handler.path.split('?')[0]
        method = handler.command
        if path == '/' or path == '/index.html':
            handler.send_response(200)
            handler.send_header('Content-type', 'text/html')
            self._send_cors(handler)
            handler.end_headers()
            handler.wfile.write(self.get_control_panel_html().encode())
            return
        if path == '/api/server/status':
            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            self._send_cors(handler)
            handler.end_headers()
            self.server_info["uptime"] = int(time.time() - self.server_info["start_time"])
            self.server_info["aegis_online"] = self.check_aegis()
            handler.wfile.write(json.dumps(self.server_info).encode())
            return
        if path.startswith('/api/') or path.startswith('/ws') or path.startswith('/vision') or path.startswith('/chat') or path.startswith('/tasks') or path.startswith('/status') or path.startswith('/health'):
            status, data = self.proxy_to_aegis(path, method)
            handler.send_response(status)
            handler.send_header('Content-type', 'application/json')
            self._send_cors(handler)
            handler.end_headers()
            handler.wfile.write(data.encode())
            return
        if path == '/api/control/restart' and method == 'POST':
            self.start_aegis()
            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "restarting"}).encode())
            return
        if path.startswith('/api/control/wake/'):
            target = path.split('/')[-1]
            _, data = self.proxy_to_aegis(f'/api/control/wake', 'POST', json.dumps({"target": target}))
            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(data.encode())
            return
        if path == '/api/vision/start' and method == 'POST':
            _, data = self.proxy_to_aegis('/api/camera/start', 'POST')
            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(data.encode())
            return
        if path == '/api/vision/stop' and method == 'POST':
            _, data = self.proxy_to_aegis('/api/camera/stop', 'POST')
            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(data.encode())
            return
        dist_path = BASE_DIR / "aegis-control-panel" / "dist"
        if dist_path.exists():
            full_path = dist_path / path.lstrip('/')
            if full_path.is_file():
                handler.send_response(200)
                content_type = 'text/html'
                if path.endswith('.js'): content_type = 'application/javascript'
                elif path.endswith('.css'): content_type = 'text/css'
                elif path.endswith('.png'): content_type = 'image/png'
                handler.send_header('Content-type', content_type)
                handler.end_headers()
                with open(full_path, 'rb') as f:
                    handler.wfile.write(f.read())
                return
            elif (dist_path / "index.html").exists():
                handler.send_response(200)
                handler.send_header('Content-type', 'text/html')
                handler.end_headers()
                with open(dist_path / "index.html", 'rb') as f:
                    handler.wfile.write(f.read())
                return
        handler.send_response(404)
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": "Not found"}).encode())
    def start_server(self):
        class RequestHandler(SimpleHTTPRequestHandler):
            def do_GET(self):
                self.server.handle_request(self)
            def do_POST(self):
                self.server.handle_request(self)
            def do_PUT(self):
                self.server.handle_request(self)
            def do_DELETE(self):
                self.server.handle_request(self)
            def do_OPTIONS(self):
                self.send_response(200)
                self.end_headers()
        RequestHandler.server = self
        server = HTTPServer(('', CONTROL_PORT), RequestHandler)
        logger.info(f"Unified server running on port {CONTROL_PORT}")
        logger.info(f"Control Panel: http://{self.server_info['local_ip']}:{CONTROL_PORT}")
        logger.info(f"AEGIS API: http://{self.server_info['local_ip']}:{AEGIS_PORT}")
        original_do_OPTIONS = RequestHandler.do_OPTIONS
        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.end_headers()
        RequestHandler.do_OPTIONS = do_OPTIONS
        server.serve_forever()
    def monitor_loop(self):
        while self.running:
            self.server_info["aegis_online"] = self.check_aegis()
            if not self.server_info["aegis_online"]:
                logger.warning("AEGIS offline, starting...")
                self.start_aegis()
                time.sleep(5)
            time.sleep(10)
    def run(self):
        self.server_info["local_ip"] = self.get_local_ip()
        logger.info("="*60)
        logger.info("AEGIS UNIFIED SERVER STARTING")
        logger.info("="*60)
        logger.info(f"Local IP: {self.server_info['local_ip']}")
        logger.info(f"Control Panel: http://{self.server_info['local_ip']}:{CONTROL_PORT}")
        logger.info(f"AEGIS API: http://{self.server_info['local_ip']}:{AEGIS_PORT}")
        logger.info("="*60)
        self.start_aegis()
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        self.start_cloud_watcher()
        self.start_server()
if __name__ == "__main__":
    server = AEGISUnifiedServer()
    server.run()
