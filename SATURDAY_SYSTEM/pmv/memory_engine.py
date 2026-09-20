import os   
import json
import time
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger("SATURDAY.MemoryEngine")

class MemoryEngine:
    def __init__(self, vault_path: str, crypto):
        self.vault_path = Path(vault_path)
        self.crypto = crypto
        self.vault_path.mkdir(parents=True, exist_ok=True)
        # Structure: /vault/memory/entries/*.enc

    def store_entry(self, content: str, entry_type: str = "general", tags: Optional[List[str]] = None):
        if tags is None:
            tags = []
        if not isinstance(tags, list):
            raise TypeError("tags must be a list of strings")
        tags = [str(t).strip() for t in tags if str(t).strip()]
        if not content or not content.strip():
            raise ValueError("content must not be empty")

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

    def retrieve_all_entries(self, limit: int = 500) -> List[Dict]:
        entries = []
        files = sorted(self.vault_path.glob("*.enc"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        for file in files[:limit]:
            try:
                encrypted_data = file.read_bytes()
                decrypted_data = self.crypto.decrypt_data(encrypted_data)
                entries.append(json.loads(decrypted_data.decode()))
            except Exception as e:
                logger.warning(f"Skipping undecryptable entry {file.name}: {e}")
        return entries

    def search_by_tag(self, tag: str) -> List[Dict]:
        all_entries = self.retrieve_all_entries()
        return [e for e in all_entries if tag in e.get('tags', [])]

    def search_by_time(self, start_time: float, end_time: float) -> List[Dict]:
        all_entries = self.retrieve_all_entries()
        return [e for e in all_entries if start_time <= e.get('timestamp', 0) <= end_time]

    def retrieve_entry(self, entry_id: str) -> Optional[Dict]:
        safe_id = "".join(c for c in str(entry_id) if c.isalnum() or c in "-_")
        if not safe_id or safe_id != str(entry_id):
            return None
        file_path = self.vault_path / f"{safe_id}.enc"
        if not file_path.exists():
            return None

        try:
            encrypted_data = file_path.read_bytes()
            decrypted_data = self.crypto.decrypt_data(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.warning(f"Failed to decrypt entry {safe_id}: {e}")
            return None

    def delete_entry(self, entry_id: str) -> bool:
        safe_id = "".join(c for c in str(entry_id) if c.isalnum() or c in "-_")
        if not safe_id or safe_id != str(entry_id):
            return False
        file_path = self.vault_path / f"{safe_id}.enc"
        try:
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to delete entry {safe_id}: {e}")
            return False
