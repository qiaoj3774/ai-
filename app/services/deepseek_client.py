import json
import requests

from .utils import safe_json_loads
from ..config import Config


class DeepSeekClient:
    def __init__(self) -> None:
        self.api_key = Config.DEEPSEEK_API_KEY
        self.base_url = Config.DEEPSEEK_BASE_URL.rstrip('/')
        self.model = Config.DEEPSEEK_MODEL

    def _endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.6,
        json_mode: bool = False,
        timeout_sec: int | None = None,
    ) -> str:
        """统一的对话接口，支持JSON模式。"""
        if not self.api_key:
            return '（未配置DEEPSEEK_API_KEY，当前为本地演示回复）'

        payload: dict = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
        }
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}

        try:
            # DeepSeek REST API 调用
            response = requests.post(
                self._endpoint(),
                headers=self._headers(),
                data=json.dumps(payload),
                timeout=timeout_sec or Config.DEEPSEEK_TIMEOUT_SEC,
            )
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception:
            return '（当前无法连接到模型服务，请稍后重试）'

    def chat_json(self, messages: list[dict], temperature: float = 0.2, timeout_sec: int | None = None) -> dict:
        content = self.chat(messages, temperature=temperature, json_mode=True, timeout_sec=timeout_sec)
        parsed = safe_json_loads(content, fallback=None)
        if parsed is None:
            return {}
        return parsed
