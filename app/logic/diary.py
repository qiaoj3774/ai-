from typing import Tuple

from ..db import (
    abandon_diary_session,
    add_diary_step,
    complete_diary_session,
    create_diary_session,
    get_active_diary_session,
    get_diary_steps,
    get_latest_emotion,
    get_latest_profile,
    update_diary_step_content,
)
from ..services.deepseek_client import DeepSeekClient
from ..services.prompts import DIARY_FEEDBACK_PROMPT, DIARY_PROMPT


MAX_DIARY_STEPS = 4
MIN_DIARY_PROMPT_CHARS = 420
DIARY_PROMPT_TIMEOUT_SEC = 6
client = DeepSeekClient()


def _build_steps_text(steps: list[dict]) -> str:
    parts = []
    for step in steps:
        parts.append(f"{step.get('prompt', '')}\n{step.get('content', '') or ''}")
    return '\n\n'.join(parts)


def _default_module_title(step_index: int) -> str:
    return {
        1: '模块1：当下情绪扫描 / Module 1: Present Emotion Scan',
        2: '模块2：事件与触发点 / Module 2: Events and Triggers',
        3: '模块3：需求与支持资源 / Module 3: Needs and Support',
        4: '模块4：整合与下一步 / Module 4: Integration and Next Step',
    }.get(step_index, f'模块{step_index} / Module {step_index}')


def _default_module_prompt(step_index: int) -> str:
    chinese = {
        1: (
            '请先把注意力放回到“此刻”的你。写下你正在经历的主要情绪，并尽量具体地描述它在身体中的位置、温度、重量或节奏。'
            '你可以写：它像一块石头压在胸口，或像一阵忽快忽慢的风。接着写下此刻最强烈的三个词，以及它们背后最真实的想法。'
            '不需要追求逻辑完整，只要真实即可。请允许句子是碎片化的、跳跃的。最后补充一句：如果这个情绪会说话，它最想被听见的内容是什么。'
        ),
        2: (
            '请回顾最近让你情绪波动最明显的一件事，按“发生了什么—我当时怎么想—我后来怎么感受”三个层次来写。'
            '尽量区分事实与解释：事实是可被记录的经过，解释是你当时脑海里的判断。你也可以写下当时未说出口的话、想做却没做的动作，'
            '以及这件事是否让你想起过去类似的经历。最后写一句：如果把这件事缩成一个画面，它最像什么场景。'
        ),
        3: (
            '请继续写：在这段经历里，你真正需要但暂时没有得到的是什么（例如理解、安全感、边界、休息、支持、肯定）。'
            '把这些需要分成“我可以自己给自己的”与“我希望他人给予的”两部分。然后写下你已经拥有的支持资源：一个人、一件事、一个习惯，'
            '哪怕很小也算。最后补一句：如果今天只做一件最温和、最可执行的小行动，它会是什么，以及你愿意在什么时间开始。'
        ),
        4: (
            '请把前面三步的内容整合成一个更连贯的自我叙述：我经历了什么、我因此产生了哪些情绪、我最深层的需要是什么、我准备如何照顾自己。'
            '你可以写给“今天的自己”，也可以写给“一周后的自己”。语气尽量温和，不批判。最后形成一段简短承诺：'
            '从现在到明天，我会用一个具体行动回应自己的需要，并写下行动完成后的自我鼓励语。'
        ),
    }.get(
        step_index,
        '请围绕你的真实感受继续书写：发生了什么、你如何理解它、你真正需要什么、你下一步想怎么照顾自己。',
    )
    english = {
        1: (
            'Bring your attention back to this exact moment. Write down the main emotion you are experiencing and describe how it feels in your body: location, temperature, weight, or rhythm. '
            'You may write that it feels like a stone on your chest or a gust of wind changing speed. Then list three words that best capture your present state and the thoughts behind them. '
            'Do not force perfect structure; authenticity matters more. Let your sentences be fragmented if needed. End with one line: if this emotion could speak, what would it ask to be heard?'
        ),
        2: (
            'Recall one recent event that triggered a strong emotional shift. Write in three layers: what happened, what you thought in that moment, and how you felt afterward. '
            'Try to separate facts from interpretations: facts are observable events, interpretations are your inner judgments. You can also include what you did not say out loud and what you wanted to do but held back. '
            'If this event reminds you of earlier experiences, note that link. End with one sentence: if this event became one image, what scene would it be?'
        ),
        3: (
            'Continue by naming what you truly needed in this experience but did not fully receive, such as understanding, safety, boundaries, rest, support, or affirmation. '
            'Split these needs into two groups: what you can offer yourself, and what you hope to receive from others. Then list support resources you already have: a person, an activity, or a small habit. '
            'Even tiny resources count. End with one gentle and realistic action you can take today, and specify when you are willing to start it.'
        ),
        4: (
            'Now integrate your earlier writing into one coherent self-narrative: what happened, what emotions emerged, what deeper needs were revealed, and how you plan to care for yourself. '
            'You may write to your present self or to yourself one week from now. Keep the tone compassionate rather than critical. '
            'Close with a short commitment: one specific action you will take by tomorrow to respond to your needs, followed by one sentence of encouragement you want to remember.'
        ),
    }.get(
        step_index,
        'Keep writing from your real experience: what happened, how you interpreted it, what you need most, and what gentle next step you are willing to take.',
    )
    return f"中文：{chinese}\n\nEnglish: {english}"


def _needs_prompt_fallback(prompt_text: str) -> bool:
    text = (prompt_text or '').strip()
    if len(text) < MIN_DIARY_PROMPT_CHARS:
        return True
    has_english = any('a' <= ch.lower() <= 'z' for ch in text)
    return not has_english


def _generate_step_prompt(step_index: int, profile: dict, emotion: dict) -> str:
    prompt = DIARY_PROMPT.format(step=step_index, profile=profile, emotion=emotion)
    messages = [
        {'role': 'system', 'content': '你是表达性写作引导师。'},
        {'role': 'user', 'content': prompt},
    ]
    result = client.chat_json(messages, timeout_sec=DIARY_PROMPT_TIMEOUT_SEC)
    module_title = (result.get('module_title') or '').strip() or _default_module_title(step_index)
    module_prompt = (result.get('prompt') or '').strip()
    if _needs_prompt_fallback(module_prompt):
        module_prompt = _default_module_prompt(step_index)
    return f"{module_title}\n{module_prompt}"


def start_or_resume_diary(user_id: int, chat_session_id: str | None = None) -> Tuple[int, int, str]:
    session = get_active_diary_session(user_id)
    if not session:
        session_id = create_diary_session(user_id)
        steps = []
        step_index = 1
    else:
        session_id = session['id']
        steps = get_diary_steps(session_id)
        if steps and all(not (step.get('content') or '').strip() for step in steps):
            abandon_diary_session(session_id)
            session_id = create_diary_session(user_id)
            steps = []
        step_index = len(steps) + 1

    if steps and steps[-1].get('content') is None:
        return session_id, len(steps), steps[-1]['prompt']

    if step_index > MAX_DIARY_STEPS:
        return session_id, MAX_DIARY_STEPS, ''

    profile = get_latest_profile(user_id, chat_session_id) or {}
    emotion = get_latest_emotion(user_id, chat_session_id) or {}
    full_prompt = _generate_step_prompt(step_index, profile, emotion)
    add_diary_step(session_id, step_index, full_prompt)
    return session_id, step_index, full_prompt


def submit_diary_step(
    user_id: int,
    session_id: int,
    step_index: int,
    content: str,
    chat_session_id: str | None = None,
) -> Tuple[int, int, str, bool]:
    steps = get_diary_steps(session_id)
    if not steps:
        return session_id, step_index, '', False

    update_diary_step_content(steps[-1]['id'], content)
    if step_index >= MAX_DIARY_STEPS:
        return session_id, step_index, '', True

    next_step = step_index + 1
    profile = get_latest_profile(user_id, chat_session_id) or {}
    emotion = get_latest_emotion(user_id, chat_session_id) or {}
    full_prompt = _generate_step_prompt(next_step, profile, emotion)
    add_diary_step(session_id, next_step, full_prompt)
    return session_id, next_step, full_prompt, False


def finalize_diary(session_id: int) -> Tuple[str, str]:
    steps = get_diary_steps(session_id)
    diary_text = _build_steps_text(steps)
    prompt = DIARY_FEEDBACK_PROMPT.format(diary=diary_text)
    messages = [
        {'role': 'system', 'content': '你是温和的心理疗愈师。'},
        {'role': 'user', 'content': prompt},
    ]
    result = client.chat_json(messages)
    diary_full = result.get('diary_full', diary_text)
    feedback = result.get('feedback', '感谢你的分享，愿你慢慢看见自己的力量。')
    complete_diary_session(session_id, diary_full, feedback)
    return diary_full, feedback


def cancel_diary(session_id: int) -> None:
    abandon_diary_session(session_id)


def _get_step_by_index(session_id: int, step_index: int) -> dict | None:
    for step in get_diary_steps(session_id):
        if step.get('step_index') == step_index:
            return step
    return None


def load_step_content(session_id: int, step_index: int) -> tuple[str, str]:
    step = _get_step_by_index(session_id, step_index)
    if not step:
        return '', ''
    return step.get('prompt', ''), step.get('content') or ''


def save_step_content(session_id: int, step_index: int, content: str) -> None:
    step = _get_step_by_index(session_id, step_index)
    if step:
        update_diary_step_content(step['id'], content)


def ensure_step_prompt(user_id: int, session_id: int, step_index: int, chat_session_id: str | None = None) -> str:
    step = _get_step_by_index(session_id, step_index)
    if step:
        return step.get('prompt', '')

    profile = get_latest_profile(user_id, chat_session_id) or {}
    emotion = get_latest_emotion(user_id, chat_session_id) or {}
    full_prompt = _generate_step_prompt(step_index, profile, emotion)
    add_diary_step(session_id, step_index, full_prompt)
    return full_prompt


def advance_guided_step(
    user_id: int,
    session_id: int,
    step_index: int,
    content: str,
    chat_session_id: str | None = None,
) -> tuple[int, str, str]:
    save_step_content(session_id, step_index, content)
    next_step = step_index + 1
    if next_step > MAX_DIARY_STEPS:
        return step_index, '', ''
    prompt = ensure_step_prompt(user_id, session_id, next_step, chat_session_id)
    _, next_content = load_step_content(session_id, next_step)
    return next_step, prompt, next_content


def retreat_guided_step(session_id: int, step_index: int, content: str) -> tuple[int, str, str]:
    save_step_content(session_id, step_index, content)
    prev_step = max(1, step_index - 1)
    prompt, prev_content = load_step_content(session_id, prev_step)
    return prev_step, prompt, prev_content


def finalize_guided_diary(session_id: int, step_index: int, content: str) -> tuple[str, str]:
    save_step_content(session_id, step_index, content)
    return finalize_diary(session_id)


def finalize_free_diary(user_id: int, content: str) -> tuple[str, str]:
    session = get_active_diary_session(user_id)
    if session:
        abandon_diary_session(session['id'])
    session_id = create_diary_session(user_id)
    add_diary_step(session_id, 1, '自由书写', content.strip())
    return finalize_diary(session_id)
