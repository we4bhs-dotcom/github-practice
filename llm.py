import requests
import json

class OllamaLLM:
    def __init__(self, model_name: str = "llama3.2"):
        self.model_name = model_name
        self.base_url = "http://localhost:11434"

    def generate(self, prompt: str) -> str:
        data = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(
            url=self.base_url + "/api/generate",
            data=json.dumps(data),
            timeout=60
        )
        return response.json()["response"]