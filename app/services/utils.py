import json
import re
from typing import Any


def extract_json_from_text(text: str) -> str | None:
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*', '', text).strip()
        text = text.strip('`').strip()
    # Try direct
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    # Find first JSON object
    match = re.search(r'\{.*\}', text, re.S)
    if match:
        return match.group(0)
    return None


def safe_json_loads(text: str, fallback: Any = None) -> Any:
    if text is None:
        return fallback
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        extracted = extract_json_from_text(text)
        if extracted:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                return fallback
        return fallback


def chunk_bytes(data: bytes, chunk_size: int) -> list[bytes]:
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
