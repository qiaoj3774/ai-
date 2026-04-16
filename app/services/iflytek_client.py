import base64
import datetime
import hashlib
import hmac
import json
import os
from urllib.parse import urlencode, urlparse

import numpy as np
import websocket

from .utils import chunk_bytes
from ..config import Config


class IFlytekClient:
    def __init__(self) -> None:
        self.app_id = Config.IFLYTEK_APP_ID
        self.api_key = self._normalize_api_key(Config.IFLYTEK_API_KEY)
        self.api_secret = Config.IFLYTEK_API_SECRET
        self.tts_voice = Config.IFLYTEK_TTS_VOICE
        self.tts_speed = self._clamp_0_100(Config.IFLYTEK_TTS_SPEED)
        self.tts_pitch = self._clamp_0_100(Config.IFLYTEK_TTS_PITCH)
        self.tts_volume = self._clamp_0_100(Config.IFLYTEK_TTS_VOLUME)
        self.stt_url = Config.IFLYTEK_STT_URL
        self.tts_url = Config.IFLYTEK_TTS_URL
        self.stt_language = Config.IFLYTEK_STT_LANGUAGE
        self.stt_accent = Config.IFLYTEK_STT_ACCENT
        self.last_error = ''

    def _set_error(self, message: str) -> None:
        self.last_error = (message or '').strip()

    def _clamp_0_100(self, value: int | str, default: int = 50) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        return max(0, min(100, number))

    def _normalize_api_key(self, raw_key: str) -> str:
        key = (raw_key or '').strip()
        if not key:
            return ''
        try:
            decoded = base64.b64decode(key, validate=True).decode('utf-8').strip()
        except Exception:
            return key

        # Some deployments accidentally store APIKey in base64 form.
        if decoded and all(ch in '0123456789abcdefABCDEF' for ch in decoded):
            return decoded
        return key

    def _error_message(self, resp: dict) -> str:
        code = resp.get('code', -1)
        message = resp.get('message') or resp.get('msg') or 'unknown error'
        sid = resp.get('sid')
        if sid:
            return f'code={code}, message={message}, sid={sid}'
        return f'code={code}, message={message}'

    def _signed_url(self, raw_url: str) -> str:
        if not self.api_key or not self.api_secret:
            return raw_url
        parsed = urlparse(raw_url)
        host = parsed.hostname
        path = parsed.path

        now = datetime.datetime.utcnow()
        date = now.strftime('%a, %d %b %Y %H:%M:%S GMT')
        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_sha).decode('utf-8')

        authorization_origin = (
            f'api_key="{self.api_key}", '
            'algorithm="hmac-sha256", '
            'headers="host date request-line", '
            f'signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        params = {
            'authorization': authorization,
            'date': date,
            'host': host,
        }
        return f"{parsed.scheme}://{host}{path}?{urlencode(params)}"

    def _prepare_audio(self, audio: np.ndarray, sample_rate: int, target_rate: int = 16000) -> tuple[bytes, int]:
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        if sample_rate != target_rate:
            x = np.linspace(0, len(audio), num=len(audio), endpoint=False)
            new_len = int(len(audio) * (target_rate / sample_rate))
            x_new = np.linspace(0, len(audio), num=new_len, endpoint=False)
            audio = np.interp(x_new, x, audio)
            sample_rate = target_rate

        if audio.dtype != np.int16:
            audio = np.clip(audio, -1.0, 1.0)
            audio = (audio * 32767).astype(np.int16)

        return audio.tobytes(), sample_rate

    def _stt_business(self) -> dict:
        business = {
            'domain': 'iat',
            'language': self.stt_language,
            'vad_eos': 10000,
            'dwa': 'wpgs',
        }
        if self.stt_language == 'zh_cn' and self.stt_accent:
            business['accent'] = self.stt_accent
        return business

    def _extract_sentence(self, result: dict) -> str:
        words: list[str] = []
        for item in result.get('ws', []):
            for cw in item.get('cw', []):
                token = (cw.get('w') or '').strip()
                if token:
                    words.append(token)
        return ''.join(words)

    def _apply_wpgs_segment(self, segments: list[str], result: dict, sentence: str) -> None:
        if not sentence:
            return
        pgs = result.get('pgs')
        rg = result.get('rg')
        if pgs == 'rpl' and isinstance(rg, list) and len(rg) == 2:
            start = max(0, int(rg[0]) - 1)
            end = max(start, int(rg[1]) - 1)
            if start >= len(segments):
                segments.append(sentence)
                return
            segments[start : end + 1] = [sentence]
            return
        segments.append(sentence)

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """iFlytek speech-to-text: returns plain text, empty string on failure."""
        self._set_error('')
        if not self.app_id:
            self._set_error('IFLYTEK_APP_ID is missing.')
            return ''
        if audio is None:
            self._set_error('No audio input.')
            return ''

        try:
            url = self._signed_url(self.stt_url)
            ws = websocket.create_connection(url, timeout=10)
            ws.settimeout(8)
        except Exception as exc:
            self._set_error(f'STT connect failed: {exc}')
            return ''

        text_segments: list[str] = []
        audio_bytes, rate = self._prepare_audio(audio, sample_rate)
        frames = chunk_bytes(audio_bytes, 1280)
        if not frames:
            ws.close()
            self._set_error('Audio is empty after preprocessing.')
            return ''

        common = {'app_id': self.app_id}
        business = self._stt_business()

        try:
            # Send all audio frames first; server may return partials asynchronously.
            for index, frame in enumerate(frames):
                status = 0 if index == 0 else 1
                if index == len(frames) - 1:
                    status = 2
                data = {
                    'status': status,
                    'format': f'audio/L16;rate={rate}',
                    'encoding': 'raw',
                    'audio': base64.b64encode(frame).decode('utf-8'),
                }
                payload = {'common': common, 'business': business, 'data': data}
                ws.send(json.dumps(payload))

            timeout_hits = 0
            while True:
                try:
                    resp_raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    timeout_hits += 1
                    if timeout_hits >= 2:
                        break
                    continue

                resp = json.loads(resp_raw)
                if resp.get('code', 0) != 0:
                    self._set_error(f'STT failed: {self._error_message(resp)}')
                    return ''

                result = resp.get('data', {}).get('result') or {}
                sentence = self._extract_sentence(result)
                self._apply_wpgs_segment(text_segments, result, sentence)

                if resp.get('data', {}).get('status') == 2:
                    break
        except Exception as exc:
            self._set_error(f'STT runtime failed: {exc}')
            return ''
        finally:
            ws.close()

        text = ''.join(text_segments).strip()
        if not text and not self.last_error:
            self._set_error('STT completed but no text recognized.')
        return text

    def synthesize(self, text: str) -> str | None:
        """iFlytek text-to-speech: returns local audio path, None on failure."""
        self._set_error('')
        text = (text or '').strip()
        if not self.app_id:
            self._set_error('IFLYTEK_APP_ID is missing.')
            return None
        if not text:
            self._set_error('Input text is empty.')
            return None

        try:
            url = self._signed_url(self.tts_url)
            ws = websocket.create_connection(url, timeout=10)
        except Exception as exc:
            self._set_error(f'TTS connect failed: {exc}')
            return None

        payload = {
            'common': {'app_id': self.app_id},
            'business': {
                'aue': 'lame',
                'auf': 'audio/L16;rate=16000',
                'vcn': self.tts_voice,
                'speed': self.tts_speed,
                'pitch': self.tts_pitch,
                'volume': self.tts_volume,
                'tte': 'utf8',
            },
            'data': {
                'status': 2,
                'text': base64.b64encode(text.encode('utf-8')).decode('utf-8'),
            },
        }

        audio_bytes = b''
        try:
            ws.send(json.dumps(payload))
            while True:
                resp_raw = ws.recv()
                resp = json.loads(resp_raw)
                if resp.get('code', 0) != 0:
                    self._set_error(f'TTS failed: {self._error_message(resp)}')
                    return None
                data = resp.get('data', {})
                if 'audio' in data:
                    audio_bytes += base64.b64decode(data['audio'])
                if data.get('status') == 2:
                    break
        except Exception as exc:
            self._set_error(f'TTS runtime failed: {exc}')
            return None
        finally:
            ws.close()

        if not audio_bytes:
            self._set_error('TTS returned empty audio bytes.')
            return None

        os.makedirs(Config.GENERATED_DIR, exist_ok=True)
        filename = f"tts_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.mp3"
        path = os.path.join(Config.GENERATED_DIR, filename)
        with open(path, 'wb') as file_obj:
            file_obj.write(audio_bytes)
        return path
