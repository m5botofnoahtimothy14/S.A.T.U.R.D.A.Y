import os
import time
import logging
import threading

try:
    import firebase_admin
    from firebase_admin import credentials, db
except ImportError:
    firebase_admin = None

logger = logging.getLogger("SATURDAY.RealtimeBridge")

class RealtimeDatabaseBridge:
    def __init__(self, service_account: str, database_url: str, node_id: str = "saturday-node"):
        self.service_account = service_account
        self.database_url = database_url
        self.node_id = node_id
        self.app = None
        self.root_ref = None
        self.commands_ref = None
        self.status_ref = None
        self.listener = None
        self.running = False
        self._initialize()

    def _initialize(self):
        if firebase_admin is None:
            raise RuntimeError("firebase_admin is required for RealtimeDatabaseBridge")

        if not self.service_account or not os.path.exists(self.service_account):
            raise RuntimeError("A valid Firebase service account JSON path is required.")
        if not self.database_url:
            raise RuntimeError("FIREBASE_DATABASE_URL is required for Realtime Database integration.")

        if not firebase_admin._apps:
            cred = credentials.Certificate(self.service_account)
            self.app = firebase_admin.initialize_app(cred, {"databaseURL": self.database_url})
        else:
            self.app = firebase_admin.get_app()

        self.root_ref = db.reference(f"/saturday_system/{self.node_id}")
        self.commands_ref = self.root_ref.child("commands")
        self.status_ref = self.root_ref.child("status")
        logger.info("RealtimeDatabaseBridge initialized.")

    def publish_status(self, payload: dict):
        if not self.status_ref:
            return
        try:
            self.status_ref.set(payload)
        except Exception as exc:
            logger.warning(f"Realtime status publish failed: {exc}")

    def _execute_remote_command(self, key: str, command_data: dict):
        result = None
        try:
            self.commands_ref.child(key).update({"status": "executing", "executed_at": int(time.time())})
            result = self.command_callback(command_data.get("command", ""), command_data)
            self.commands_ref.child(key).update({
                "status": "executed",
                "result": str(result),
                "completed_at": int(time.time()),
            })
            logger.info(f"Remote command executed: {key}")
        except Exception as exc:
            logger.error(f"Remote command failed: {exc}")
            try:
                self.commands_ref.child(key).update({"status": "error", "error": str(exc), "completed_at": int(time.time())})
            except Exception:
                pass
        return result

    def _on_command_event(self, event):
        data = event.data
        if not data:
            return

        if isinstance(data, dict):
            for command_key, payload in data.items():
                if isinstance(payload, dict) and payload.get("status") == "pending":
                    self._execute_remote_command(command_key, payload)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("status") == "pending" and "id" in item:
                    self._execute_remote_command(item["id"], item)

    def _listen_loop(self):
        try:
            self.listener = self.commands_ref.listen(self._on_command_event)
        except Exception as exc:
            logger.error(f"Realtime listener failed: {exc}")

    def _publish_loop(self):
        while self.running:
            try:
                if self.status_provider:
                    payload = self.status_provider()
                    self.publish_status(payload)
            except Exception as exc:
                logger.warning(f"Realtime publish loop error: {exc}")
            time.sleep(10)

    def start(self, status_provider, command_callback):
        if not callable(status_provider) or not callable(command_callback):
            raise RuntimeError("A status provider and command callback are required.")

        self.status_provider = status_provider
        self.command_callback = command_callback
        self.running = True
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.publisher_thread = threading.Thread(target=self._publish_loop, daemon=True)
        self.listener_thread.start()
        self.publisher_thread.start()
        logger.info("RealtimeDatabaseBridge started.")

    def stop(self):
        self.running = False
        try:
            if self.listener:
                self.listener.close()
        except Exception:
            pass
        logger.info("RealtimeDatabaseBridge stopped.")
