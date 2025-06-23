# core/daemons/base_daemon.py

import threading
import time
import logging

class BaseDaemon(threading.Thread):
    def __init__(self, name="BaseDaemon", interval=5):
        super().__init__(daemon=True)
        self.name = name
        self.interval = interval
        self._stop_event = threading.Event()
        self.logger = logging.getLogger(self.name)
        logging.basicConfig(level=logging.INFO)

    def run(self):
        self.logger.info(f"{self.name} started.")
        while not self._stop_event.is_set():
            try:
                self.heartbeat()
            except Exception as e:
                self.logger.error(f"Error in {self.name}: {e}")
            self._stop_event.wait(self.interval)
        self.logger.info(f"{self.name} stopped.")

    def heartbeat(self):
        raise NotImplementedError("Subclasses must implement heartbeat()")

    def start(self):
        self.logger.info(f"Starting {self.name}...")
        super().start()

    def stop(self):
        self.logger.info(f"Stopping {self.name}...")
        self._stop_event.set()
        self.join()
