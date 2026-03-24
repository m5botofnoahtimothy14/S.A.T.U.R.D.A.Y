#!/usr/bin/env python3
"""
Start AEGIS Production with all services
"""

import subprocess
import time
import threading
import signal
import sys
import os

class AEGISProduction:
    def __init__(self):
        self.processes = {}
        self.running = True
        
    def start_mqtt_broker(self):
        """Start MQTT broker for HomeBot"""
        print("[AEGIS] Starting MQTT Broker...")
        try:
            process = subprocess.Popen([
                sys.executable, 'simple_mqtt_broker.py'
            ], cwd=os.path.dirname(__file__))
            self.processes['mqtt'] = process
            print("✅ MQTT Broker started (PID: {})".format(process.pid))
            return True
        except Exception as e:
            print(f"❌ MQTT Broker failed: {e}")
            return False
    
    def start_aegis_server(self):
        """Start AEGIS main server"""
        print("[AEGIS] Starting AEGIS Server...")
        try:
            process = subprocess.Popen([
                r'.\.venv\Scripts\python.exe', r'd:\AEGIS\Core\main.py'
            ], cwd=os.path.dirname(__file__))
            self.processes['aegis'] = process
            print("✅ AEGIS Server started (PID: {})".format(process.pid))
            return True
        except Exception as e:
            print(f"❌ AEGIS Server failed: {e}")
            return False
    
    def start_cloudflare_tunnel(self):
        """Start Cloudflare tunnel for external access"""
        print("[AEGIS] Starting Cloudflare Tunnel...")
        try:
            process = subprocess.Popen([
                'cloudflared.exe', 'tunnel', '--url', 'https://localhost:8000'
            ], cwd=os.path.dirname(__file__))
            self.processes['tunnel'] = process
            print("✅ Cloudflare Tunnel started (PID: {})".format(process.pid))
            return True
        except Exception as e:
            print(f"❌ Cloudflare Tunnel failed: {e}")
            return False
    
    def monitor_processes(self):
        """Monitor all processes"""
        while self.running:
            for name, process in list(self.processes.items()):
                if process.poll() is not None:
                    print(f"⚠️ Process {name} stopped (exit code: {process.poll()})")
                    del self.processes[name]
                    
                    # Restart critical processes
                    if name == 'mqtt':
                        print("🔄 Restarting MQTT Broker...")
                        self.start_mqtt_broker()
                    elif name == 'aegis':
                        print("🔄 Restarting AEGIS Server...")
                        self.start_aegis_server()
            
            time.sleep(5)
    
    def stop_all(self):
        """Stop all processes"""
        print("\n[AEGIS] Shutting down...")
        self.running = False
        
        for name, process in self.processes.items():
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ {name} stopped")
            except:
                try:
                    process.kill()
                    print(f"🔥 {name} killed")
                except:
                    print(f"❌ Failed to stop {name}")
    
    def start(self):
        """Start all AEGIS production services"""
        print("🚀 Starting AEGIS Production Environment")
        print("=" * 50)
        
        # Start services in order
        services = [
            ("MQTT Broker", self.start_mqtt_broker),
            ("AEGIS Server", self.start_aegis_server),
            ("Cloudflare Tunnel", self.start_cloudflare_tunnel),
        ]
        
        started = []
        for name, start_func in services:
            if start_func():
                started.append(name)
                time.sleep(2)  # Give each service time to start
            else:
                print(f"❌ Failed to start {name}")
        
        print(f"\n✅ Started services: {', '.join(started)}")
        
        # Show access information
        print("\n🌐 Access Information:")
        print("   Local:   https://localhost:8000")
        print("   Network: https://192.168.0.180:8000")
        
        # Check if tunnel is running
        if 'tunnel' in self.processes:
            print("   External: Check Cloudflare tunnel output for URL")
        
        print("\n🔧 HomeBot Integration:")
        print("   MQTT Broker: localhost:1883")
        print("   COM4: Ready for HomeBot Core2")
        print("   Commands: 'homebot move forward', 'bot go to 5 10'")
        
        # Start monitoring
        monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
        monitor_thread.start()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, lambda s, f: self.stop_all())
        signal.signal(signal.SIGTERM, lambda s, f: self.stop_all())
        
        print("\n[CTRL+C] to stop all services")
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_all()

if __name__ == "__main__":
    aegis = AEGISProduction()
    aegis.start()
