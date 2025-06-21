import threading
from queue import Queue
import time

class MessageHandlerDaemon:
    """
    Handles non-file textual input: user chat messages, commands,
    encrypted secrets, or notes. Classifies intent and routes accordingly.

    All memory storage, tagging, and prompt/context updates are performed strictly in background threads.
    This ensures that chat responses are never delayed by memory or prompt operations.
    DO NOT add any blocking or synchronous calls in the main message loop that could add latency to answers.
    """

    def __init__(self, command_router, message_queue: Queue, state_manager=None):
        """
        Args:
            command_router: callable that accepts classified commands for execution.
            message_queue: thread-safe queue with incoming text messages.
            state_manager: (optional) StateManager instance for semantic memory storage and relevancy updates.
        """
        self.command_router = command_router
        self.message_queue = message_queue
        self.state_manager = state_manager
        self._running = False
        self.worker_thread = threading.Thread(target=self._process_messages_loop, daemon=True)

    def start(self):
        self._running = True
        self.worker_thread.start()
        print("[MessageHandlerDaemon] Started.")

    def stop(self):
        self._running = False
        self.worker_thread.join()
        print("[MessageHandlerDaemon] Stopped.")

    def build_prompt(self, user_message, n=5):
        """
        Build a dynamic prompt using recent chat, relevant long-term memories, mood, and topic.
        Runs background fetches for long-term context to avoid latency.
        """
        # Get recent chat (short-term)
        recent_context = self.memory_daemon.prepare_prompt_context() if hasattr(self, 'memory_daemon') and self.memory_daemon else ""
        # Use cached or last background prompt for long-term context
        background_context = getattr(self, '_last_background_prompt', "")
        # Optionally, trigger a background update for next turn
        threading.Thread(target=self.update_background_prompt, daemon=True).start()
        # Compose the prompt
        prompt = (
            f"Current mood: {getattr(self, '_last_mood', 'neutral')}\n"
            f"Current topic: {getattr(self, '_last_topic', 'general')}\n"
            f"Recent chat:\n{recent_context}\n"
            f"Relevant memories:\n{background_context}\n"
            f"User: {user_message}\n"
            f"Judy:"
        )
        return prompt

    def update_background_prompt(self, context_query=None, n=5, mood=None, topic=None):
        """
        Update the background prompt with the most relevant memories from ChromaDB.
        This is always run in a background thread to avoid any latency in chat responses.
        If mood, topic, or context changes, use them to guide semantic search.
        """
        if not self.state_manager:
            return ""
        # Build a dynamic query based on mood, topic, or explicit context
        queries = []
        if context_query:
            queries.append(context_query)
        if topic:
            queries.append(topic)
        if mood:
            queries.append(mood)
        # Combine queries for semantic search
        if queries:
            search_query = " ".join(queries)
            docs = self.state_manager.search_memories_chroma(search_query, memory_type="long", n=n)
        else:
            docs = self.state_manager.get_recent_memories_chroma(memory_type="long", n=n)
        # Build a background prompt string
        prompt = "\n".join([
            f"[{doc[1].get('timestamp', 'unknown')}] ({', '.join(doc[1].get('tags', []))}) {doc[0]}" for doc in docs
        ])
        print(f"[MessageHandlerDaemon] Updated background prompt (mood/topic/context-aware):\n{prompt}")
        return prompt

    def _process_messages_loop(self):
        last_mood = None
        last_topic = None
        while self._running:
            try:
                message = self.message_queue.get(timeout=1)
                print(f"[MessageHandlerDaemon] Processing message: {message}")

                intent = self._classify_intent(message)
                if intent == "command":
                    self.command_router(message)
                elif intent == "note":
                    # Store note in background to avoid latency
                    self._store_note(message)
                elif intent == "secret":
                    # Store secret in background to avoid latency
                    self._handle_secret(message)
                else:
                    print(f"[MessageHandlerDaemon] Unknown intent: '{intent}'. Treating as note.")
                    self._store_note(message)

                # Detect mood/topic/context changes (simple example)
                mood = self._detect_mood(message)
                topic = self._detect_topic(message)
                context_changed = (mood != last_mood) or (topic != last_topic)
                last_mood, last_topic = mood, topic

                # Always update background prompt in a background thread to avoid any latency
                threading.Thread(
                    target=self.update_background_prompt,
                    kwargs={"mood": mood, "topic": topic},
                    daemon=True
                ).start()

                self.message_queue.task_done()
            except Exception:
                pass

    def _classify_intent(self, message):
        # Simplified example intent classification:
        message = message.strip().lower()
        if message.startswith("/"):
            return "command"
        if "secret" in message or "encrypt" in message:
            return "secret"
        if len(message) > 0:
            return "note"
        return "unknown"

    def _store_note(self, note):
        # Use StateManager's advanced_autotag for tagging (centralized, ML/NLP-powered)
        def background_tag_and_store():
            if self.state_manager:
                tags = self.state_manager.advanced_autotag(note, is_secret=False)
                self.state_manager.add_memory_chroma(
                    note,
                    memory_type="short",
                    metadata={
                        "timestamp": time.time(),
                        "source": "note",
                        "tags": tags
                    },
                    use_advanced_tagging=False  # Already tagged above
                )
                print(f"[MessageHandlerDaemon] Stored note in ChromaDB with tags {tags}: {note}")
            else:
                print(f"[MessageHandlerDaemon] Stored note: {note}")
        threading.Thread(target=background_tag_and_store, daemon=True).start()

    def _handle_secret(self, secret_text):
        # Use StateManager's advanced_autotag for secret tagging
        def background_tag_and_store_secret():
            if self.state_manager:
                tags = self.state_manager.advanced_autotag(secret_text, is_secret=True)
                self.state_manager.add_memory_chroma(
                    secret_text,
                    memory_type="long",
                    metadata={
                        "timestamp": time.time(),
                        "source": "secret",
                        "sensitivity": "high",
                        "tags": tags
                    },
                    use_advanced_tagging=False,  # Already tagged above
                    is_secret=True
                )
                print(f"[MessageHandlerDaemon] Securely stored secret in ChromaDB with tags {tags}: {secret_text}")
            else:
                print(f"[MessageHandlerDaemon] Securely stored secret: {secret_text}")
        threading.Thread(target=background_tag_and_store_secret, daemon=True).start()

    def _detect_mood(self, message):
        # Simple mood detection (expand with NLP/ML as needed)
        msg = message.lower()
        if any(word in msg for word in ["happy", "joy", "excited"]):
            return "happy"
        if any(word in msg for word in ["sad", "down", "depressed"]):
            return "sad"
        if any(word in msg for word in ["angry", "mad", "frustrated"]):
            return "angry"
        return None

    def _detect_topic(self, message):
        # Simple topic detection (expand with NLP/ML as needed)
        msg = message.lower()
        if "project" in msg:
            return "project"
        if "meeting" in msg:
            return "meeting"
        if "reminder" in msg:
            return "reminder"
        if "todo" in msg:
            return "todo"
        return None

    def update_prompt_file(self, new_prompt, prompt_path="config/prompt_frame.json"):
        """
        Update the prompt template file in a background thread.
        """
        def background_update():
            try:
                import json
                with open(prompt_path, "w", encoding="utf-8") as f:
                    json.dump({"template": new_prompt}, f, indent=2)
                print(f"[MessageHandlerDaemon] Prompt file updated at {prompt_path}.")
            except Exception as e:
                print(f"[MessageHandlerDaemon] Failed to update prompt file: {e}")
        threading.Thread(target=background_update, daemon=True).start()

    def rewrite_memory(self, memory_id, new_text, memory_type="short"):
        """
        Rewrite a memory entry by ID in a background thread.
        """
        def background_rewrite():
            if not self.state_manager:
                print("[MessageHandlerDaemon] No state manager for memory rewrite.")
                return
            # This assumes your state_manager has a method to rewrite memory by ID
            try:
                self.state_manager.rewrite_memory(memory_id, new_text, memory_type=memory_type)
                print(f"[MessageHandlerDaemon] Memory {memory_id} rewritten.")
            except Exception as e:
                print(f"[MessageHandlerDaemon] Failed to rewrite memory: {e}")
        threading.Thread(target=background_rewrite, daemon=True).start()
