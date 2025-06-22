import os
import json
import threading
import logging
from datetime import datetime, timedelta

class MemoryDaemon:
    def __init__(self, memory_file, archive_file, expiration_minutes=60):
        self.memory_file = memory_file
        self.archive_file = archive_file
        self.expiration_minutes = expiration_minutes
        self.running = False
        self.memory = []
        self.shutdown_event = threading.Event()
        self._thread = None
        self.load_memory()

    def load_memory(self):
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                try:
                    self.memory = json.load(f)
                    if not isinstance(self.memory, list):
                        print("[MemoryDaemon] Memory file is not a list. Resetting to empty list.")
                        self.memory = []
                    else:
                        print(f"[MemoryDaemon] Loaded {len(self.memory)} memories.") # MODIFIED
                except json.JSONDecodeError:
                    print("[MemoryDaemon] Memory file is corrupted. Starting fresh.") # MODIFIED
                    self.memory = []
        else:
            self.memory = []

    def save_memory(self):
        with open(self.memory_file, 'w') as f:
            json.dump(self.memory, f, indent=4)
        # print(f"[MemoryDaemon] Saved {len(self.memory)} memories to {self.memory_file}") # Optional: for very verbose logging

    def archive_memory(self, item):
        if not os.path.exists(self.archive_file):
            with open(self.archive_file, 'w') as f:
                json.dump([], f)

        with open(self.archive_file, 'r+') as f:
            archive = json.load(f)
            if not isinstance(archive, list):
                print("[MemoryDaemon] Archive file is not a list. Resetting to empty list.")
                archive = []
            archive.append(item)
            f.seek(0)
            json.dump(archive, f, indent=4)
            f.truncate()
            print(f"[MemoryDaemon] Archived memory: {item.get('id', 'Unknown ID')}") # MODIFIED

    def check_memory_expiration(self):
        now = datetime.utcnow()
        active_memories = []
        for item in self.memory:
            try:
                timestamp_str = item.get("timestamp")
                if not isinstance(timestamp_str, str):
                    raise ValueError("Timestamp is not a string.")
                item_time = datetime.fromisoformat(timestamp_str)
                age = (now - item_time).total_seconds() / 60

                if age > self.expiration_minutes:
                    self.archive_memory(item)
                else:
                    active_memories.append(item)

            except Exception as e:
                print(f"[MemoryDaemon] Error processing memory item: {item.get('id', 'Unknown ID')} | Error: {e}") # MODIFIED

        if len(self.memory) != len(active_memories):
            print(f"[MemoryDaemon] Expired {len(self.memory) - len(active_memories)} memories.")
        self.memory = active_memories
        self.save_memory()

    def start(self):
        if self.running:
            print("[MemoryDaemon] Already running.")
            return
        print("[MemoryDaemon] Starting daemon thread...")
        self.running = True
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def run(self):
        print("[MemoryDaemon] MemoryDaemon started.") # MODIFIED
        while self.running:
            # self.check_memory_expiration() # Commented out: Handled by PulseCoordinator's idle cycle via StateManager
            print("[MemoryDaemon] Running... (memory expiration logic now handled by StateManager via PulseCoordinator)")
            # Wait for 10 seconds or until shutdown_event is set
            self.shutdown_event.wait(10) # NEW

    def stop(self):
        print("[MemoryDaemon] Attempting to stop MemoryDaemon...") # MODIFIED
        self.running = False
        self.shutdown_event.set()
        if self._thread:
            self._thread.join()
        logging.info("MemoryDaemon stopped.")

    def add_memory(self, memory_item, memory_type="short"):
        """Adds a new memory entry to the memory list and saves it. Accepts memory_type for compatibility."""
        self.memory.append(memory_item)
        self.save_memory()

    def prepare_prompt_context(self):
        # Return a string summary or recent memory items for the prompt
        if not self.memory:
            return "(No recent memories.)"
        # Get the last 5 valid memories as a summary
        recent = [item for item in self.memory if isinstance(item, dict)][-5:]
        summary = "\n".join([
            f"[{item.get('timestamp', 'unknown')}] {item.get('content', str(item))}" for item in recent
        ])
        return summary

    def on_heartbeat(self):
        """Called by HeartbeatDaemon on each heartbeat. Sync new/expired memories to StateManager (ChromaDB)."""
        print("[MemoryDaemon] Heartbeat received. Syncing to StateManager...") # MODIFIED: ChromaDB sync logic commented out
        # Example: Push all new/active memories to StateManager's ChromaDB
        # if hasattr(self, 'state_manager') and self.state_manager:
        #     for item in self.memory:
        #         # Only push if not already in ChromaDB (you may want a better check in production)
        #         if isinstance(item, dict) and 'content' in item:
        #             self.state_manager.add_memory_chroma(item['content'], memory_type="short", metadata=item)
        print("[MemoryDaemon] Note: ChromaDB sync from MemoryDaemon.on_heartbeat is now handled by StateManager's idle tasks.")
        # You can also pull relevant context from ChromaDB if needed
