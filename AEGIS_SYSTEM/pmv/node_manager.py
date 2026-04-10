import json
import uuid
import socket
from pathlib import Path

class NodeManager:
    def __init__(self, node_config_path: str):
        self.config_path = Path(node_config_path)
        self.node_info = self._load_or_create_node()

    def _load_or_create_node(self):
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        
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

    def add_trusted_peer(self, peer_id: str):
        if peer_id not in self.node_info["trusted_peers"]:
            self.node_info["trusted_peers"].append(peer_id)
            self._save_node()

    def _save_node(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.node_info, f, indent=4)

    def status(self):
        return f"Node ID: {self.node_info['node_id']} | Host: {self.node_info['hostname']}"
