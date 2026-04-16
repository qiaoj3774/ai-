from typing import Tuple

from ..config import Config
from ..db import (
    bump_trigger,
    get_latest_emotion,
    get_latest_profile,
    list_recent_messages,
    save_chat_message,
    save_emotion_record,
    save_recommendation,
    update_user_state,
    upsert_profile,
)
from ..services.deepseek_client import DeepSeekClient
from ..services.prompts import (
    CHAT_REPLY_PROMPT,
    CHAT_REPLY_REWRITE_PROMPT,
    EMOTION_ANALYSIS_PROMPT,
    PROFILE_UPDATE_PROMPT,
    RECOMMENDATION_BRIDGE_PROMPT,
    RECOMMENDATION_PREFACE_PROMPT,
    SYSTEM_THERAPIST,
)
from ..services.recommendation import recommend_module


client = DeepSeekClient()


PROFILE_QUESTIONS = [
    (
        'age',
        '\u4e3a\u4e86\u66f4\u597d\u5730\u8d34\u8fd1\u4f60\u7684\u89c6\u89d2\uff0c\u5982\u679c\u65b9\u4fbf\u7684\u8bdd\uff0c\u53ef\u4ee5\u544a\u8bc9\u6211\u4f60\u5927\u6982\u5904\u5728\u54ea\u4e2a\u5e74\u9f84\u9636\u6bb5\u5417\uff1f\n'
        "In order to better align with your perspective, if it's convenient for you, "
        'could you please tell me approximately which age group you belong to?',
    ),
    (
        'occupation',
        '\u53e6\u5916\uff0c\u6211\u4e5f\u60f3\u4e86\u89e3\u4e00\u4e0b\u4f60\u76ee\u524d\u7684\u751f\u6d3b\u91cd\u5fc3\uff0c\u6bd4\u5982\u662f\u5728\u4e0a\u5b66\u3001\u5de5\u4f5c\uff0c\u8fd8\u662f\u5176\u4ed6\u7684\u72b6\u6001\uff1f\u6309\u7167\u4f60\u8212\u670d\u7684\u8282\u594f\u8bf4\u5c31\u53ef\u4ee5\u3002\n'
        'Additionally, I would also like to know what your current priorities in life are, '
        'such as being at school, working, or in some other state? '
        'You can simply describe it in a way that suits your own pace.',
    ),
    (
        'current_emotion',
        '\u5982\u679c\u4f60\u613f\u610f\uff0c\u4e5f\u53ef\u4ee5\u7528\u51e0\u4e2a\u8bcd\u63cf\u8ff0\u4e00\u4e0b\u4f60\u6b64\u523b\u6700\u660e\u663e\u7684\u60c5\u7eea\u5417\uff1f\u6bd4\u5982\u96be\u8fc7\u3001\u7126\u8651\u3001\u59d4\u5c48\u3001\u70e6\u8e81\uff0c\u6216\u8005\u522b\u7684\u611f\u53d7\u3002\n'
        'If you are willing, could you also use a few words to describe the strongest emotions you are feeling right now, '
        'such as sadness, anxiety, hurt, irritability, or anything else?',
    ),
    (
        'stressor',
        '\u5982\u679c\u4f60\u613f\u610f\uff0c\u53ef\u4ee5\u544a\u8bc9\u6211\u6700\u8fd1\u6700\u4e3b\u8981\u7684\u538b\u529b\u6765\u6e90\u5417\uff1f\uff08\u6bd4\u5982\u6765\u81ea\u5b66\u4e60/\u5de5\u4f5c/\u4eba\u9645/\u5176\u4ed6\uff09\u3002\n'
        'If you would like, could you tell me the main source of your stress recently? '
        '(For example, from studies, work, relationships, or something else.)',
    ),
    (
        'healing_preference',
        '\u5728\u5e73\u65f6\uff0c\u4f60\u66f4\u559c\u6b22\u7528\u4ec0\u4e48\u65b9\u5f0f\u5e2e\u52a9\u81ea\u5df1\u7f13\u4e00\u7f13\u3001\u6574\u7406\u60c5\u7eea\u5462\uff1f\uff08\u6bd4\u5982\u547c\u5438\u7ec3\u4e60\u3001\u5199\u4e0b\u6765\u3001\u804a\u5929\u3001\u6563\u6b65\uff0c\u6216\u8005\u522b\u7684\u65b9\u6cd5\uff09\u3002\n'
        'In daily life, what way do you usually prefer to help yourself slow down and sort through emotions? '
        '(For example, breathing exercises, writing, talking, walking, or some other method.)',
    ),
]

QUESTION_HINTS = {
    'age': ('\u5e74\u9f84\u9636\u6bb5', '\u66f4\u4e86\u89e3\u4f60\u4e00\u70b9', 'age range', 'high school', 'college'),
    'occupation': ('\u73b0\u5728\u7684\u72b6\u6001', '\u4e0a\u5b66/\u5de5\u4f5c/\u5176\u4ed6', 'current situation', 'school/work'),
    'current_emotion': ('\u6b64\u523b\u7684\u60c5\u7eea', '\u96be\u8fc7/\u7126\u8651/\u70e6\u8e81', 'current emotion', 'sadness', 'anxiety'),
    'stressor': ('\u538b\u529b\u6765\u6e90', '\u5b66\u4e60/\u5de5\u4f5c/\u4eba\u9645', 'main source of your stress'),
    'healing_preference': ('\u7f13\u89e3\u65b9\u5f0f', '\u547c\u5438\u7ec3\u4e60/\u5199\u4e0b\u6765/\u6563\u6b65', 'preferred coping method'),
}

UNKNOWN_VALUES = {'', 'unknown', '\u672a\u77e5', '\u672a\u63d0\u4f9b', 'none', 'null'}
MAX_PROFILE_FOLLOWUPS = len(PROFILE_QUESTIONS)
ANALYSIS_TIMEOUT_SEC = 8
PROFILE_TIMEOUT_SEC = 8
REPLY_TIMEOUT_SEC = 18
REPLY_REWRITE_TIMEOUT_SEC = 10
RECOMMENDATION_TIMEOUT_SEC = 12
REPLY_CHAR_LIMIT = 600
PROFILE_FOLLOWUP_SEQUENCE = [question for _, question in PROFILE_QUESTIONS]


def _build_conversation_text(messages: list[dict]) -> str:
    return '\n'.join([f"{m['role']}: {m['content']}" for m in messages])


def analyze_emotion(conversation: str, timeout_sec: int | None = None) -> dict:
    prompt = EMOTION_ANALYSIS_PROMPT.format(conversation=conversation)
    messages = [
        {'role': 'system', 'content': SYSTEM_THERAPIST},
        {'role': 'user', 'content': prompt},
    ]
    result = client.chat_json(messages, timeout_sec=timeout_sec)
    return _normalize_emotions(result)


def update_profile(conversation: str, profile: dict | None, emotion: dict | None, timeout_sec: int | None = None) -> dict:
    prompt = PROFILE_UPDATE_PROMPT.format(profile=profile or {}, emotion=emotion or {}, conversation=conversation)
    messages = [
        {'role': 'system', 'content': SYSTEM_THERAPIST},
        {'role': 'user', 'content': prompt},
    ]
    return client.chat_json(messages, timeout_sec=timeout_sec)


def generate_reply(conversation: str, profile: dict | None, emotion: dict | None, timeout_sec: int | None = None) -> str:
    prompt = CHAT_REPLY_PROMPT.format(profile=profile or {}, emotion=emotion or {}, conversation=conversation)
    messages = [
        {'role': 'system', 'content': SYSTEM_THERAPIST},
        {'role': 'user', 'content': prompt},
    ]
    return client.chat(messages, temperature=0.6, timeout_sec=timeout_sec)


def generate_recommendation_preface(
    conversation: str,
    profile: dict | None,
    emotion: dict | None,
    timeout_sec: int | None = None,
) -> str:
    prompt = RECOMMENDATION_PREFACE_PROMPT.format(
        conversation=conversation,
        profile=profile or {},
        emotion=emotion or {},
    )
    messages = [
        {'role': 'system', 'content': SYSTEM_THERAPIST},
        {'role': 'user', 'content': prompt},
    ]
    return client.chat(messages, temperature=0.4, timeout_sec=timeout_sec)


def rewrite_reply_bilingually(
    draft: str,
    conversation: str,
    profile: dict | None,
    emotion: dict | None,
    timeout_sec: int | None = None,
) -> str:
    prompt = CHAT_REPLY_REWRITE_PROMPT.format(
        draft=draft or '',
        conversation=conversation,
        profile=profile or {},
        emotion=emotion or {},
    )
    messages = [
        {'role': 'system', 'content': SYSTEM_THERAPIST},
        {'role': 'user', 'content': prompt},
    ]
    return client.chat(messages, temperature=0.4, timeout_sec=timeout_sec)


def generate_recommendation_bridge(
    conversation: str,
    module: str,
    reason: str,
    profile: dict | None,
    emotion: dict | None,
    timeout_sec: int | None = None,
) -> str:
    module_name = '练习室（正念呼吸）' if module == 'mindfulness' else '日记（表达性写作）'
    prompt = RECOMMENDATION_BRIDGE_PROMPT.format(
        module=module_name,
        reason=reason,
        profile=profile or {},
        emotion=emotion or {},
        conversation=conversation,
    )
    messages = [
        {'role': 'system', 'content': SYSTEM_THERAPIST},
        {'role': 'user', 'content': prompt},
    ]
    return client.chat(messages, temperature=0.6, timeout_sec=timeout_sec)


def _count_profile_followups(messages: list[dict]) -> int:
    # Count only the fixed follow-up sequence in order, so free-form AI questions
    # will not accidentally advance or skip the 5-step profile form.
    seq_index = 0
    for msg in messages:
        if msg.get('role') != 'assistant':
            continue
        if seq_index >= len(PROFILE_FOLLOWUP_SEQUENCE):
            break
        content = msg.get('content') or ''
        if PROFILE_FOLLOWUP_SEQUENCE[seq_index] in content:
            seq_index += 1
    return seq_index


def _next_profile_question(profile: dict | None, messages: list[dict]) -> str:
    _ = profile
    count = _count_profile_followups(messages)
    if count >= MAX_PROFILE_FOLLOWUPS:
        return ''
    return PROFILE_FOLLOWUP_SEQUENCE[count]


def _fixed_jump_prompt(module: str) -> str:
    if module == 'mindfulness':
        return (
            '如果你愿意，我们现在可以直接进入“练习室”。\n'
            'If you would like, we can jump to the Practice Room right now.'
        )
    return (
        '如果你愿意，我们现在可以直接进入“日记”。\n'
        'If you would like, we can jump to Journal right now.'
    )


def _fallback_recommendation_bridge(module: str, reason: str) -> str:
    module_name = '练习室（正念呼吸）' if module == 'mindfulness' else '日记（表达性写作）'
    return (
        f'结合你刚才的分享，我更推荐你先试试{module_name}，这样会更贴近你现在的状态（{reason}）。\n'
        f'Based on what you shared, I recommend trying {module_name} first, '
        f'as it better matches your current state ({reason}).'
    )


def _clip_at_sentence(text: str, max_chars: int) -> str:
    content = (text or '').strip()
    if max_chars <= 0:
        return ''
    if len(content) <= max_chars:
        return content

    punctuation = ['。', '！', '？', '.', '!', '?', '\n']
    threshold = max(20, int(max_chars * 0.62))
    for marker in punctuation:
        idx = content.rfind(marker, 0, max_chars + 1)
        if idx >= threshold:
            return content[: idx + 1].strip()

    return content[:max_chars].rstrip()


def _split_bilingual_pairs(text: str) -> list[tuple[str, str]]:
    lines = _nonempty_lines(text)
    if len(lines) < 2 or len(lines) % 2 != 0:
        return []

    pairs: list[tuple[str, str]] = []
    for index in range(0, len(lines), 2):
        zh_line = lines[index]
        en_line = lines[index + 1]
        if not _has_cjk(zh_line) or not _looks_english_line(en_line):
            return []
        pairs.append((zh_line, en_line))
    return pairs


def _clip_bilingual_text(text: str, max_chars: int, min_pairs: int = 1) -> str:
    if max_chars <= 0:
        return ''

    pairs = _split_bilingual_pairs(text)
    if not pairs:
        return _clip_at_sentence(text, max_chars)

    selected: list[str] = []
    total_len = 0
    for zh_line, en_line in pairs:
        pair_text = f"{zh_line}\n{en_line}".strip()
        addition = len(pair_text) if not selected else len(pair_text) + 2
        if selected and total_len + addition > max_chars:
            break
        if not selected and len(pair_text) > max_chars:
            return pair_text
        selected.append(pair_text)
        total_len += addition

    if len(selected) >= min_pairs:
        return '\n\n'.join(selected)

    first_pair = f"{pairs[0][0]}\n{pairs[0][1]}".strip()
    return first_pair if len(first_pair) <= max_chars or min_pairs <= 1 else _clip_at_sentence(text, max_chars)


def _compose_reply_with_follow_up(main_reply: str, follow_up: str) -> str:
    tail = (follow_up or '').strip()
    body_budget = max(80, REPLY_CHAR_LIMIT - len(tail) - 2)
    body = _clip_bilingual_text(main_reply, body_budget, min_pairs=1)
    if tail:
        return f"{body}\n\n{tail}".strip()
    return _clip_bilingual_text(body, REPLY_CHAR_LIMIT, min_pairs=1)


def _compose_reply_with_recommendation(main_reply: str, bridge: str, jump_prompt: str) -> str:
    jump = (jump_prompt or '').strip()
    bridge_text = _clip_bilingual_text(bridge, 220, min_pairs=1)
    body_budget = max(120, REPLY_CHAR_LIMIT - len(bridge_text) - len(jump) - 4)
    body = _clip_bilingual_text(main_reply, body_budget, min_pairs=1)
    merged = f"{body}\n\n{bridge_text}\n\n{jump}".strip()
    if len(merged) <= REPLY_CHAR_LIMIT:
        return merged

    # Guarantee jump prompt visibility while keeping bilingual pairs intact.
    bridge_text = _clip_bilingual_text(bridge_text, 170, min_pairs=1)
    body_budget = max(100, REPLY_CHAR_LIMIT - len(bridge_text) - len(jump) - 4)
    body = _clip_bilingual_text(body, body_budget, min_pairs=1)
    merged = f"{body}\n\n{bridge_text}\n\n{jump}".strip()
    if len(merged) <= REPLY_CHAR_LIMIT:
        return merged

    bridge_budget = max(40, REPLY_CHAR_LIMIT - len(body) - len(jump) - 4)
    bridge_text = _clip_bilingual_text(bridge_text, bridge_budget, min_pairs=1)
    merged = f"{body}\n\n{bridge_text}\n\n{jump}".strip()
    if len(merged) <= REPLY_CHAR_LIMIT:
        return merged

    body_budget = max(60, REPLY_CHAR_LIMIT - len(jump) - 2)
    body = _clip_bilingual_text(body, body_budget, min_pairs=1)
    return f"{body}\n\n{jump}".strip()


def _nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or '').replace('\r\n', '\n').split('\n') if line.strip()]


def _has_cjk(text: str) -> bool:
    return any('\u4e00' <= char <= '\u9fff' for char in text or '')


def _looks_english_line(text: str) -> bool:
    letters = sum(1 for char in text if ('a' <= char.lower() <= 'z'))
    cjk_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    return letters >= 6 and cjk_chars <= 2


def _has_bilingual_pairs(reply: str, min_pairs: int = 1) -> bool:
    lines = _nonempty_lines(reply)
    if len(lines) < min_pairs * 2 or len(lines) % 2 != 0:
        return False
    for index in range(0, len(lines), 2):
        zh_line = lines[index]
        en_line = lines[index + 1]
        if not _has_cjk(zh_line):
            return False
        if not _looks_english_line(en_line):
            return False
    return True


def _needs_bilingual_rewrite(reply: str) -> bool:
    return not _has_bilingual_pairs(reply, min_pairs=2)


def _needs_single_bilingual_pair(reply: str) -> bool:
    return not _has_bilingual_pairs(reply, min_pairs=1)


def _is_model_error_reply(reply: str) -> bool:
    content = (reply or '').strip()
    return not content or content.startswith('\uff08\u672a\u914d\u7f6e') or content.startswith('\uff08\u5f53\u524d\u65e0\u6cd5\u8fde\u63a5')


def process_user_message(user_id: int, session_id: str, text: str) -> Tuple[str, dict | None, dict | None, dict | None]:
    save_chat_message(user_id, session_id, 'user', text)
    state = update_user_state(user_id, session_id, len(text))

    history = list_recent_messages(user_id, session_id, limit=14)
    profile_history = list_recent_messages(user_id, session_id, limit=200)
    conversation = _build_conversation_text(history)

    triggered = int(state.get('total_chars', 0)) >= int(state.get('next_trigger_at', Config.TRIGGER_STEP))

    profile = get_latest_profile(user_id, session_id)
    emotion = get_latest_emotion(user_id, session_id)
    recommendation: dict | None = None

    if triggered:
        emotion = analyze_emotion(conversation, timeout_sec=ANALYSIS_TIMEOUT_SEC)
        if emotion:
            emotions = emotion.get('emotions') or []
            secondary = emotions[1] if len(emotions) > 1 else {}
            save_emotion_record(
                user_id,
                session_id,
                emotion.get('primary_emotion', '\u672a\u77e5'),
                _to_int(emotion.get('primary_percent', 0)),
                json_dumps(emotion),
                secondary.get('emotion'),
                _to_int(secondary.get('percent', 0)) if secondary else None,
            )

        profile_data = update_profile(conversation, profile, emotion, timeout_sec=PROFILE_TIMEOUT_SEC)
        if profile_data:
            upsert_profile(
                user_id,
                session_id,
                profile_data.get('age', '\u672a\u77e5'),
                profile_data.get('occupation', '\u672a\u77e5'),
                profile_data.get('current_emotion', emotion.get('primary_emotion', '\u672a\u77e5') if emotion else '\u672a\u77e5'),
                profile_data.get('stressor', '\u672a\u77e5'),
                profile_data.get('healing_preference', '\u672a\u77e5'),
            )
            profile = get_latest_profile(user_id, session_id)

        bump_trigger(user_id, session_id)

        rec = recommend_module(profile, emotion)
        if rec:
            module, reason = rec
            save_recommendation(user_id, session_id, module, reason)
            recommendation = {'module': module, 'reason': reason}

    if recommendation:
        reply = generate_recommendation_preface(conversation, profile, emotion, timeout_sec=REPLY_TIMEOUT_SEC)
        if _is_model_error_reply(reply) or _needs_single_bilingual_pair(reply):
            reply = (
                '\u8c22\u8c22\u4f60\u613f\u610f\u7ee7\u7eed\u8bf4\u4e0b\u53bb\uff0c\u6211\u4f1a\u966a\u4f60\u4e00\u8d77\u628a\u8fd9\u4efd\u611f\u53d7\u5b89\u653e\u597d\u3002\n'
                'Thank you for continuing to share. I will stay with you and help hold this feeling with care.'
            )
    else:
        reply = generate_reply(conversation, profile, emotion, timeout_sec=REPLY_TIMEOUT_SEC)
        if _is_model_error_reply(reply):
            reply = (
                '\u8c22\u8c22\u4f60\u544a\u8bc9\u6211\u8fd9\u4e9b\uff0c\u6211\u542c\u89c1\u4e86\u4f60\u7684\u611f\u53d7\u3002\n'
                'Thank you for sharing this. I hear you.\n'
                '\u6211\u4eec\u53ef\u4ee5\u4e00\u6b65\u4e00\u6b65\u6765\uff0c\u4f60\u73b0\u5728\u6700\u9700\u8981\u7684\u662f\u653e\u677e\u3001\u503e\u8bc9\uff0c\u8fd8\u662f\u68b3\u7406\u95ee\u9898\uff1f\n'
                'We can go step by step. What do you need most now: relaxation, expression, or problem sorting?'
            )

        if _needs_bilingual_rewrite(reply):
            rewritten = rewrite_reply_bilingually(
                reply,
                conversation,
                profile,
                emotion,
                timeout_sec=REPLY_REWRITE_TIMEOUT_SEC,
            )
            if rewritten and not _is_model_error_reply(rewritten):
                reply = rewritten.strip()
        if _needs_bilingual_rewrite(reply):
            reply = (
                '\u8c22\u8c22\u4f60\u7ee7\u7eed\u544a\u8bc9\u6211\u8fd9\u4e9b\uff0c\u6211\u4f1a\u966a\u4f60\u628a\u73b0\u5728\u7684\u611f\u53d7\u4e00\u70b9\u70b9\u8bf4\u6e05\u695a\u3002\n'
                'Thank you for continuing to share this. I will stay with you and help you put these feelings into words step by step.\n'
                '\u5982\u679c\u4f60\u613f\u610f\uff0c\u53ef\u4ee5\u7ee7\u7eed\u8bf4\u8bf4\u6b64\u523b\u6700\u660e\u663e\u7684\u4e00\u79cd\u611f\u53d7\u662f\u4ec0\u4e48\u3002\n'
                'If you would like, you can keep going by naming the strongest feeling you notice right now.'
            )

    if recommendation:
        bridge = generate_recommendation_bridge(
            conversation,
            recommendation['module'],
            recommendation['reason'],
            profile,
            emotion,
            timeout_sec=RECOMMENDATION_TIMEOUT_SEC,
        )
        if not bridge or bridge.startswith('\uff08\u672a\u914d\u7f6e') or bridge.startswith('\uff08\u5f53\u524d\u65e0\u6cd5\u8fde\u63a5'):
            bridge = _fallback_recommendation_bridge(recommendation['module'], recommendation['reason'])
        jump_prompt = _fixed_jump_prompt(recommendation['module'])
        reply = _compose_reply_with_recommendation(reply, bridge, jump_prompt)
    else:
        follow_up = _next_profile_question(profile, profile_history)
        reply = _compose_reply_with_follow_up(reply, follow_up)

    save_chat_message(user_id, session_id, 'assistant', reply, emotion.get('primary_emotion') if emotion else None)
    return reply, recommendation, profile, emotion


def json_dumps(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False)


def _to_int(value, default: int = 0) -> int:
    import re

    try:
        return int(float(value))
    except (TypeError, ValueError):
        digits = re.findall(r'\d+', str(value))
        return int(digits[0]) if digits else default


def _normalize_emotions(emotion: dict) -> dict:
    if not emotion:
        return {}
    items = emotion.get('emotions') or []
    if not isinstance(items, list):
        return emotion

    cleaned = []
    for item in items:
        name = item.get('emotion')
        percent = _to_int(item.get('percent', 0))
        if name:
            cleaned.append({'emotion': name, 'percent': percent})

    cleaned.sort(key=lambda x: x['percent'], reverse=True)
    max_items = max(1, int(Config.MAX_EMOTIONS))
    cleaned = cleaned[:max_items]

    total = sum(c['percent'] for c in cleaned) or 1
    normalized = []
    running = 0
    for i, item in enumerate(cleaned):
        if i == len(cleaned) - 1:
            percent = max(0, 100 - running)
        else:
            percent = int(round(item['percent'] / total * 100))
            running += percent
        normalized.append({'emotion': item['emotion'], 'percent': percent})

    primary = normalized[0] if normalized else {'emotion': '\u672a\u77e5', 'percent': 0}
    emotion['primary_emotion'] = primary['emotion']
    emotion['primary_percent'] = primary['percent']
    emotion['emotions'] = normalized
    return emotion
