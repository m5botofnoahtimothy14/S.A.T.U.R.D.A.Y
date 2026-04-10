                   

import os
import logging
import hashlib
import threading
import time
import shutil
logger = logging.getLogger("AEGIS.Antivirus")
logger.setLevel(logging.INFO)
class Antivirus:
    def __init__(self, scan_paths=["./"], quarantine_folder="./quarantine"):
        self.scan_paths = scan_paths
        self.quarantine_folder = quarantine_folder
        os.makedirs(self.quarantine_folder, exist_ok=True)
        self.running = False
        self.known_hashes = set()                                           
    def start(self, interval=60):
        self.running = True
        threading.Thread(target=self._scan_loop, args=(interval,), daemon=True).start()
        logger.info("Antivirus started.")
    def _scan_loop(self, interval):
        while self.running:
            self.scan_files()
            time.sleep(interval)
    def scan_files(self):
        for path in self.scan_paths:
            for root, dirs, files in os.walk(path):
                for file in files:
                    filepath = os.path.join(root, file)
                    try:
                        file_hash = self.hash_file(filepath)
                        if file_hash not in self.known_hashes:
                            logger.warning(f"Antivirus: Suspicious file detected: {filepath}")
                            self.quarantine(filepath)
                    except Exception as e:
                        logger.error(f"Error scanning {filepath}: {e}")
    def hash_file(self, filepath):
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            h.update(f.read())
        return h.hexdigest()
    def quarantine(self, filepath):
        try:
            filename = os.path.basename(filepath)
            target = os.path.join(self.quarantine_folder, filename)
            shutil.move(filepath, target)
            logger.info(f"File {filepath} quarantined to {target}")
        except Exception as e:
            logger.error(f"Failed to quarantine {filepath}: {e}")
