import sys
import os
import time
import json
import signal
from queue import Queue
from brain.daemons.memory_daemon import MemoryDaemon
from brain.daemons.lore_trigger_watcher import LoreTriggerWatcher
from brain.agents.jalen_agent import JalenAgent
from brain.core.state_manager import StateManager
from brain.daemons.MessageHandlerDaemon import MessageHandlerDaemon
from brain.daemons.PulseCoordinator import PulseCoordinator
from runners import run_daemons
from gui.widgets import status_bar  # 👈 so PulseCoordinator can hit the GUI pulse handler
import threading
import tkinter as tk
from tkinter import scrolledtext

CONFIG_PATH = "config/config.yaml"
MEMORY_PATH = "runtime/memory.json"
ARCHIVE_PATH = "chronicles/memory_archive.json"
PID_FILE = "app.pid"

def load_config(path):
    if not os.path.exists(path):
        print(f"[Config] Config file not found: {path}")
        return {}
    if path.endswith('.json'):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Config] Error loading JSON config: {e}")
            return {}
    else:
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML is required for YAML config files. Install with 'pip install pyyaml'.")
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[Config] Error loading YAML config: {e}")
            return {}

def your_actual_memory_injector(content: str):
    print(f"[MemoryInjector] Snippet: {content[:100]}...")
    pass

def write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def read_pid():
    if not os.path.exists(PID_FILE):
        return None
    with open(PID_FILE, "r") as f:
        return int(f.read().strip())

def remove_pid():
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)

def launch_test_gui(agent):
    def on_send(event=None):
        user_input = input_box.get()
        if user_input.strip():
            chat_log.config(state='normal')
            chat_log.insert(tk.END, f'You: {user_input}\n')
            chat_log.config(state='disabled')
            input_box.delete(0, tk.END)
            # Asynchronously get response from agent
            if hasattr(agent, 'generate_response_async'):
                # The callback (jalen_widget._log_message) will handle displaying the response
                agent.generate_response_async(user_input, agent.gui_callback)
            else:
                # Fallback or error handling if method doesn't exist
                jalen_widget._log_message("[Error] Agent does not support async response generation.")

    root = tk.Tk()
    root.title("Judy Test Chat")
    root.geometry("400x500")  # Increased height to accommodate JalenWidget
    root.resizable(False, False)

    # Create JalenWidget instance
    from gui.components.jalen_widget import JalenWidget
    jalen_widget = JalenWidget(root)
    jalen_widget.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # Pass JalenWidget's _log_message as callback to agent
    agent.gui_callback = jalen_widget._log_message

    chat_log = jalen_widget.chat_display # Use JalenWidget's chat_display

    input_frame = tk.Frame(root)
    input_frame.pack(fill=tk.X, padx=10, pady=(0,10))

    input_box = tk.Entry(input_frame)
    input_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
    input_box.bind('<Return>', on_send)

    send_btn = tk.Button(input_frame, text="Send", command=on_send)
    send_btn.pack(side=tk.RIGHT)

    input_box.focus()
    root.mainloop()

def main():
    write_pid()
    config = load_config(CONFIG_PATH)
    print("[✅] Config loaded:", config)

    state_file = config.get("state_file", "runtime/state.json")
    state_manager = StateManager(memory_file=state_file)

    memory_daemon = MemoryDaemon(memory_file=MEMORY_PATH, archive_file=ARCHIVE_PATH,
                                 expiration_minutes=config.get("memory_settings", {}).get("expiration_minutes", 60))
    memory_daemon.state_manager = state_manager

    lore_trigger_watcher = LoreTriggerWatcher(state_manager, memory_daemon)

    message_queue = Queue()

    def dummy_command_router(cmd):
        print(f"[CommandRouter] {cmd}")

    message_handler = MessageHandlerDaemon(dummy_command_router, message_queue, state_manager=state_manager)
    message_handler.start()

    # PulseCoordinator now fully operational
    daemons = {
        "LoreTriggerWatcher": lore_trigger_watcher,
        "MessageHandler": message_handler
    }
    pulse_coordinator = PulseCoordinator(
        state_manager=state_manager,
        memory_daemon=memory_daemon,
        daemons=daemons,
        interval=5
    )
    pulse_coordinator.register_observer(status_bar.handle_pulse_update) # Ensure status_bar is defined or imported correctly
    pulse_coordinator.start()

    # Fire up Judy's chat agent
    # Agent is created first, then gui_callback is set in launch_test_gui
    agent = JalenAgent(memory_daemon, state_manager)
    # agent.start_chatbox()  # Disabled for test GUI

    gui_thread = threading.Thread(target=launch_test_gui, args=(agent,), daemon=True)
    gui_thread.start()

    print("[🌹] Judy’s system is live. Daemons humming. Pulse beating. Let’s ride.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[System] Shutdown requested.")
        agent.stop()
        memory_daemon.stop()
        lore_trigger_watcher.stop()
        message_handler.stop()
        pulse_coordinator.stop()
    finally:
        remove_pid()

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "start":
        main()
    elif len(sys.argv) == 2 and sys.argv[1] == "stop":
        pid = read_pid()
        if pid:
            try:
                # Windows: use os.kill with signal.CTRL_BREAK_EVENT
                if os.name == 'nt':
                    import ctypes
                    handle = ctypes.windll.kernel32.OpenProcess(1, 0, pid)
                    ctypes.windll.kernel32.GenerateConsoleCtrlEvent(1, pid)
                    ctypes.windll.kernel32.CloseHandle(handle)
                else:
                    os.kill(pid, signal.SIGINT)
                print(f"[System] Sent stop signal to process {pid}.")
                remove_pid()
            except Exception as e:
                print(f"[System] Could not stop process {pid}: {e}")
        else:
            print("[System] No running app found.")
    else:
        print("Usage: python main.py [start|stop]")
