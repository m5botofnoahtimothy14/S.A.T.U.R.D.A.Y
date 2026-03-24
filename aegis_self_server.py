#!/usr/bin/env python3
"""
AEGIS Self-Owned Server
=======================
Completely self-hosted AEGIS server - no third party APIs required.
Runs 24/7 with auto-restart and remote access.
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
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

os.chdir(BASE_DIR)

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

LOG_DIR = BASE_DIR / "logs" / "server"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "aegis_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AEGIS.Server")

class AEGISServer:
    def __init__(self):
        self.process = None
        self.running = False
        self.restart_count = 0
        self.max_restarts = 100
        self.restart_delay = 5
        
    def get_local_ip(self):
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def get_public_ip(self):
        """Get public IP (optional - uses local methods only)"""
        try:
            import urllib.request
            return urllib.request.urlopen('http://checkip.dyndns.org', timeout=5).read().decode().split(': ')[1].split('<')[0]
        except:
            return "Not available"
    
    def check_port(self, port):
        """Check if port is available"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    
    def start_aegis(self):
        """Start AEGIS core"""
        logger.info("Starting AEGIS Core...")
        
        cmd = [
            sys.executable,
            str(BASE_DIR / "run_production.py"),
            "--mode", "standalone"
        ]
        
        self.process = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        )
        
        logger.info(f"AEGIS Core started with PID: {self.process.pid}")
        return True
    
    def stop_aegis(self):
        """Stop AEGIS core"""
        if self.process:
            logger.info("Stopping AEGIS Core...")
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            logger.info("AEGIS Core stopped")
    
    def monitor_loop(self):
        """Monitor AEGIS and restart if needed"""
        while self.running:
            if self.process:
                retcode = self.process.poll()
                if retcode is not None:
                    logger.warning(f"AEGIS Core exited with code: {retcode}")
                    
                    if self.restart_count < self.max_restarts:
                        self.restart_count += 1
                        logger.info(f"Restarting AEGIS... (attempt {self.restart_count})")
                        time.sleep(self.restart_delay)
                        self.start_aegis()
                    else:
                        logger.error("Max restarts reached. Stopping server.")
                        self.running = False
                else:
                    time.sleep(5)
            else:
                time.sleep(1)
    
    def run(self):
        """Run the AEGIS server"""
        local_ip = self.get_local_ip()
        
        logger.info("="*50)
        logger.info("AEGIS SELF-OWNED SERVER STARTING")
        logger.info("="*50)
        logger.info(f"Local IP: {local_ip}")
        logger.info(f"Port: 8000")
        logger.info(f"Access URL: http://{local_ip}:8000")
        logger.info("="*50)
        
        self.running = True
        
        self.start_aegis()
        
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal")
            self.running = False
            self.stop_aegis()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_aegis()

if __name__ == "__main__":
    server = AEGISServer()
    server.run()
