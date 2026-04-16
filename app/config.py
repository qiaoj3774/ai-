import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env at project root
load_dotenv(BASE_DIR / '.env')


class Config:
    # Core
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
    DEBUG = os.getenv('DEBUG', 'False').lower() in {'1', 'true', 'yes'}
    PORT = int(os.getenv('PORT', '5000'))

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{(BASE_DIR / 'therapy_users.db').as_posix()}")

    # DeepSeek
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    DEEPSEEK_TIMEOUT_SEC = int(os.getenv('DEEPSEEK_TIMEOUT_SEC', '35'))

    # iFLYTEK
    IFLYTEK_APP_ID = os.getenv('IFLYTEK_APP_ID', '')
    IFLYTEK_API_KEY = os.getenv('IFLYTEK_API_KEY', '')
    IFLYTEK_API_SECRET = os.getenv('IFLYTEK_API_SECRET', '')
    IFLYTEK_TTS_VOICE = os.getenv('IFLYTEK_TTS_VOICE', 'x4_yezi')
    IFLYTEK_TTS_SPEED = int(os.getenv('IFLYTEK_TTS_SPEED', '35'))
    IFLYTEK_TTS_PITCH = int(os.getenv('IFLYTEK_TTS_PITCH', '45'))
    IFLYTEK_TTS_VOLUME = int(os.getenv('IFLYTEK_TTS_VOLUME', '50'))
    IFLYTEK_STT_LANGUAGE = os.getenv('IFLYTEK_STT_LANGUAGE', 'zh_cn')
    IFLYTEK_STT_ACCENT = os.getenv('IFLYTEK_STT_ACCENT', 'mandarin')
    IFLYTEK_STT_URL = os.getenv('IFLYTEK_STT_URL', 'wss://iat-api.xfyun.cn/v2/iat')
    IFLYTEK_TTS_URL = os.getenv('IFLYTEK_TTS_URL', 'wss://tts-api.xfyun.cn/v2/tts')

    # App settings
    TRIGGER_STEP = int(os.getenv('TRIGGER_STEP', '250'))
    MAX_EMOTIONS = int(os.getenv('MAX_EMOTIONS', '5'))

    # Assets
    MUSIC_DIR = str(BASE_DIR / 'assets' / 'music')
    GENERATED_DIR = str(BASE_DIR / 'assets' / 'generated')
