import threading
import time
import datetime
import json
import os
import concurrent.futures
from brain.core.text_generation import TextGeneration
from brain.core.prompt_frame import prompt_template

class JalenAgent:
    def __init__(self, memory_daemon, state_manager, model_path=None, gui_callback=None):
        self.state_manager = state_manager
        self.memory_daemon = memory_daemon
        self._running = False
        self._input_thread = None
        self.text_gen = TextGeneration(model_path=model_path)
        self.gui_callback = gui_callback
        self.core_profile = self._load_core_profile()

    def _load_core_profile(self):
        core_profile_path = os.path.join(os.path.dirname(__file__), '../core/core_profile.json')
        try:
            with open(core_profile_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[JalenAgent] Error loading core profile: {e}")
            return {}

    def start_chatbox(self):
        if self._running:
            print("[Judy🌹] Chatbox already running.")
            return
        print("[Judy🌹] Starting CLI chatbox...")
        self._running = True
        self._input_thread = threading.Thread(target=self._chat_loop, daemon=True)
        self._input_thread.start()

    def _chat_loop(self):
        while self._running:
            try:
                message = input("📨 You: ")
                if message.lower() in ["exit", "quit"]:
                    print("[Judy🌹] Shutting down chatbox.")
                    self._running = False
                    break

                # Store user input in both legacy and ChromaDB memory
                self.memory_daemon.add_memory({"timestamp": datetime.datetime.now().isoformat(), "text": f"User: {message}"}, memory_type="short")
                self.state_manager.add_memory_chroma(f"User: {message}", memory_type="short", metadata={"timestamp": time.time(), "role": "user"})

                # Run Judy's response in a background thread and print when ready
                def print_response(response):
                    # Store Judy's response in both legacy and ChromaDB memory
                    self.memory_daemon.add_memory({"timestamp": datetime.datetime.now().isoformat(), "text": f"Judy: {response}"}, memory_type="short")
                    self.state_manager.add_memory_chroma(f"Judy: {response}", memory_type="short", metadata={"timestamp": time.time(), "role": "judy"})
                    if self.gui_callback:
                        self.gui_callback(f"Judy🌹: {response}")
                    else:
                        print(f"Judy🌹: {response}")

                self.generate_response_async(message, print_response)
                # Wait for the response to print before accepting new input
                while hasattr(self, '_executor') and any(f.running() for f in getattr(self._executor, '_threads', [])):
                    time.sleep(0.1)

            except Exception as e:
                print(f"[Judy🌹] Error in chat loop: {e}")

    def stop(self):
        print("[Judy🌹] Stopping agent.")
        self._running = False
        if self._input_thread:
            self._input_thread.join()

    def handle_command(self, message):
        """
        Handle special commands, e.g. /switchmodel <model_path>
        """
        if message.startswith("/switchmodel"):
            parts = message.split(maxsplit=1)
            if len(parts) == 2:
                new_model_path = parts[1].strip()
                self.text_gen.switch_model(new_model_path)
                print(f"[JalenAgent] Switched model to: {new_model_path}")
                return f"[Judy🌹] Model switched to: {os.path.basename(new_model_path)}"
            else:
                return "[Judy🌹] Usage: /switchmodel <model_path>"
        return None

    def generate_response(self, user_input):
        """
        Generate a response to user_input using the full Judy prompt and core profile.
        """
        # Check for command
        if user_input.startswith("/"):
            cmd_result = self.handle_command(user_input)
            if cmd_result:
                return cmd_result

        # Use cached Judy's core profile
        core_profile = self.core_profile
        # Gather context
        mood = self.state_manager.get_mood() if hasattr(self.state_manager, 'get_mood') else "neutral"
        scene = self.state_manager.state.get("scene", "default")

        # Fetch recent memories from MemoryDaemon
        recent_memories = ""
        if self.memory_daemon and hasattr(self.memory_daemon, 'memory'):
            # Access the memory list directly from memory_daemon
            all_memories = self.memory_daemon.memory
            # Get the last 5 entries that are dictionaries and have a 'text' key
            valid_memories = [m['text'] for m in all_memories if isinstance(m, dict) and 'text' in m][-5:]
            recent_memories = '\n'.join(valid_memories)
            if not valid_memories:
                print("[JalenAgent] No valid recent memories found in MemoryDaemon for prompt.")
        else:
            print("[JalenAgent] MemoryDaemon not available or has no memory attribute.")

        # Compose prompt
        prompt = prompt_template.format(
            judy_name=core_profile.get("name", "Judy"),
            user_name=core_profile.get("preferred_pet_names", ["Stixx"])[0],
            mood=mood,
            scene=scene,
            recent_memories=recent_memories,
            user_message=user_input
        )
        response = self.text_gen.generate(prompt)
        return response.strip()

    def greet(self):
        """
        Generate Judy's initial greeting for first message in chat or GUI.
        """
        greeting = "Hello! I'm Judy, your AI assistant. How can I help you today?"
        return greeting

    def generate_response_async(self, user_input, callback):
        """
        Run generate_response in a background thread and call callback(result) when done.
        """
        if not hasattr(self, '_executor'):
            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = self._executor.submit(self.generate_response, user_input)
        future.add_done_callback(lambda f: callback(f.result()))
