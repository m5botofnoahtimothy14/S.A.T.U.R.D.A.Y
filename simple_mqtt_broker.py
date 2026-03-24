#!/usr/bin/env python3
"""
Simple MQTT Broker for HomeBot
"""

import asyncio
import socket
import threading
import json
from collections import defaultdict

class SimpleMQTTBroker:
    def __init__(self, host='0.0.0.0', port=1883):
        self.host = host
        self.port = port
        self.clients = {}
        self.subscriptions = defaultdict(set)
        self.running = False
        self.server_socket = None
        
    async def start(self):
        """Start the MQTT broker"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"[MQTT] Broker started on {self.host}:{self.port}")
        
        # Accept connections in a separate thread
        threading.Thread(target=self._accept_connections, daemon=True).start()
        
    def _accept_connections(self):
        """Accept client connections"""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                print(f"[MQTT] Client connected: {addr}")
                
                # Handle client in separate thread
                threading.Thread(target=self._handle_client, args=(client_socket, addr), daemon=True).start()
                
            except Exception as e:
                if self.running:
                    print(f"[MQTT] Accept error: {e}")
                    
    def _handle_client(self, client_socket, addr):
        """Handle individual client"""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                    
                # Simple MQTT packet handling
                self._process_packet(client_socket, data, addr)
                
        except Exception as e:
            print(f"[MQTT] Client {addr} error: {e}")
        finally:
            client_socket.close()
            print(f"[MQTT] Client {addr} disconnected")
            
    def _process_packet(self, client_socket, data, addr):
        """Process MQTT packets (simplified)"""
        try:
            # Very simple MQTT implementation
            # Just handle basic PUBLISH messages
            if data.startswith(b'\x30'):  # PUBLISH packet
                # Extract topic and payload (simplified)
                parts = data[2:].split(b'\x00', 2)
                if len(parts) >= 2:
                    topic = parts[0].decode()
                    payload = parts[1].decode()
                    
                    print(f"[MQTT] PUBLISH {topic}: {payload}")
                    
                    # Forward to subscribed clients
                    self._forward_message(topic, payload, addr)
                    
        except Exception as e:
            print(f"[MQTT] Packet processing error: {e}")
            
    def _forward_message(self, topic, payload, sender_addr):
        """Forward message to subscribed clients"""
        # Simple topic matching
        for subscribed_topic in self.subscriptions:
            if self._topic_matches(topic, subscribed_topic):
                for client_addr in self.subscriptions[subscribed_topic]:
                    if client_addr != sender_addr:  # Don't send back to sender
                        # In a real implementation, we'd send to actual client sockets
                        print(f"[MQTT] Forward {topic} to {client_addr}")
                        
    def _topic_matches(self, topic, pattern):
        """Simple topic matching"""
        if pattern.endswith('#'):
            return topic.startswith(pattern[:-1])
        elif '+' in pattern:
            parts = pattern.split('+')
            topic_parts = topic.split('/')
            if len(parts) == len(topic_parts):
                return all(p == '+' or p == t for p, t in zip(parts, topic_parts))
        return topic == pattern
        
    def stop(self):
        """Stop the broker"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("[MQTT] Broker stopped")

def start_broker():
    """Start the MQTT broker"""
    broker = SimpleMQTTBroker()
    
    try:
        asyncio.run(broker.start())
    except KeyboardInterrupt:
        print("\n[MQTT] Shutting down...")
        broker.stop()

if __name__ == "__main__":
    print("[MQTT] Starting Simple MQTT Broker for HomeBot...")
    start_broker()
