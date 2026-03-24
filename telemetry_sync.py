from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TelemetryConfig:
    collection: str = "telemetry_nodes"
    history_limit: int = 200
    log_limit: int = 100


class TelemetrySync:
    def __init__(
        self,
        *,
        node_id: str,
        service_account_path: str | None = None,
        project_id: str | None = None,
        config: TelemetryConfig | None = None,
    ) -> None:
        self.node_id = node_id
        self.project_id = project_id or os.getenv("FIREBASE_PROJECT_ID")
        self.config = config or TelemetryConfig()
        self._lock = threading.RLock()
        self._recent_logs: list[dict[str, Any]] = []
        self._latest_snapshot: dict[str, Any] | None = None
        self._firebase_available = False
        self._db = None
        self._init_firebase(service_account_path)

    @property
    def firebase_enabled(self) -> bool:
        return self._firebase_available

    def _init_firebase(self, service_account_path: str | None) -> None:
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            
            if not firebase_admin._apps:
                options = {}
                if self.project_id:
                    options["projectId"] = self.project_id
                
                if service_account_path and os.path.exists(service_account_path):
                    cred = credentials.Certificate(service_account_path)
                    firebase_admin.initialize_app(cred, options=options or None)
                elif self.project_id:
                    firebase_admin.initialize_app(options=options)
            
            if firebase_admin._apps:
                self._db = firestore.client()
                self.node_ref = self._db.collection(self.config.collection).document(self.node_id)
                self.history_ref = self.node_ref.collection("history")
                self.log_ref = self.node_ref.collection("logs")
                self._firebase_available = True
                print("Telemetry: Firebase connected")
        except Exception as e:
            print(f"Telemetry: Firebase not available: {e}")
            self._db = None
            self._firebase_available = False

    def _system_metrics(self) -> dict[str, Any]:
        try:
            import psutil
            vm = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": vm.percent,
                "memory_used_mb": round(vm.used / (1024 * 1024), 2),
                "memory_total_mb": round(vm.total / (1024 * 1024), 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "timestamp": _utc_now_iso(),
            }
        except Exception:
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "memory_used_mb": 0,
                "memory_total_mb": 0,
                "disk_percent": 0,
                "disk_used_gb": 0,
                "disk_total_gb": 0,
                "timestamp": _utc_now_iso(),
            }

    def push_log(self, *, level: str, message: str, context: dict[str, Any] | None = None) -> None:
        payload = {
            "timestamp": _utc_now_iso(),
            "level": level.upper(),
            "message": message,
            "context": context or {},
        }
        
        # Always store locally
        with self._lock:
            self._recent_logs.append(payload)
            if len(self._recent_logs) > self.config.log_limit:
                self._recent_logs = self._recent_logs[-self.config.log_limit:]
        
        # Try Firebase if available
        if self._firebase_available and self._db:
            try:
                self.log_ref.add(payload)
            except Exception:
                pass

    def build_snapshot(
        self,
        *,
        agent_state: dict[str, Any],
        sensors: dict[str, Any],
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        metrics = self._system_metrics()
        with self._lock:
            recent_logs = list(self._recent_logs[-20:])

        return {
            "node_id": self.node_id,
            "updated_at": _utc_now_iso(),
            "timestamp": metrics["timestamp"],
            "metrics": metrics,
            "agent_state": agent_state,
            "robotics": sensors,
            "task_status": tasks,
            "backend": "firebase" if self._firebase_available else "local",
            "logs": recent_logs,
        }

    def push_snapshot(self, payload: dict[str, Any]) -> None:
        self._latest_snapshot = dict(payload)
        if not self._firebase_available or not self._db:
            return
        try:
            self.node_ref.set(payload, merge=True)
            self.history_ref.add(payload)
            self._trim_history()
        except Exception as e:
            print(f"Error pushing snapshot: {e}")

    def _trim_history(self) -> None:
        if not self._firebase_available:
            return
        try:
            from firebase_admin import firestore
            docs = self.history_ref.order_by("updated_at", direction=firestore.Query.DESCENDING).stream()
            stale = []
            for index, doc in enumerate(docs):
                if index >= self.config.history_limit:
                    stale.append(doc.reference)
            if not stale:
                return
            for ref in stale:
                ref.delete()
        except Exception:
            pass

    def pull_latest(self) -> dict[str, Any] | None:
        if not self._firebase_available or not self._db:
            return dict(self._latest_snapshot) if self._latest_snapshot else None
        try:
            doc = self.node_ref.get()
            if doc.exists:
                return doc.to_dict()
        except Exception:
            pass
        return None
