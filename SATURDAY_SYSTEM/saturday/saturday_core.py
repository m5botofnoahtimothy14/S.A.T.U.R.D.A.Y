import logging
import shlex
import time
from pathlib import Path
from saturday.controller import MemoryController

logger = logging.getLogger("SATURDAY.Core")

class SATURDAYCore:
    def __init__(self, passphrase: str, project_root: Path):
        self.project_root = project_root
        self.pmv = MemoryController(passphrase, project_root)
        self.is_running = False
        self._command_handlers = self._build_command_handlers()

    def initialize(self):
        """Pre-flight checks and vault mounting."""
        self.pmv.mount_vaults()
        self.pmv.update_heartbeat()
        self.is_running = True
        logger.info("SATURDAY Intelligence initialized and online.")

    def _build_command_handlers(self):
        return {
            "store": self._handle_store,
            "retrieve": self._handle_retrieve,
            "search": self._handle_search,
            "status": self._handle_status,
            "sync": self._handle_sync,
            "heartbeat": self._handle_heartbeat,
            "help": self._handle_help,
        }

    def _parse_command(self, cmd_string: str):
        tokens = shlex.split(cmd_string.strip())
        command = tokens[0].lower() if tokens else ""
        args = tokens[1:]
        return command, args

    def _extract_tags(self, text: str):
        tags = []
        if "tag:" in text:
            content_part, tag_part = text.split("tag:", 1)
            tags = [t.strip() for t in tag_part.split(",") if t.strip()]
            return content_part.strip(), tags
        return text.strip(), tags

    def process_command(self, cmd_string: str):
        cmd_string = cmd_string.strip()
        if not cmd_string:
            return "❓ Please enter a command. Type 'help' for available commands."

        if self.pmv.auto_lock_check():
            logger.info("Vault auto-locked due to inactivity.")

        command, args = self._parse_command(cmd_string)
        handler = self._command_handlers.get(command, self._handle_unknown)
        try:
            return handler(args, cmd_string)
        except Exception as exc:
            logger.exception("Command processing failed", error=str(exc))
            return f"❌ System Error: {str(exc)}"

    def _handle_store(self, args, raw_text):
        content, tags = self._extract_tags(raw_text[len("store"):].strip())
        if not content:
            return "❌ Please provide text to store. Example: store My secret tag:project,secret"
        entry_id = self.pmv.secure_store(content, tags=tags)
        return f"✅ Stored securely. Entry ID: {entry_id}"

    def _handle_retrieve(self, args, raw_text):
        if not args:
            return "❌ Provide the entry ID to retrieve. Example: retrieve <entry_id>"
        entry = self.pmv.secure_retrieve(args[0])
        if not entry:
            return "❌ Entry not found."
        return (
            f"📝 Entry found:\n"
            f"   Time: {entry.get('timestamp')}\n"
            f"   Content: {entry.get('content')}\n"
            f"   Tags: {entry.get('tags')}"
        )

    def _handle_search(self, args, raw_text):
        query = raw_text[len("search"):].strip()
        if query.lower().startswith("tag:"):
            tag = query[4:].strip()
            results = self.pmv.secure_search(tag=tag)
        else:
            results = self.pmv.secure_search()

        if not results:
            return "🔎 No matches found."

        results = sorted(results, key=lambda e: e.get("timestamp", 0), reverse=True)
        summary = [f"   - [{r['id'][:8]}] {r['content'][:60]}..." for r in results[:5]]
        return f"🔎 Found {len(results)} matches:\n" + "\n".join(summary)

    def _handle_status(self, args, raw_text):
        dm_status = self.pmv.get_deadman_status()
        node_status = self.pmv.node_status()
        return (
            "🔋 SATURDAY Status: ONLINE\n"
            f"🛡️ Vault mounted: {self.pmv.vault_mounted}\n"
            f"💀 Deadman status: {dm_status}\n"
            f"🌐 {node_status}"
        )

    def _handle_sync(self, args, raw_text):
        return "🔄 Sync initiated. Synchronizing encrypted containers via P2P..."

    def _handle_heartbeat(self, args, raw_text):
        self.pmv.update_heartbeat()
        return "💓 Heartbeat updated."

    def _handle_help(self, args, raw_text):
        return (
            "Available commands:\n"
            " - store [content] tag:[tags] : Store encrypted memory.\n"
            " - retrieve [id] : Retrieve a stored entry.\n"
            " - search tag:[tag] : Search memory by tag.\n"
            " - search : List recent entries.\n"
            " - status : Show system and vault status.\n"
            " - heartbeat : Update the deadman heartbeat.\n"
            " - sync : Trigger a sync operation.\n"
            " - help : Show this help text."
        )

    def _handle_unknown(self, args, raw_text):
        return "❓ Unknown command. Type 'help' for available commands."

    def get_status_payload(self):
        return {
            "online": self.is_running,
            "vault_mounted": self.pmv.vault_mounted,
            "deadman_status": self.pmv.get_deadman_status(),
            "node_status": self.pmv.node_status(),
            "last_activity": self.pmv.last_activity,
            "timestamp": time.time(),
        }

    def shutdown(self):
        if self.is_running:
            logger.info("Securing memory core...")
            self.pmv.dismount_vaults()
            self.is_running = False
            logger.info("SATURDAY Core deactivated.")
