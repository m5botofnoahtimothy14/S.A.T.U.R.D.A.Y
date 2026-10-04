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
logger = logging.getLogger("SATURDAY.Unified")
SATURDAY_PORT = 8000
CONTROL_PORT = 8001
class SATURDAYUnifiedServer:
    def __init__(self):
        self.running = True
        self.saturday_process = None
        self.saturday_start_time = 0
        self.server_info = {
            "status": "starting",
            "saturday_online": False,
            "uptime": 0,
            "local_ip": "",
            "start_time": time.time()
        }
        self.node_id = os.getenv("SATURDAY_NODE_ID", "saturday-primary")
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
    def check_saturday(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', SATURDAY_PORT))
            sock.close()
            return result == 0
        except:
            return False
    def start_saturday(self):
        if self.saturday_process and self.saturday_process.poll() is None:
            return True
        if self.saturday_start_time > 0 and time.time() - self.saturday_start_time < 60:
            return False
        logger.info("Starting SATURDAY Core...")
        cmd = [sys.executable, str(BASE_DIR / "run_production.py"), "--mode", "standalone"]
        self.saturday_process = subprocess.Popen(
            cmd, cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        )
        self.saturday_start_time = time.time()
        logger.info(f"SATURDAY started with PID: {self.saturday_process.pid}")
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
                    self.start_saturday()
                    doc.reference.update({"status": "executed", "woken_at": time.time()})
        self.db.collection("telemetry_nodes").document(self.node_id).collection("remote_commands").where("command", "==", "wake").on_snapshot(on_snapshot)
        logger.info("Unified Server: Cloud Watcher active.")
    def proxy_to_saturday(self, path, method="GET", body=None):
        import http.client
        try:
            conn = http.client.HTTPConnection("127.0.0.1", SATURDAY_PORT, timeout=10)
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
        saturday_status = "🟢 ONLINE" if self.server_info["saturday_online"] else "🔴 OFFLINE"
        uptime = int(time.time() - self.server_info["start_time"])
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>S.A.T.U.R.D.A.Y // LOCALHOST CONTROL PLANE</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Orbitron:wght@600;800;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Rajdhani', -apple-system, sans-serif;
            background: #030712;
            color: #e2f1f8;
            min-height: 100vh;
            overflow-x: hidden;
        }}
        .grid-bg {{
            position: fixed; inset: 0; z-index: 0; pointer-events: none;
            background-image: radial-gradient(rgba(0, 242, 254, 0.08) 1px, transparent 0);
            background-size: 30px 30px;
        }}
        .header {{
            position: relative; z-index: 10;
            background: rgba(3, 7, 18, 0.85);
            backdrop-filter: blur(16px);
            border-bottom: 1px solid rgba(0, 242, 254, 0.3);
            padding: 18px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{
            font-family: 'Orbitron', sans-serif;
            background: linear-gradient(90deg, #00f2fe, #9d4edd);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 24px;
            letter-spacing: 4px;
        }}
        .badges {{ display: flex; align-items: center; gap: 12px; }}
        .sub-tag {{
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid #10b981;
            padding: 6px 16px;
            border-radius: 20px;
            color: #10b981;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            font-weight: 700;
            box-shadow: 0 0 15px rgba(16,185,129,0.2);
        }}
        .status-badge {{
            background: rgba(0, 242, 254, 0.1);
            border: 1px solid #00f2fe;
            padding: 6px 16px;
            border-radius: 20px;
            color: #00f2fe;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 700;
        }}
        .nav {{
            position: relative; z-index: 10;
            background: rgba(13, 22, 38, 0.6);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(0, 242, 254, 0.15);
            padding: 12px 40px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .nav button {{
            background: rgba(0, 242, 254, 0.08);
            border: 1px solid rgba(0, 242, 254, 0.3);
            color: #00f2fe;
            padding: 8px 18px;
            border-radius: 8px;
            cursor: pointer;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.3s;
        }}
        .nav button:hover {{
            background: rgba(0, 242, 254, 0.2);
            box-shadow: 0 0 15px rgba(0, 242, 254, 0.4);
            transform: translateY(-1px);
        }}
        .content {{
            position: relative; z-index: 10;
            padding: 30px 40px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .panel {{
            background: rgba(13, 22, 38, 0.75);
            backdrop-filter: blur(14px);
            border: 1px solid rgba(0, 242, 254, 0.25);
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }}
        .panel h2 {{
            font-family: 'Orbitron', sans-serif;
            color: #00f2fe;
            margin-bottom: 16px;
            font-size: 16px;
            letter-spacing: 2px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
        }}
        .info-box {{
            background: rgba(2, 6, 14, 0.8);
            border: 1px solid rgba(0, 242, 254, 0.15);
            padding: 16px;
            border-radius: 10px;
        }}
        .info-label {{
            color: #64748b;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .info-value {{
            font-size: 22px;
            font-weight: 700;
            color: #00f2fe;
            margin-top: 6px;
            font-family: 'Rajdhani', sans-serif;
        }}
        .url-box {{
            background: rgba(0, 242, 254, 0.05);
            border: 1px solid rgba(0, 242, 254, 0.3);
            padding: 16px;
            border-radius: 10px;
            margin: 12px 0;
            display: flex; justify-content: space-between; align-items: center;
        }}
        .url-box a {{
            color: #10b981;
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            text-decoration: none;
            font-weight: 600;
        }}
        .url-box a:hover {{ text-decoration: underline; }}
        .api-section {{ margin-top: 16px; }}
        .api-endpoint {{
            background: rgba(2, 6, 14, 0.8);
            border: 1px solid rgba(0, 242, 254, 0.15);
            padding: 12px 16px;
            border-radius: 8px;
            margin: 8px 0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            display: flex; align-items: center; justify-content: space-between;
        }}
        .method {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            margin-right: 12px;
        }}
        .get {{ background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }}
        .post {{ background: rgba(0, 242, 254, 0.2); color: #00f2fe; border: 1px solid #00f2fe; }}
        .cmd-box {{
            display: flex; gap: 10px; margin-top: 10px;
        }}
        .cmd-input {{
            flex: 1; padding: 10px 14px; background: rgba(2, 6, 14, 0.9); border: 1px solid rgba(0, 242, 254, 0.3);
            border-radius: 8px; color: #fff; font-family: 'JetBrains Mono', monospace; font-size: 13px;
        }}
        .cmd-out {{
            height: 120px; overflow-y: auto; background: rgba(2, 6, 14, 0.95); border: 1px solid rgba(0, 242, 254, 0.2);
            border-radius: 8px; padding: 12px; font-family: 'JetBrains Mono', monospace; font-size: 12px;
            margin-top: 10px; color: #10b981; white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="grid-bg"></div>
    <div class="header">
        <h1>⬡ S.A.T.U.R.D.A.Y CONTROL PLANE</h1>
        <div class="badges">
            <div class="sub-tag">★ PRO SUBSCRIBED</div>
            <div class="status-badge">{saturday_status}</div>
        </div>
    </div>
    <div class="nav">
        <button onclick="location.reload()">🔄 REFRESH</button>
        <button onclick="fetch('/api/control/restart',{{method:'POST'}}).then(()=>location.reload())">♻️ RESTART CORE</button>
        <button onclick="fetch('/api/control/wake/saturday',{{method:'POST'}}).then(r=>r.json()).then(d=>alert(d.message||JSON.stringify(d)))">⚡ WAKE CORE</button>
        <button onclick="fetch('/api/vision/start',{{method:'POST'}}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">📷 START CAMERA</button>
        <button onclick="fetch('/api/vision/stop',{{method:'POST'}}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">⏹ STOP CAMERA</button>
        <button onclick="window.open('http://{local_ip}:8099','_blank')">🌐 OPEN VERCEL HUD (8099)</button>
    </div>
    <div class="content">
        <div class="panel">
            <h2>📊 LOCALHOST SERVER TELEMETRY</h2>
            <div class="info-grid">
                <div class="info-box">
                    <div class="info-label">Server Uptime</div>
                    <div class="info-value">{hours}h {minutes}m</div>
                </div>
                <div class="info-box">
                    <div class="info-label">SATURDAY Core</div>
                    <div class="info-value">{saturday_status}</div>
                </div>
                <div class="info-box">
                    <div class="info-label">Network Host IP</div>
                    <div class="info-value">{local_ip}</div>
                </div>
                <div class="info-box">
                    <div class="info-label">Control Port</div>
                    <div class="info-value">:{CONTROL_PORT}</div>
                </div>
            </div>
        </div>

        <div class="panel">
            <h2>⚡ QUICK EXECUTE CONSOLE</h2>
            <div class="cmd-box">
                <input id="quickCmd" class="cmd-input" placeholder="Type status | wake | heal | sense | who | briefing..." value="status">
                <button class="nav" style="padding:10px 20px" onclick="runQuickCmd()">RUN COMMAND</button>
            </div>
            <div id="cmdOut" class="cmd-out">Ready for commands...</div>
        </div>

        <div class="panel">
            <h2>🔗 LOCALHOST & VERCEL ACCESS LINKS</h2>
            <div class="url-box">
                <div>
                    <p style="color:#64748b;font-size:12px;font-family:'JetBrains Mono';">SATURDAY Core API Port 8000:</p>
                    <a href="http://{local_ip}:{SATURDAY_PORT}" target="_blank">http://{local_ip}:{SATURDAY_PORT}</a>
                </div>
                <button onclick="window.open('http://{local_ip}:{SATURDAY_PORT}/api/status','_blank')">TEST API</button>
            </div>
            <div class="url-box">
                <div>
                    <p style="color:#64748b;font-size:12px;font-family:'JetBrains Mono';">Unified Control Panel Port 8001:</p>
                    <a href="http://{local_ip}:{CONTROL_PORT}" target="_blank">http://{local_ip}:{CONTROL_PORT}</a>
                </div>
                <button onclick="location.reload()">RELOAD</button>
            </div>
            <div class="url-box">
                <div>
                    <p style="color:#64748b;font-size:12px;font-family:'JetBrains Mono';">Vercel Web HUD Port 8099:</p>
                    <a href="http://{local_ip}:8099" target="_blank">http://{local_ip}:8099</a>
                </div>
                <button onclick="window.open('http://{local_ip}:8099','_blank')">OPEN HUD</button>
            </div>
        </div>

        <div class="panel">
            <h2>🛠️ SYSTEM API ENDPOINTS</h2>
            <div class="api-section">
                <div class="api-endpoint">
                    <span><span class="method get">GET</span> /api/status — Core & Subsystems Telemetry</span>
                    <button onclick="fetch('/api/status').then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">CALL</button>
                </div>
                <div class="api-endpoint">
                    <span><span class="method get">GET</span> /api/health — System Health & Memory Metrics</span>
                    <button onclick="fetch('/api/health').then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">CALL</button>
                </div>
                <div class="api-endpoint">
                    <span><span class="method post">POST</span> /api/control/wake/saturday — Wake SATURDAY Core</span>
                    <button onclick="fetch('/api/control/wake/saturday',{{method:'POST'}}).then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">CALL</button>
                </div>
                <div class="api-endpoint">
                    <span><span class="method post">POST</span> /api/vision/start — Start Vision Camera Feed</span>
                    <button onclick="fetch('/api/vision/start',{{method:'POST'}}).then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">CALL</button>
                </div>
                <div class="api-endpoint">
                    <span><span class="method get">GET</span> /api/tasks — Active Autonomous Tasks</span>
                    <button onclick="fetch('/api/tasks').then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">CALL</button>
                </div>
            </div>
        </div>
    </div>
    <script>
        function runQuickCmd() {{
            const c = document.getElementById('quickCmd').value.trim();
            if(!c) return;
            document.getElementById('cmdOut').textContent = "Executing: " + c + "...";
            fetch('/api/command', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{command: c}})
            }}).then(r=>r.json()).then(d => {{
                document.getElementById('cmdOut').textContent = d.response || JSON.stringify(d,null,2);
            }}).catch(e => {{
                document.getElementById('cmdOut').textContent = "Error: " + e;
            }});
        }}

        // Auto-refresh status every 10 seconds
        setInterval(() => {{
            fetch('/api/server/status').then(r=>r.json()).then(d => {{
                const sb = document.querySelector('.status-badge');
                if(d.saturday_online) {{
                    sb.textContent = '🟢 ONLINE';
                    sb.style.color = '#10b981';
                    sb.style.borderColor = '#10b981';
                }} else {{
                    sb.textContent = '🔴 OFFLINE';
                    sb.style.color = '#f43f5e';
                    sb.style.borderColor = '#f43f5e';
                }}
            }});
        }}, 8000);
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
            self.server_info["saturday_online"] = self.check_saturday()
            handler.wfile.write(json.dumps(self.server_info).encode())
            return
        if path.startswith('/api/') or path.startswith('/ws') or path.startswith('/vision') or path.startswith('/chat') or path.startswith('/tasks') or path.startswith('/status') or path.startswith('/health'):
            status, data = self.proxy_to_saturday(path, method)
            handler.send_response(status)
            handler.send_header('Content-type', 'application/json')
            self._send_cors(handler)
            handler.end_headers()
            handler.wfile.write(data.encode())
            return
        if path == '/api/control/restart' and method == 'POST':
            self.start_saturday()
            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "restarting"}).encode())
            return
        if path.startswith('/api/control/wake/'):
            target = path.split('/')[-1]
            _, data = self.proxy_to_saturday(f'/api/control/wake', 'POST', json.dumps({"target": target}))
            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(data.encode())
            return
        if path == '/api/vision/start' and method == 'POST':
            _, data = self.proxy_to_saturday('/api/camera/start', 'POST')
            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(data.encode())
            return
        if path == '/api/vision/stop' and method == 'POST':
            _, data = self.proxy_to_saturday('/api/camera/stop', 'POST')
            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(data.encode())
            return
        dist_path = BASE_DIR / "saturday-control-panel" / "dist"
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
        logger.info(f"SATURDAY API: http://{self.server_info['local_ip']}:{SATURDAY_PORT}")
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
            self.server_info["saturday_online"] = self.check_saturday()
            if not self.server_info["saturday_online"]:
                logger.warning("SATURDAY offline, starting...")
                self.start_saturday()
                time.sleep(5)
            time.sleep(10)
    def run(self):
        self.server_info["local_ip"] = self.get_local_ip()
        logger.info("="*60)
        logger.info("SATURDAY UNIFIED SERVER STARTING")
        logger.info("="*60)
        logger.info(f"Local IP: {self.server_info['local_ip']}")
        logger.info(f"Control Panel: http://{self.server_info['local_ip']}:{CONTROL_PORT}")
        logger.info(f"SATURDAY API: http://{self.server_info['local_ip']}:{SATURDAY_PORT}")
        logger.info("="*60)
        self.start_saturday()
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        self.start_cloud_watcher()
        self.start_server()
if __name__ == "__main__":
    server = SATURDAYUnifiedServer()
    server.run()
