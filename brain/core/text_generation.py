import threading
from llama_cpp import Llama

import os

class TextGeneration:
    def __init__(self, model_path=None, n_gpu_layers=20): # model_name arg removed, n_gpu_layers default restored
        self.model_path = model_path
        self.model = None
        self.lock = threading.Lock()
        self.n_gpu_layers = n_gpu_layers

        if self.model_path and os.path.exists(self.model_path):
            print(f"[TextGeneration] Loading model from {self.model_path}...")
            try:
                self.model = Llama(model_path=self.model_path, n_gpu_layers=self.n_gpu_layers)
                print("[TextGeneration] Model loaded successfully.")
            except Exception as e:
                print(f"[TextGeneration] Error loading model: {e}. Text generation will be disabled.")
                self.model = None
        elif self.model_path:
            print(f"[TextGeneration] Model path specified ({self.model_path}), but file not found. Text generation will be disabled.")
            self.model = None
        else:
            print("[TextGeneration] No model path specified. Text generation will be disabled.")
            self.model = None

    def generate(self, prompt, max_tokens=2500, temperature=0.7):
        with self.lock:
            if not self.model:
                return "[Text generation disabled: Model not loaded]"
            try:
                response = self.model(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response['choices'][0]['text']
            except Exception as e:
                return f"[Text generation error: {e}]"

    def generate_async(self, prompt, callback, max_tokens=2500, temperature=0.7):
        def worker():
            try:
                result = self.generate(prompt, max_tokens=max_tokens, temperature=temperature)
            except Exception as e:
                result = f"Error during generation: {str(e)}" # This outer try-except might be redundant now
            callback(result)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread

    def switch_model(self, new_model_path, n_gpu_layers=None):
        """
        Switch to a new Llama model at runtime.
        """
        with self.lock:
            if n_gpu_layers is None:
                n_gpu_layers = self.n_gpu_layers # Use existing n_gpu_layers if not specified

            if not new_model_path or not os.path.exists(new_model_path):
                print(f"[TextGeneration] Failed to switch model: Path '{new_model_path}' is invalid or file does not exist.")
                # Optionally, decide if self.model should be set to None or keep the old one
                # For now, let's keep the old model if switching fails
                return

            try:
                print(f"[TextGeneration] Switching to model: {new_model_path}")
                new_model_instance = Llama(model_path=new_model_path, n_gpu_layers=n_gpu_layers)
                self.model = new_model_instance
                self.model_path = new_model_path
                self.n_gpu_layers = n_gpu_layers # Update n_gpu_layers if a new model is successfully loaded
                print(f"[TextGeneration] Model switched successfully to {os.path.basename(new_model_path)}.")
            except Exception as e:
                print(f"[TextGeneration] Failed to switch model to {new_model_path}: {e}")
                # Keep the old model if switching fails