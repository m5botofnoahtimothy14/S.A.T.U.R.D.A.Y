import os
import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Optional

class MemoryEngine:
    def __init__(self, vault_path: str, crypto):
        self.vault_path = Path(vault_path)
        self.crypto = crypto
        self.vault_path.mkdir(parents=True, exist_ok=True)
        # Structure: /vault/memory/entries/*.enc

    def store_entry(self, content: str, entry_type: str = "general", tags: List[str] = None):
        if tags is None:
            tags = []
        
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "type": entry_type,
            "tags": tags,
            "content": content
        }
        
        entry_json = json.dumps(entry)
        encrypted_data = self.crypto.encrypt_data(entry_json.encode())
        
        file_name = f"{entry['id']}.enc"
        file_path = self.vault_path / file_name
        
        with open(file_path, 'wb') as f:
            f.write(encrypted_data)
        
        return entry['id']

    def retrieve_all_entries(self) -> List[Dict]:
        entries = []
        for file in self.vault_path.glob("*.enc"):
            try:
                encrypted_data = file.read_bytes()
                decrypted_data = self.crypto.decrypt_data(encrypted_data)
                entries.append(json.loads(decrypted_data.decode()))
            except Exception as e:
                print(f"Error decrypting {file}: {e}")
        return entries

    def search_by_tag(self, tag: str) -> List[Dict]:
        all_entries = self.retrieve_all_entries()
        return [e for e in all_entries if tag in e.get('tags', [])]

    def search_by_time(self, start_time: float, end_time: float) -> List[Dict]:
        all_entries = self.retrieve_all_entries()
        return [e for e in all_entries if start_time <= e.get('timestamp', 0) <= end_time]

    def retrieve_entry(self, entry_id: str) -> Optional[Dict]:
        file_path = self.vault_path / f"{entry_id}.enc"
        if not file_path.exists():
            return None
        
        encrypted_data = file_path.read_bytes()
        decrypted_data = self.crypto.decrypt_data(encrypted_data)
        return json.loads(decrypted_data.decode())
