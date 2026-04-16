import os
import random

from ..config import Config
from ..db import get_latest_emotion, get_latest_profile
from ..services.deepseek_client import DeepSeekClient
from ..services.iflytek_client import IFlytekClient
from ..services.prompts import MINDFULNESS_PROMPT


deepseek = DeepSeekClient()
iflytek = IFlytekClient()
MIN_SCRIPT_CHARS = 150
MAX_SCRIPT_CHARS = 300


def _clip_script(text: str, max_chars: int = MAX_SCRIPT_CHARS) -> str:
    script = (text or '').strip()
    if len(script) <= max_chars:
        return script
    for marker in ('。', '！', '？', '.', '!', '?', '\n'):
        idx = script.rfind(marker, 0, max_chars + 1)
        if idx >= int(max_chars * 0.65):
            return script[: idx + 1].strip()
    return script[:max_chars].rstrip() + '…'


def generate_mindfulness_text(user_id: int, session_id: str | None = None) -> str:
    profile = get_latest_profile(user_id, session_id) or {}
    emotion = get_latest_emotion(user_id, session_id) or {}
    prompt = MINDFULNESS_PROMPT.format(profile=profile, emotion=emotion)
    messages = [
        {'role': 'system', 'content': '你是正念呼吸引导师。'},
        {'role': 'user', 'content': prompt},
    ]
    script = deepseek.chat(messages, temperature=0.4)
    if not script or script.startswith('（未配置') or script.startswith('（当前无法连接'):
        return ''
    script = script.strip()

    if len(script) < MIN_SCRIPT_CHARS:
        expand_prompt = (
            '请将下面这段正念呼吸引导词扩写为150-300字，语气保持温和、稳定、可跟随，不要添加标题或编号。\n\n'
            f'原文：{script}\n\n'
            f'用户画像：{profile}\n情绪分析：{emotion}\n\n'
            '仅输出扩写后的引导词文本。'
        )
        expanded = deepseek.chat(
            [
                {'role': 'system', 'content': '你是正念呼吸引导师。'},
                {'role': 'user', 'content': expand_prompt},
            ],
            temperature=0.4,
        )
        if expanded and not expanded.startswith('（未配置') and not expanded.startswith('（当前无法连接'):
            script = expanded.strip()

    return _clip_script(script, MAX_SCRIPT_CHARS)


def build_mindfulness_audio(script: str) -> tuple[str | None, str | None]:
    tts_path = iflytek.synthesize(script) if script else None
    return tts_path, pick_music()


def generate_mindfulness_guidance(user_id: int, session_id: str | None = None) -> tuple[str, str | None, str | None]:
    script = generate_mindfulness_text(user_id, session_id)
    tts_path, music_path = build_mindfulness_audio(script)
    return script, tts_path, music_path


def pick_music() -> str | None:
    if not os.path.isdir(Config.MUSIC_DIR):
        return None
    files = [
        f
        for f in os.listdir(Config.MUSIC_DIR)
        if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac'))
    ]
    if not files:
        return None
    return os.path.join(Config.MUSIC_DIR, random.choice(files))


def get_last_tts_error() -> str:
    return (iflytek.last_error or '').strip()
