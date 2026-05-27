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
            "stream": False,
            "format": "json"  # 💡 Ollama에게 오직 JSON 형식으로만 출력하라고 강제하는 옵션이야!
        }
        try:
            response = requests.post(
                url=f"{self.base_url}/api/generate",
                headers={"Content-Type": "application/json"},
                data=json.dumps(data),
                timeout=60
            )
            response.raise_for_status() # HTTP 에러 체크 (4xx, 5xx)
            return response.json().get("response", "")
        except requests.exceptions.RequestException as e:
            print(f"[Ollama Error] 통신 실패: {e}")
            return f"Error: LLM 호출 실패 ({e})"