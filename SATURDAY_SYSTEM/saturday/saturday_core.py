import logging
from pathlib import Path
from saturday.controller import MemoryController

logger = logging.getLogger("SATURDAY.Core")

class SATURDAYCore:
    def __init__(self, passphrase: str, project_root: Path):
        self.project_root = project_root
        # The Memory Controller is the ONLY way SATURDAY interacts with the vault
        self.pmv = MemoryController(passphrase, project_root)
        self.is_running = False

    def initialize(self):
        """Pre-flight checks and mounting."""
        self.pmv.mount_vaults()
        self.pmv.update_heartbeat()
        self.is_running = True
        logger.info("SATURDAY Intelligence initialized and online.")

    def process_command(self, cmd_string: str):
        """
        Main decision layer for commands.
        In a real AI system, this would involve NLP/LLM orchestration.
        Here we implement the logic for the required secure commands.
        """
        cmd_string = cmd_string.strip().lower()
        
        # Inactivity check
        self.pmv.auto_lock_check()

        try:
            # Command: Store
            if cmd_string.startswith("store "):
                content = cmd_string[6:]
                tags = []
                if "tag:" in content:
                    parts = content.split("tag:")
                    content = parts[0].strip()
                    tags = [t.strip() for t in parts[1].split(",")]
                
                entry_id = self.pmv.secure_store(content, tags=tags)
                return f"✅ Stored securely. Entry ID: {entry_id}"

            # Command: Retrieve
            elif cmd_string.startswith("retrieve "):
                entry_id = cmd_string[9:].strip()
                entry = self.pmv.secure_retrieve(entry_id)
                if entry:
                    return f"📝 Entry found:\n   Time: {entry['timestamp']}\n   Content: {entry['content']}\n   Tags: {entry['tags']}"
                return "❌ Entry not found."

            # Command: Search
            elif cmd_string.startswith("search "):
                query = cmd_string[7:].strip()
                if query.startswith("tag:"):
                    tag = query[4:].strip()
                    results = self.pmv.secure_search(tag=tag)
                else:
                    results = self.pmv.secure_search() # Default: list all for now
                
                if not results:
                    return "🔎 No matches found."
                
                output = f"🔎 Found {len(results)} matches:\n"
                for r in results[:5]: # Show last 5
                    output += f"   - [{r['id'][:8]}] {r['content'][:50]}...\n"
                return output

            # Command: Status
            elif cmd_string == "status":
                dm_status = self.pmv.get_deadman_status()
                node = self.pmv.node_status()
                return f"🔋 SATURDAY Status: ONLINE\n🛡️ Vault: MOUNTED\n💀 Deadman: {dm_status}\n🌐 {node}"

            # Command: Sync
            elif cmd_string == "sync":
                # Simulated sync operation
                return "🔄 Sync initiated. Synchronizing encrypted containers via P2P..."

            # Command: Heartbeat
            elif cmd_string == "heartbeat":
                self.pmv.update_heartbeat()
                return "💓 Heartbeat updated."

            else:
                return "❓ Unknown command. Try: 'store [text]', 'retrieve [id]', 'search tag:[tag]', 'status', 'sync', 'heartbeat'."

        except Exception as e:
            return f"❌ System Error: {str(e)}"

    def shutdown(self):
        """Secure shutdown sequence."""
        if self.is_running:
            logger.info("Securing memory core...")
            self.pmv.dismount_vaults()
            self.is_running = False
            logger.info("SATURDAY Core deactivated.")
