import json
import logging
import re
import uuid
import socket
from pathlib import Path

logger = logging.getLogger("SATURDAY.Node")

_PEER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

class NodeManager:
    def __init__(self, node_config_path: str):
        self.config_path = Path(node_config_path)
        self.node_info = self._load_or_create_node()

    def _load_or_create_node(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict) and "node_id" in data:
                    data.setdefault("trusted_peers", [])
                    data.setdefault("sync_folders", ["vault", "blackbox"])
                    return data
                logger.warning("Node config corrupt; backing up and regenerating.")
                self._backup_corrupt()
            except Exception as e:
                logger.warning(f"Node config unreadable ({e}); backing up and regenerating.")
                self._backup_corrupt()
        
        node_id = str(uuid.uuid4())
        hostname = socket.gethostname()
        new_node = {
            "node_id": node_id,
            "hostname": hostname,
            "trusted_peers": [],
            "sync_folders": ["vault", "blackbox"]
        }
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(new_node, f, indent=4)
        
        return new_node

    def get_identity(self):
        return self.node_info

    def _backup_corrupt(self):
        try:
            backup = self.config_path.with_suffix(".corrupt.bak")
            self.config_path.rename(backup)
        except Exception:
            pass

    def add_trusted_peer(self, peer_id: str):
        peer_id = str(peer_id).strip()
        if not _PEER_RE.match(peer_id):
            raise ValueError("Invalid peer ID format.")
        if peer_id not in self.node_info["trusted_peers"]:
            self.node_info["trusted_peers"].append(peer_id)
            self._save_node()

    def remove_trusted_peer(self, peer_id: str) -> bool:
        if peer_id in self.node_info.get("trusted_peers", []):
            self.node_info["trusted_peers"].remove(peer_id)
            self._save_node()
            return True
        return False

    def _save_node(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.node_info, f, indent=4)

    def status(self):
        node_id = self.node_info.get('node_id', 'unknown')
        host = self.node_info.get('hostname', 'unknown')
        peers = len(self.node_info.get('trusted_peers', []))
        return f"Node ID: {node_id} | Host: {host} | Trusted peers: {peers}"
