import threading
from llama_cpp import Llama

class TextGeneration:
    def __init__(self, model_path=None, model_name="mythomax-l2-13b.Q5_0.gguf"):
        self.model_path = model_path or "C:\\Users\\cnorthington\\xxJudy\\models\\mythomax-l2-13b.Q5_0.gguf"
        print(f"[TextGeneration] Loading model from {self.model_path} with GPU acceleration if available...")
        # Try to use GPU layers if supported by llama-cpp-python
        try:
            self.model = Llama(model_path=self.model_path, n_gpu_layers=20)  # Adjust n_gpu_layers as appropriate for your GPU
        except TypeError:
            # Fallback for older llama-cpp-python versions
            self.model = Llama(model_path=self.model_path)
        self.lock = threading.Lock()

    def generate(self, prompt, max_tokens=2500, temperature=0.7):
        with self.lock:
            response = self.model(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response['choices'][0]['text']

    def generate_async(self, prompt, callback, max_tokens=2500, temperature=0.7):
        def worker():
            try:
                result = self.generate(prompt, max_tokens=max_tokens, temperature=temperature)
            except Exception as e:
                result = f"Error during generation: {str(e)}"
            callback(result)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread

    def switch_model(self, model_path, n_gpu_layers=20):
        """
        Switch to a new Llama model at runtime.
        """
        with self.lock:
            try:
                print(f"[TextGeneration] Switching to model: {model_path}")
                from llama_cpp import Llama
                self.model = Llama(model_path=model_path, n_gpu_layers=n_gpu_layers)
                self.model_path = model_path
                print(f"[TextGeneration] Model switched successfully.")
            except Exception as e:
                print(f"[TextGeneration] Failed to switch model: {e}")