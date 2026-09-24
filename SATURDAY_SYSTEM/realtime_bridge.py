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
    def __init__(self, service_account: str, database_url: str, node_id: str = "saturday-node", publish_interval: float = 10.0):
        self.service_account = service_account
        self.database_url = database_url
        self.node_id = node_id
        self.publish_interval = max(2.0, float(publish_interval))
        self.app = None
        self.root_ref = None
        self.commands_ref = None
        self.status_ref = None
        self.listener = None
        self.running = False
        self.status_provider = None
        self.command_callback = None
        self.listener_thread = None
        self.publisher_thread = None
        self._initialize()

    def _initialize(self):
        if firebase_admin is None:
            raise RuntimeError("firebase_admin is required for RealtimeDatabaseBridge")

        if not self.service_account or not os.path.exists(self.service_account):
            raise RuntimeError("A valid Firebase service account JSON path is required.")
        if not self.database_url:
            raise RuntimeError("FIREBASE_DATABASE_URL is required for Realtime Database integration.")

        if not firebase_admin._apps:
            try:
                self.app = firebase_admin.get_app()
            except ValueError:
                cred = credentials.Certificate(self.service_account)
                self.app = firebase_admin.initialize_app(cred, {"databaseURL": self.database_url})
        else:
            self.app = firebase_admin.get_app()

        self.root_ref = db.reference(f"/saturday_system/{self.node_id}")
        self.commands_ref = self.root_ref.child("commands")
        self.status_ref = self.root_ref.child("status")
        logger.info("RealtimeDatabaseBridge initialized.")

    def publish_status(self, payload: dict) -> bool:
        if not self.status_ref:
            return False
        try:
            self.status_ref.set(payload)
            return True
        except Exception as exc:
            logger.warning(f"Realtime status publish failed: {exc}")
            return False

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
        try:
            data = event.data
        except Exception as exc:
            logger.warning(f"Ignoring malformed realtime event: {exc}")
            return
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
        failures = 0
        while self.running:
            try:
                if self.status_provider:
                    ok = self.publish_status(self.status_provider())
                    failures = 0 if ok else failures + 1
                else:
                    failures = 0
            except Exception as exc:
                failures += 1
                logger.warning(f"Realtime publish loop error: {exc}")
            # Backoff on repeated failure so a dead backend can't hot-spin
            # the loop for months: 0.5s steps up to 60s between attempts.
            wait = min(60.0, self.publish_interval * (2 ** min(failures, 4)))
            for _ in range(int(wait * 2)):
                if not self.running:
                    break
                time.sleep(0.5)

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
        for thread in (getattr(self, "listener_thread", None), getattr(self, "publisher_thread", None)):
            try:
                if thread and thread.is_alive():
                    thread.join(timeout=3.0)
            except Exception:
                pass
        logger.info("RealtimeDatabaseBridge stopped.")
