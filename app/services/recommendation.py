from typing import Tuple


ANXIETY_EMOTIONS = {'焦虑', '紧张', '恐惧', '压力', '担忧', '不安'}
SAD_EMOTIONS = {'悲伤', '委屈', '难过', '失落', '沮丧', '孤独'}


def recommend_module(profile: dict | None, emotion: dict | None) -> Tuple[str, str] | None:
    if profile:
        preference = (profile.get('healing_preference') or '').strip()
        if preference in {'正念呼吸', '正念', '呼吸'}:
            return 'mindfulness', '用户偏好正念呼吸/ User preference for mindfulness breathing'
        if preference in {'表达性写作', '写作', '日记'}:
            return 'diary', '用户偏好表达性写作/ User preference for expressive writing'

    if emotion:
        primary = emotion.get('primary_emotion') or ''
        if primary in ANXIETY_EMOTIONS:
            return 'mindfulness', f'主要情绪为{primary}，适合呼吸放松'
        if primary in SAD_EMOTIONS:
            return 'diary', f'主要情绪为{primary}，适合表达性写作'

    return 'mindfulness', '默认推荐正念呼吸/ Default recommendation: Mindfulness breathing'
