                      

import logging
import asyncio
import time
import json
import threading
import os
from core.event_bus import EventBus
logger = logging.getLogger("AEGIS.CloudBridge")
class CloudBridge:
    def __init__(self, event_bus: EventBus, project_id: str, node_id: str = "aegis-primary"):
        self.event_bus = event_bus
        self.project_id = project_id
        self.node_id = node_id
        self.service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT", "").strip()
        self.db = None
        self.running = False
        self._init_firebase()
        self.event_bus.subscribe("vitals_update", self._push_vitals)
        self.event_bus.subscribe("power_mode", self._push_status)
        self.event_bus.subscribe("voice_response", self._push_logs)
    def _init_firebase(self):
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            if not self.project_id:
                raise RuntimeError("FIREBASE_PROJECT_ID is required for CloudBridge.")
            if not self.service_account_path or not os.path.exists(self.service_account_path):
                raise RuntimeError("FIREBASE_SERVICE_ACCOUNT must point to a valid Firebase service account JSON file.")
            if not firebase_admin._apps:
                cred = credentials.Certificate(self.service_account_path)
                firebase_admin.initialize_app(cred, options={"projectId": self.project_id})
            self.db = firestore.client()
            self.node_ref = self.db.collection("telemetry_nodes").document(self.node_id)
            self.command_ref = self.node_ref.collection("remote_commands")
            logger.info(f"Cloud Bridge connected to Firebase: {self.project_id}")
        except Exception as e:
            logger.error(f"Cloud Bridge failed to initialize Firebase: {e}")
    def _push_vitals(self, data):
        if not self.db: return
        try:
            self.node_ref.set({"vitals": data, "last_seen": time.time()}, merge=True)
        except: pass
    def _push_status(self, data):
        if not self.db: return
        try:
            self.node_ref.set({"status": data, "last_seen": time.time()}, merge=True)
        except: pass
    def _push_logs(self, text):
        if not self.db: return
        try:
            log_entry = {
                "timestamp": time.time(),
                "text": str(text),
                "type": "ai_response"
            }
            self.node_ref.collection("logs").add(log_entry)
        except: pass
    async def _command_listener(self):
        if not self.db: return
        logger.info("Cloud Bridge: Remote command listener active.")
        def on_snapshot(col_snapshot, changes, read_time):
            for change in changes:
                if change.type.name == 'ADDED':
                    cmd_doc = change.document.to_dict()
                    if cmd_doc.get("status") == "pending":
                        cmd_text = cmd_doc.get("command")
                        logger.info(f"Remote command received: {cmd_text}")
                        self.event_bus.publish("voice_command", cmd_text)
                        change.document.reference.update({"status": "executed", "executed_at": time.time()})
        query_watch = self.command_ref.where("status", "==", "pending").on_snapshot(on_snapshot)
        while self.running:
            await asyncio.sleep(1)
    async def start(self):
        self.running = True
        await self._command_listener()
    def stop(self):
        self.running = False
