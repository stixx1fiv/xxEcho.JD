# core/daemons/memory_daemon.py

import os
import json
from datetime import datetime
from core.daemons.base_daemon import BaseDaemon

class MemoryDaemon(BaseDaemon):
    def __init__(self, memory_file, archive_file, expiration_minutes=60):
        super().__init__(name="MemoryDaemon", interval=10)
        self.memory_file = memory_file
        self.archive_file = archive_file
        self.expiration_minutes = expiration_minutes
        self.memory = []
        self.state_manager = None  # Optional external reference
        self.load_memory()

    def heartbeat(self):
        self.check_memory_expiration()

    def load_memory(self):
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                try:
                    self.memory = json.load(f)
                    if not isinstance(self.memory, list):
                        print("[MemoryDaemon] Memory file is not a list. Resetting to empty list.")
                        self.memory = []
                    else:
                        print(f"[MemoryDaemon] Loaded {len(self.memory)} memories.")
                except json.JSONDecodeError:
                    print("[MemoryDaemon] Memory file is corrupted. Starting fresh.")
                    self.memory = []
        else:
            self.memory = []

    def save_memory(self):
        with open(self.memory_file, 'w') as f:
            json.dump(self.memory, f, indent=4)

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
            print(f"[MemoryDaemon] Archived memory: {item.get('id', 'Unknown ID')}")

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
                print(f"[MemoryDaemon] Error processing memory item: {item.get('id', 'Unknown ID')} | Error: {e}")

        if len(self.memory) != len(active_memories):
            print(f"[MemoryDaemon] Expired {len(self.memory) - len(active_memories)} memories.")
        self.memory = active_memories
        self.save_memory()

    def add_memory(self, memory_item, memory_type="short"):
        self.memory.append(memory_item)
        self.save_memory()

    def prepare_prompt_context(self):
        if not self.memory:
            return "(No recent memories.)"
        recent = [item for item in self.memory if isinstance(item, dict)][-5:]
        summary = "\n".join([
            f"[{item.get('timestamp', 'unknown')}] {item.get('content', str(item))}" for item in recent
        ])
        return summary

    def on_heartbeat(self):
        print("[MemoryDaemon] Heartbeat received. Syncing to StateManager...")
        if self.state_manager:
            for item in self.memory:
                if isinstance(item, dict) and 'content' in item:
                    self.state_manager.add_memory_chroma(item['content'], memory_type="short", metadata=item)
