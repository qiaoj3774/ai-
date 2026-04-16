
import base64
from datetime import datetime, timezone
import html as html_lib
from pathlib import Path

import gradio as gr

from ..db import (
    accept_latest_recommendation,
    add_mindfulness_session,
    get_diary_session,
    list_mindfulness_sessions,
    list_recent_diary_sessions,
    save_chat_message,
    save_recommendation,
    start_new_chat_session,
)
from ..logic.chat import process_user_message
from ..logic.diary import (
    MAX_DIARY_STEPS,
    advance_guided_step,
    cancel_diary,
    finalize_free_diary,
    finalize_guided_diary,
    load_step_content,
    retreat_guided_step,
    start_or_resume_diary,
)
from ..logic.mindfulness import build_mindfulness_audio, generate_mindfulness_text, get_last_tts_error
from ..services.iflytek_client import IFlytekClient


iflytek = IFlytekClient()

WELCOME_TEXT = (
    '\u4f60\u597d\uff0c\u6211\u662f\u4f60\u7684AI\u966a\u4f34\u5c0f\u52a9\u624b\u3002\u4f60\u53ef\u4ee5\u8bf4\u8bf4\u4eca\u5929\u7684\u5fc3\u60c5\uff0c\u6211\u4f1a\u7ed9\u4f60\u5177\u4f53\u5efa\u8bae\u3002\n'
    'Hi, I am your AI companion. Share how you feel today and I will give concrete suggestions.'
)


OVERALL_ADVICE = (
    '\u603b\u4f53\u7597\u6108\u5efa\u8bae\uff1a\u4f18\u5148\u4fdd\u8bc1\u7761\u7720\u548c\u89c4\u5f8b\u996e\u98df\uff0c\u767d\u5929\u5b89\u639210-20\u5206\u949f\u8f7b\u8fd0\u52a8\uff0c'
    '\u5e76\u7559\u51fa\u7a33\u5b9a\u7684\u653e\u677e\u65f6\u95f4\u3002\u82e5\u60c5\u7eea\u6301\u7eed\u52a0\u91cd\u6216\u660e\u663e\u5f71\u54cd\u5b66\u4e60\u3001\u5de5\u4f5c\u548c\u7761\u7720\uff0c'
    '\u5efa\u8bae\u8054\u7cfb\u5b66\u6821\u5fc3\u7406\u4e2d\u5fc3\u6216\u533b\u9662\u5fc3\u7406\u95e8\u8bca\u8fdb\u884c\u4e13\u4e1a\u8bc4\u4f30\u3002\n'
    'Overall advice: keep regular sleep and meals, do 10-20 minutes of light exercise in daytime, '
    'and reserve stable relaxation time. If symptoms keep worsening or affect study/work/sleep, '
    'please contact a counselor or hospital clinic for professional support.'
)


DIARY_INTRO_TEXT = (
    '欢迎来到「日记」模块，这是一个以“表达性写作练习”为核心的安全空间。'
    '在这里，你可以通过系统提供的写作提示，梳理内心那些模糊的感受、盘旋的思绪或重要的回忆。'
    '请完全放下对“文笔”或“逻辑”的苛求，允许自己跟随提示，将最真实的情感片段自由地书写下来——'
    '每一段文字都是拼图的一角，无需完整，只需真诚。\n\n'
    '你的练习将分步进行：请根据每一页的提示写下你想表达的内容，完成后点击「下一步」，即可继续深入或转换角度。'
    '你可以完全掌控节奏，这个过程只属于你。当你点击「我写完了」系统会把你所有写下的内容，'
    '智能而温柔地整合成一篇连贯的完整日记，帮你看见自己情感的全貌；随后，你将获得一份专属的AI反馈——'
    '它并非评判，而是一面专注的“镜子”，会温和地映照出你文字中蕴含的情感脉络与潜在需求，陪伴你完成这场自我觉察。\n\n'
    '现在，请放松下来，踏上这场既结构化又充满自由的内心书写旅程吧。'
    'Welcome to the "Diary" module, which is a secure space centered around "expressive writing exercises". '
    'Here, you can use the writing prompts provided by the system to sort out those vague feelings, swirling thoughts or important memories in your mind. '
    'Please completely let go of the obsession with "writing style"or "logic", and allow yourself to follow the prompts and freely write down the most genuine emotional fragments'
    'Each paragraph of text is a corner of a puzzle. There is no need for it to be complete; sincerity is all that matters. \n\n'
    'Your practice will be carried out in steps: Please write down what you want to express according to the instructions on each page. After completing it, click "Next" to proceed and either deepen your understanding or change your perspective. '
    'You can completely control the pace. This process is solely yours. When you click "done", the system will intelligently and gently integrate all the content you have written into a coherent and complete diary, helping you see the full picture of your emotions; subsequently, you will receive an exclusive AI feedback - '
    'It is not a judgment, but rather a focused "mirror", which will gently reflect the emotional thread and potential needs contained in your writing, accompanying you in completing this self-awareness process." \n\n'
    'Now, please relax. Embark on this structured yet liberating journey of inner writing." '
)


FREE_DIARY_FIXED_PROMPT = (
    '\u5f53\u4f60\u9762\u5bf9\u8fd9\u4e2a\u7a7a\u767d\u7684\u9875\u9762\u65f6\uff0c\u8bf7\u4e3a\u81ea\u5df1\u9884\u7559\u4e00\u6bb5\u4e0d\u88ab\u6253\u6270\u7684\u65f6\u5149\u3002\u8fd9\u91cc\u7684\u4e66\u5199\u5b8c\u5168\u5c5e\u4e8e\u4f60\uff0c\u6ca1\u6709\u8bc4\u5224\uff0c\u4e5f\u65e0\u9700\u5b8c\u7f8e\u3002\u8bd5\u7740\u653e\u4e0b\u5bf9\u201c\u6587\u7b14\u201d\u6216\u201c\u903b\u8f91\u201d\u7684\u82db\u6c42\uff0c\u8ba9\u952e\u76d8\u6210\u4e3a\u611f\u53d7\u7684\u5ef6\u4f38\u3002\u5982\u679c\u4e0d\u77e5\u5982\u4f55\u5f00\u59cb\uff0c\u4e0d\u59a8\u5148\u8f7b\u8f7b\u95ee\u81ea\u5df1\uff1a\u6b64\u523b\u6700\u660e\u663e\u7684\u60c5\u7eea\u662f\u4ec0\u4e48\uff1f\u662f\u9690\u9690\u7684\u75b2\u60eb\uff0c\u8fd8\u662f\u5b89\u9759\u7684\u559c\u60a6\uff1f\u4e0d\u5fc5\u8ffd\u6eaf\u5b8c\u6574\u7684\u4e8b\u4ef6\uff0c\u53ea\u9700\u6e29\u67d4\u5730\u6ce8\u89c6\u8fd9\u4efd\u611f\u53d7\u672c\u8eab\u2014\u2014\u5b83\u505c\u7559\u5728\u8eab\u4f53\u7684\u54ea\u4e2a\u89d2\u843d\uff1f\u5982\u679c\u5b83\u6709\u989c\u8272\u6216\u6e29\u5ea6\uff0c\u4f1a\u662f\u4ec0\u4e48\u6a21\u6837\uff1f\n\n'
    '\u5141\u8bb8\u81ea\u5df1\u5199\u5f97\u96f6\u788e\u3001\u8df3\u8dc3\uff0c\u751a\u81f3\u8bed\u65e0\u4f26\u6b21\u3002\u5982\u679c\u4e2d\u9014\u505c\u987f\uff0c\u5c31\u91cd\u590d\u6572\u4e0b\u6700\u540e\u4e00\u53e5\u8bdd\uff0c\u6216\u8005\u8bda\u5b9e\u5730\u8f93\u5165\uff1a\u201c\u6211\u6709\u70b9\u4e0d\u77e5\u9053\u5199\u4ec0\u4e48\u2026\u2026\u201d\u7136\u540e\u7b49\u5f85\u4e0b\u4e00\u7f15\u601d\u7eea\u81ea\u7136\u6d6e\u73b0\u3002\u4f60\u4e5f\u53ef\u4ee5\u7528\u4e00\u4e2a\u7b80\u5355\u7684\u6bd4\u55bb\u5f00\u573a\uff1a\u201c\u4eca\u5929\uff0c\u50cf\u4e00\u9635______\u7684\u98ce\u201d\uff0c\u586b\u4e0a\u53ea\u5c5e\u4e8e\u4f60\u7684\u8bcd\u8bed\u3002\n\n'
    '\u8bf7\u8ddf\u968f\u5185\u5fc3\u7684\u8282\u594f\uff0c\u81ea\u7531\u5730\u4e66\u5199\u3002\u5f53\u4f60\u611f\u5230\u544a\u4e00\u6bb5\u843d\uff0c\u65e0\u9700\u56de\u5934\u4fee\u6539\u6216\u8bc4\u5224\u2014\u2014\u53ea\u9700\u70b9\u51fb\u4e0b\u65b9\u201c\u6211\u5199\u5b8c\u5566\u201d\u3002\u4f60\u5c06\u6536\u5230\u4e00\u4efd\u57fa\u4e8e\u4f60\u4e66\u5199\u5185\u5bb9\u751f\u6210\u7684\u3001\u68b3\u7406\u540e\u7684\u5185\u5fc3\u65e5\u8bb0\uff0c\u4ee5\u53ca\u4e00\u4efd\u6e29\u6696\u800c\u771f\u8bda\u7684\u53cd\u9988\u3002\u8fd9\u4e0d\u662f\u4fee\u6539\uff0c\u800c\u662f\u4e00\u9762\u955c\u5b50\uff0c\u5e2e\u4f60\u7167\u89c1\u81ea\u5df1\u6587\u5b57\u4e2d\u8574\u85cf\u7684\u771f\u5b9e\u60c5\u611f\u4e0e\u9700\u6c42\u3002\u4f60\u7684\u6bcf\u4e00\u6b21\u771f\u8bda\u6d41\u9732\uff0c\u90fd\u503c\u5f97\u88ab\u6e29\u67d4\u770b\u89c1\u3002'
)

MINDFULNESS_FIXED_GUIDANCE = (
    '\u8bf7\u627e\u5230\u4e00\u4e2a\u8212\u9002\u7684\u4f4d\u7f6e\u5750\u4e0b\uff0c\u80cc\u90e8\u81ea\u7136\u633a\u76f4\uff0c\u53cc\u624b\u8f7b\u8f7b\u653e\u5728\u819d\u76d6\u6216\u5927\u817f\u4e0a\u3002\u5982\u679c\u4f60\u613f\u610f\uff0c\u53ef\u4ee5\u7f13\u7f13\u95ed\u4e0a\u773c\u775b\uff0c\u6216\u8005\u5c06\u76ee\u5149\u67d4\u548c\u7684\u843d\u5728\u524d\u65b9\u4e0d\u8fdc\u7684\u5730\u9762\u3002\u6211\u4eec\u5373\u5c06\u5f00\u59cb\u4e00\u6bb5\u7b80\u77ed\u7684\u6b63\u5ff5\u547c\u5438\u7ec3\u4e60\uff0c\u552f\u4e00\u7684\u76ee\u6807\uff0c\u5c31\u662f\u6e29\u67d4\u5730\u89c9\u5bdf\u81ea\u5df1\u7684\u547c\u5438\u3002\n\n'
    '\u73b0\u5728\uff0c\u8bf7\u5c06\u6ce8\u610f\u529b\u8f7b\u8f7b\u5730\u5e26\u5230\u4f60\u7684\u8eab\u4f53\u4e0a\u3002\u611f\u53d7\u81c0\u90e8\u4e0e\u6905\u5b50\u63a5\u89e6\u7684\u611f\u89c9\uff0c\u53cc\u811a\u5e73\u8d34\u5730\u9762\u7684\u8e0f\u5b9e\u611f\u3002\u7136\u540e\uff0c\u6162\u6162\u5730\u5c06\u89c9\u5bdf\u8f6c\u5411\u4f60\u7684\u547c\u5438\u3002\u4e0d\u9700\u8981\u7528\u529b\u6539\u53d8\u547c\u5438\u7684\u6df1\u6d45\u6216\u8282\u594f\uff0c\u53ea\u662f\u53bb\u6ce8\u610f\u5b83\u3002\u611f\u53d7\u7a7a\u6c14\u5982\u4f55\u81ea\u7136\u5730\u6d41\u5165\u4f60\u7684\u9f3b\u8154\uff0c\u5fae\u5fae\u6e05\u51c9\uff1b\u53c8\u662f\u5982\u4f55\u81ea\u7136\u5730\u6d41\u51fa\uff0c\u5e26\u7740\u4e00\u4e1d\u6696\u610f\u3002\u53bb\u89c9\u5bdf\u5438\u6c14\u65f6\uff0c\u80f8\u8154\u6216\u8179\u90e8\u90a3\u5fae\u5fae\u7684\u8d77\u4f0f\uff1b\u547c\u6c14\u65f6\uff0c\u8eab\u4f53\u90a3\u7ec6\u5fae\u7684\u653e\u677e\u3002\u5982\u679c\u4f60\u7684\u6ce8\u610f\u529b\u8dd1\u5f00\u4e86\uff0c\u60f3\u5230\u521a\u624d\u7684\u5de5\u4f5c\u6216\u63a5\u4e0b\u6765\u7684\u5b89\u6392\uff0c\u8fd9\u5b8c\u5168\u6ca1\u6709\u5173\u7cfb\u2014\u2014\u8fd9\u6b63\u662f\u89c9\u5bdf\u7684\u5f00\u59cb\u3002\u53ea\u9700\u6e29\u548c\u5730\u6ce8\u610f\u5230\uff1a\u201c\u554a\uff0c\u601d\u7eea\u98d8\u8d70\u4e86\u3002\u201d\u7136\u540e\uff0c\u518d\u4e00\u6b21\u8f7b\u67d4\u5730\u5c06\u6ce8\u610f\u529b\u5e26\u56de\u5230\u547c\u5438\u7684\u611f\u89c9\u4e0a\uff0c\u50cf\u9080\u8bf7\u4e00\u4f4d\u8001\u670b\u53cb\u56de\u5bb6\u4e00\u6837\u81ea\u7136\u3002\n\n'
    '\u6211\u4eec\u5c06\u8fd9\u6837\u6301\u7eed\u5730\u966a\u4f34\u547c\u5438\u3002\u5438\u6c14\uff0c\u77e5\u9053\u81ea\u5df1\u5728\u5438\u6c14\uff1b\u547c\u6c14\uff0c\u77e5\u9053\u81ea\u5df1\u5728\u547c\u6c14\u3002\u5141\u8bb8\u4e00\u5207\u611f\u53d7\u2014\u2014\u5e73\u9759\u3001\u70e6\u8e81\u3001\u653e\u677e\u3001\u7d27\u7ef7\u2014\u2014\u5982\u4e91\u6735\u822c\u98d8\u6765\uff0c\u53c8\u98d8\u8fc7\u3002\u4f60\u53ea\u662f\u5929\u7a7a\uff0c\u9759\u9759\u5730\u89c2\u5bdf\u7740\u4e91\u5f69\u7684\u53d8\u5316\u3002\n\n'
    '\u5f53\u4f60\u51c6\u5907\u597d\u4e86\uff0c\u53ef\u4ee5\u6162\u6162\u7ed3\u675f\u8fd9\u6bb5\u7ec3\u4e60\u3002\u5148\u8ba9\u89c9\u5bdf\u56de\u5230\u623f\u95f4\uff0c\u611f\u53d7\u8eab\u4f53\u7684\u5b58\u5728\uff0c\u518d\u7f13\u7f13\u7741\u5f00\u773c\u775b\u3002'
)

MINDFULNESS_OPERATION_HINT = (
    '你可以点击“开始”，进入正式的正念呼吸练习。过程中，如果需要短暂调整，'
    '可以随时点击“暂停”；当你希望完全结束本次练习时，点击“终止”按钮即可。'
    '愿你在这段呼吸的间隙中，收获片刻的宁静与清晰。\n'
    'Tap "Start" to begin mindful breathing. Use "Pause" any time, and click "Stop" when you want to finish. '
    'May this short practice bring you a moment of calm and clarity.'
)

STEP_LABELS = {1: '模块1 / Module 1', 2: '模块2 / Module 2', 3: '模块3 / Module 3', 4: '模块4 / Module 4'}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;800&display=swap');

:root {
  --wx-green: #07c160;
  --wx-green-dark: #05a851;
  --wx-line: #d2d8e1;
  --wx-chat-bg: #d7dde6;
  --wx-user: #95ec69;
  --wx-ai: #ffffff;
}

html,
body {
  margin: 0 !important;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #dde2ea;
  font-family: 'Noto Sans SC', sans-serif;
}

gradio-app,
.gradio-container,
.gradio-container .main,
.gradio-container main.contain {
  width: 100vw !important;
  max-width: none !important;
  height: 100vh !important;
  max-height: none !important;
  margin: 0 !important;
  padding: 0 !important;
  border: none !important;
  border-radius: 0 !important;
  background: transparent !important;
}

footer {
  display: none !important;
}

#app-root {
  height: 100vh;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

#section-chat,
#section-mindfulness,
#section-diary {
  flex: 1;
  min-height: 0;
}

.top-title {
  height: 74px;
  line-height: 74px;
  text-align: center;
  font-size: 50px;
  font-weight: 800;
  color: #121212;
  border-bottom: 1px solid #d9dfe7;
  background: rgba(247, 249, 252, 0.96);
}

#chat-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--wx-chat-bg);
}

#chat-window {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 14px 8px;
  background: var(--wx-chat-bg);
}

#chat-messages {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.msg-row.user {
  justify-content: flex-end;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  overflow: hidden;
  flex-shrink: 0;
  background: #e7b39f;
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.bubble {
  max-width: 74%;
  padding: 9px 12px;
  font-size: 15px;
  line-height: 1.55;
  color: #14161a;
  word-break: break-word;
  position: relative;
}

.ai-bubble {
  background: var(--wx-ai);
  border-radius: 4px 14px 14px 14px;
}

.user-bubble {
  background: var(--wx-user);
  border-radius: 14px 4px 14px 14px;
}

.ai-bubble::before {
  content: '';
  position: absolute;
  left: -6px;
  top: 10px;
  border-style: solid;
  border-width: 6px 8px 6px 0;
  border-color: transparent #ffffff transparent transparent;
}

.user-bubble::after {
  content: '';
  position: absolute;
  right: -6px;
  top: 10px;
  border-style: solid;
  border-width: 6px 0 6px 8px;
  border-color: transparent transparent transparent var(--wx-user);
}

#rec-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 8px 2px;
}

#rec-actions button {
  min-height: 30px;
  height: 30px;
  border-radius: 999px;
  border: 1px solid #d3d9e2;
  background: #ffffff;
  color: #46505e;
  font-size: 12px;
  padding: 0 12px;
  cursor: pointer;
}

#rec-yes-btn button {
  border: none;
  color: #fff;
  background: linear-gradient(135deg, var(--wx-green) 0%, var(--wx-green-dark) 100%);
}

#wechat-input {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  margin: 0 !important;
  padding: 8px 10px !important;
  border-top: 1px solid var(--wx-line);
  background: #f5f7fa;
}

#wechat-audio {
  width: 76px !important;
  min-width: 76px !important;
  flex: 0 0 76px !important;
}

#wechat-audio .audio-container {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
}

#wechat-text {
  flex: 1;
  min-width: 0;
}

#wechat-text textarea {
  border: 1px solid #d2d8e1 !important;
  border-radius: 8px !important;
  background: #fff !important;
  font-size: 14px !important;
  line-height: 1.45 !important;
  min-height: 36px;
  max-height: 108px;
}

#wechat-send,
#wechat-send button {
  width: 54px !important;
  min-width: 54px !important;
  height: 34px !important;
  border: none !important;
  border-radius: 8px !important;
  color: #fff !important;
  font-weight: 700 !important;
  font-size: 14px !important;
  background: linear-gradient(135deg, var(--wx-green) 0%, var(--wx-green-dark) 100%) !important;
}

#section-mindfulness {
  background:
    radial-gradient(circle at 10% 25%, rgba(255, 178, 150, 0.35), transparent 36%),
    linear-gradient(90deg, #f7ece8 0%, #e9e8ea 38%, #d6e4f0 100%);
}

#mind-shell {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

#mind-stage {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px 18px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
}

.breath-ball {
  width: 220px;
  height: 220px;
  border-radius: 50%;
  align-self: flex-start;
  margin-top: 72px;
  margin-left: 4px;
  background: radial-gradient(circle at 30% 28%, #ffd9cd 0%, #f7b29a 62%, #f0a189 100%);
  opacity: 0.9;
  animation: breathe 5s ease-in-out infinite alternate;
  box-shadow: 0 0 88px rgba(246, 155, 131, 0.40);
}

#mind-script {
  width: min(1120px, 80%);
  margin-top: -176px;
  max-height: 260px;
  min-height: 170px;
  overflow: hidden;
  padding: 12px 18px;
  border: none;
  background: transparent;
  font-size: 18px;
  line-height: 1.82;
  text-align: center;
  color: #4e5966;
}

#mind-script,
#mind-script .prose,
#mind-script .prose *,
#mind-script .md,
#mind-script .md * {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
}

#mind-script p {
  margin: 0;
}

#mind-timer {
  margin-top: 2px;
  font-size: 36px;
  font-weight: 800;
  color: #727d8a;
}

#mind-hint {
  width: min(1280px, 96%);
  margin-top: auto;
  margin-bottom: 4px;
  padding: 10px 14px;
  border: 1px solid #d5deea;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.72);
  color: #4d5865;
  font-size: 14px;
  line-height: 1.65;
}

#mind-history-open {
  position: absolute !important;
  right: 14px !important;
  top: 12px !important;
  left: auto !important;
  z-index: 24;
  width: auto !important;
  min-width: 96px !important;
  max-width: 112px !important;
  margin: 0 !important;
  padding: 0 !important;
  display: inline-flex !important;
  flex: 0 0 auto !important;
}

#mind-history-open button {
  width: 100% !important;
  min-height: 34px !important;
  height: 34px !important;
  border-radius: 12px !important;
  border: 1px solid #d6dee8 !important;
  background: rgba(255, 255, 255, 0.92) !important;
  color: #556171 !important;
  font-size: 13px !important;
  padding: 0 10px !important;
}

#mind-controls {
  margin: 0 10px 4px !important;
  gap: 10px;
}

#mind-controls > * {
  flex: 1;
}

#mind-controls button {
  min-height: 42px !important;
  border-radius: 999px !important;
  font-size: 31px !important;
  font-weight: 700 !important;
  border: 1px solid #d2dbe6 !important;
  background: #fff !important;
  color: #556171 !important;
}

#mind-start button {
  border: none !important;
  color: #fff !important;
  background: linear-gradient(135deg, var(--wx-green) 0%, var(--wx-green-dark) 100%) !important;
}

#mind-status {
  margin: 0 12px 4px;
  text-align: center;
  color: #6a7482;
  font-size: 13px;
}

#mind-guidance-audio,
#mind-bgm-audio {
  width: 1px !important;
  min-width: 1px !important;
  height: 1px !important;
  margin: 0 !important;
  opacity: 0 !important;
  overflow: hidden !important;
}

#mind-guidance-audio .audio-container,
#mind-bgm-audio .audio-container {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
}

#section-diary {
  background: linear-gradient(90deg, #f3f5f8 0%, #eff8f4 100%);
}

#diary-shell {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  padding: 0 12px 8px;
  display: flex;
  flex-direction: column;
}

#diary-intro {
  margin-top: 8px;
  padding: 12px 14px;
  border: 1px solid #dde6f0;
  border-radius: 0;
  background: linear-gradient(90deg, #f8fafb 0%, #ebf8f1 100%);
  color: #2f3f50;
  line-height: 1.75;
  font-size: 14px;
}

#diary-progress {
  margin: 8px 0 6px;
  text-align: right;
  color: var(--wx-green);
  font-size: 20px;
  font-weight: 800;
}

#diary-prompt textarea,
#diary-content textarea {
  border: 1px solid #dbe3ee !important;
  border-radius: 12px !important;
  overflow-y: hidden !important;
  resize: none !important;
}

#diary-prompt textarea {
  min-height: 210px;
  line-height: 1.68 !important;
  background: #f4f8f6;
}

#diary-content textarea {
  min-height: 320px;
  line-height: 1.66 !important;
  background: #fff;
}

#diary-actions,
#diary-tools {
  gap: 10px;
  margin-top: 8px;
}

#diary-actions button,
#diary-tools button {
  min-height: 40px !important;
  border-radius: 10px !important;
  font-size: 24px !important;
  font-weight: 700 !important;
}

#btn-next button,
#btn-finish button,
#btn-free-submit button {
  border: none !important;
  color: #fff !important;
  background: linear-gradient(135deg, var(--wx-green) 0%, var(--wx-green-dark) 100%) !important;
}

#btn-cancel button,
#btn-history button,
#btn-prev button {
  border: 1px solid #d5deea !important;
  background: #fff !important;
  color: #4f5966 !important;
}

#diary-status {
  margin-top: 6px;
  min-height: 24px !important;
  padding-bottom: 6px;
  color: #4b5563;
  line-height: 1.5;
}

#history-feedback {
  margin-top: 10px;
}

#bottom-nav {
  flex: 0 0 auto;
  display: grid !important;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  border-top: 1px solid var(--wx-line);
  background: #f5f7fa;
}

#bottom-nav > * {
  min-width: 0 !important;
}

#bottom-nav button {
  width: 100% !important;
  height: 56px !important;
  min-height: 56px !important;
  border: none !important;
  border-radius: 0 !important;
  background: transparent !important;
  color: #8b94a1 !important;
  font-size: 22px !important;
  font-weight: 600 !important;
  box-shadow: none !important;
}

#nav-chat button {
  color: var(--wx-green) !important;
  font-weight: 700 !important;
}

.overlay-modal {
  position: fixed !important;
  inset: 0;
  z-index: 1500;
  background: rgba(15, 23, 42, 0.34);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
}

.overlay-modal.hide,
.overlay-modal[style*="display: none"] {
  display: none !important;
  pointer-events: none !important;
}

.modal-card {
  width: min(820px, 95vw);
  max-height: min(84vh, 860px);
  overflow: auto;
  border-radius: 12px;
  padding: 14px;
  border: 1px solid #dde4ef;
  background: #fff;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.25);
}

#mind-history-table,
#diary-history-table {
  font-size: 13px;
}

@keyframes breathe {
  from { transform: scale(0.83); opacity: 0.58; }
  to { transform: scale(1.14); opacity: 0.94; }
}

@media (max-width: 920px) {
  .top-title {
    height: 62px;
    line-height: 62px;
    font-size: 34px;
  }

  .bubble {
    max-width: 82%;
  }

  #mind-script {
    width: 98%;
    margin-top: 12px;
    min-height: 148px;
    font-size: 16px;
  }

  .breath-ball {
    width: 164px;
    height: 164px;
    margin-top: 30px;
  }

  #mind-controls button {
    font-size: 18px !important;
  }

  #diary-actions button,
  #diary-tools button,
  #bottom-nav button {
    font-size: 16px !important;
  }
}
"""


REC_BUBBLE_JS = """<script>
(function () {
  if (window.__recBubbleBound) {
    return;
  }
  window.__recBubbleBound = true;

  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-rec-choice]');
    if (!trigger) {
      return;
    }
    event.preventDefault();
    var choice = trigger.getAttribute('data-rec-choice');
    var selector = choice === 'yes' ? '#rec-yes-btn button' : '#rec-no-btn button';
    var button = document.querySelector(selector);
    if (button) {
      button.click();
    }
  });

  var scrollToBottom = function () {
    var wrapper = document.querySelector('#chat-window');
    if (wrapper) {
      wrapper.scrollTop = wrapper.scrollHeight;
    }
  };

  setInterval(scrollToBottom, 300);
})();
</script>"""


BASE_DIR = Path(__file__).resolve().parents[2]
AVATAR_USER = BASE_DIR / 'assets' / 'generated' / 'avatar_user.png'
AVATAR_AI = BASE_DIR / 'assets' / 'generated' / 'avatar_ai.png'


def _load_avatar(path: Path) -> str | None:
    try:
        encoded = base64.b64encode(path.read_bytes()).decode('ascii')
        return f'data:image/png;base64,{encoded}'
    except Exception:
        return None


USER_AVATAR_DATA = _load_avatar(AVATAR_USER)
AI_AVATAR_DATA = _load_avatar(AVATAR_AI)


def _initial_chat_state() -> list[dict]:
    return [{'role': 'assistant', 'content': WELCOME_TEXT}]


def _timer_text(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    mm, ss = divmod(seconds, 60)
    return f'<span>计时/Time：{mm:02d}:{ss:02d}</span>'


def _compact_text(text: str | None) -> str:
    if not text:
        return ''
    lines = [(line or '').strip() for line in str(text).replace('\r\n', '\n').split('\n')]
    return '\n'.join([line for line in lines if line])


def _parse_iso_datetime(value: str | None) -> datetime | None:
    raw = (value or '').strip()
    if not raw:
        return None
    normalized = raw.replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            return None
    # Historical rows were stored as naive UTC timestamps, so convert to local time for display.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def _format_local_datetime(value: str | None, with_time: bool = True) -> str:
    dt = _parse_iso_datetime(value)
    if not dt:
        return ''
    return dt.strftime('%Y-%m-%d %H:%M:%S' if with_time else '%Y-%m-%d')


def transcribe_audio(audio):
    if audio is None:
        return ''
    sample_rate, data = audio
    if data is None:
        return ''
    try:
        return iflytek.transcribe(data, sample_rate)
    except Exception:
        return ''

AFFIRMATIVE_WORDS = {
    '是', '好', '好的', '行', '可以', '嗯', '嗯嗯', '要', '想', '愿意', '同意', '可以跳转', 'ok', 'yes'
}
NEGATIVE_WORDS = {'不', '不要', '不想', '不用', '暂不', '先不', '等等', '稍后', '算了', 'no'}


def _is_affirmative(text: str) -> bool:
    content = text.strip().lower()
    if not content:
        return False
    if any(word in content for word in NEGATIVE_WORDS):
        return False
    if content in AFFIRMATIVE_WORDS:
        return True
    return any(word in content for word in AFFIRMATIVE_WORDS if len(word) >= 2)


def _is_negative(text: str) -> bool:
    content = text.strip().lower()
    if not content:
        return False
    return any(word in content for word in NEGATIVE_WORDS)


def _normalize_intent_text(text: str) -> str:
    content = ''.join((text or '').strip().split())
    return content.strip('。！？!?.,，；;:：').lower()


def _detect_direct_intent(text: str) -> str | None:
    content = _normalize_intent_text(text)
    if not content:
        return None
    if content == '我想去写日记':
        return 'diary'
    if content == '我想去练习室':
        return 'mindfulness'
    return None


def _rec_choice_labels(rec_state: dict | None) -> tuple[str, str]:
    module = (rec_state or {}).get('module')
    if module == 'mindfulness':
        return '\u8fdb\u5165\u7ec3\u4e60\u5ba4 / Go to Practice Room', '\u6682\u4e0d\u8df3\u8f6c / Stay in Chat'
    if module == 'diary':
        return '\u8fdb\u5165\u65e5\u8bb0 / Go to Journal', '\u6682\u4e0d\u8df3\u8f6c / Stay in Chat'
    return '', ''


def _render_chat_html(messages: list[dict], rec_state: dict | None = None) -> str:
    rows = []
    for msg in messages:
        role = msg.get('role')
        content = html_lib.escape(msg.get('content', '')).replace('\n', '<br>')
        if role == 'user':
            avatar = f'<img src="{USER_AVATAR_DATA}" alt="user" />' if USER_AVATAR_DATA else '?'
            rows.append(
                '<div class="msg-row user">'
                f'<div class="bubble user-bubble">{content}</div>'
                f'<div class="avatar">{avatar}</div>'
                '</div>'
            )
        else:
            avatar = f'<img src="{AI_AVATAR_DATA}" alt="ai" />' if AI_AVATAR_DATA else 'AI'
            rows.append(
                '<div class="msg-row assistant">'
                f'<div class="avatar">{avatar}</div>'
                f'<div class="bubble ai-bubble">{content}</div>'
                '</div>'
            )

    return f'<div id="chat-messages">{"".join(rows)}</div>'


def _section_updates(target: str):
    return (
        gr.update(visible=target == 'chat'),
        gr.update(visible=target == 'mindfulness'),
        gr.update(visible=target == 'diary'),
    )


def _rec_action_updates(rec_state: dict | None):
    if rec_state and rec_state.get('module') in {'mindfulness', 'diary'}:
        yes_label = (
            '\u8fdb\u5165\u7ec3\u4e60\u5ba4 / Go to Practice Room'
            if rec_state['module'] == 'mindfulness'
            else '\u8fdb\u5165\u65e5\u8bb0 / Go to Journal'
        )
        return (
            gr.update(visible=True),
            gr.update(value=yes_label),
            gr.update(value='\u6682\u4e0d\u8df3\u8f6c / Stay in Chat'),
        )
    return gr.update(visible=False), gr.update(), gr.update()


def _rec_hide_updates():
    return (
        gr.update(visible=False),
        gr.update(value='进入练习室 / Go to Practice Room'),
        gr.update(value='暂不跳转 / Stay in Chat'),
    )


def _clear_recommendation_state():
    return {}, *_rec_hide_updates()


def _mindfulness_reset(script: str, status_text: str):
    script = _compact_text((script or '').strip() or MINDFULNESS_FIXED_GUIDANCE)
    return (
        gr.update(value=script),
        script,
        None,
        None,
        gr.update(value=status_text),
        False,
        gr.update(active=False),
        0,
        gr.update(value=_timer_text(0)),
    )


def prepare_mindfulness_direct():
    return _mindfulness_reset(
        MINDFULNESS_FIXED_GUIDANCE,
        '已加载固定引导词。点击“开始”后才会播放语音和背景音乐。\nFixed guidance loaded. Audio and BGM will start after clicking "Start".',
    )


def prepare_mindfulness_ai(user_id: int, session_id: str):
    script = generate_mindfulness_text(user_id, session_id) or MINDFULNESS_FIXED_GUIDANCE
    return _mindfulness_reset(
        script,
        '已生成当前专属引导词。点击“开始”后播放语音和背景音乐。\nPersonalized guidance is ready. Audio and BGM will start after clicking "Start".',
    )


def keep_mindfulness_state(mind_script_state: str, timer_running: bool, timer_elapsed: int):
    return (
        gr.update(),
        mind_script_state,
        gr.update(),
        gr.update(),
        gr.update(),
        timer_running,
        gr.update(),
        timer_elapsed,
        gr.update(),
    )

def start_mindfulness(user_id: int, session_id: str, script: str):
    script = _compact_text((script or '').strip() or MINDFULNESS_FIXED_GUIDANCE)
    tts_path, music_path = build_mindfulness_audio(script)
    if tts_path and music_path:
        status_text = '\u7ec3\u4e60\u5df2\u5f00\u59cb\uff0c\u8bed\u97f3\u548c\u80cc\u666f\u97f3\u4e50\u5df2\u64ad\u653e\u3002\nSession started. Voice guidance and BGM are playing.'
    elif tts_path:
        status_text = '\u7ec3\u4e60\u5df2\u5f00\u59cb\uff0c\u8bed\u97f3\u5df2\u64ad\u653e\uff0c\u672a\u68c0\u6d4b\u5230\u80cc\u666f\u97f3\u4e50\u6587\u4ef6\u3002\nSession started with voice guidance only (no BGM file detected).'
    elif music_path:
        err = (get_last_tts_error() or '').strip()
        if err:
            status_text = (
                '\u7ec3\u4e60\u5df2\u5f00\u59cb\uff0c\u80cc\u666f\u97f3\u4e50\u5df2\u64ad\u653e\uff0c\u8bed\u97f3\u751f\u6210\u5931\u8d25\u3002\n'
                f'Session started with BGM only. TTS failed: {err}'
            )
        else:
            status_text = '\u7ec3\u4e60\u5df2\u5f00\u59cb\uff0c\u80cc\u666f\u97f3\u4e50\u5df2\u64ad\u653e\uff0c\u8bed\u97f3\u751f\u6210\u5931\u8d25\u3002\nSession started with BGM only (voice synthesis failed).'
    else:
        err = (get_last_tts_error() or '').strip()
        if err:
            status_text = (
                '\u7ec3\u4e60\u5df2\u5f00\u59cb\uff0c\u4f46\u8bed\u97f3\u548c\u80cc\u666f\u97f3\u4e50\u90fd\u672a\u80fd\u64ad\u653e\u3002\n'
                f'Session started, but voice and BGM are unavailable. TTS error: {err}'
            )
        else:
            status_text = '\u7ec3\u4e60\u5df2\u5f00\u59cb\uff0c\u4f46\u8bed\u97f3\u548c\u80cc\u666f\u97f3\u4e50\u90fd\u672a\u80fd\u64ad\u653e\u3002\nSession started, but voice and BGM are unavailable.'
    return (
        gr.update(value=script),
        script,
        tts_path,
        music_path,
        gr.update(value=status_text),
        True,
        gr.update(active=True),
        0,
        gr.update(value=_timer_text(0)),
    )


def pause_mindfulness(script: str, elapsed: int):
    compact_script = _compact_text(script or MINDFULNESS_FIXED_GUIDANCE)
    return (
        gr.update(value=compact_script),
        compact_script,
        None,
        None,
        gr.update(value='已暂停。准备好后可再次点击“开始”。\nPaused. Click "Start" when you are ready.'),
        False,
        gr.update(active=False),
        elapsed,
        gr.update(value=_timer_text(elapsed)),
    )


def stop_mindfulness(user_id: int, script: str, elapsed: int):
    script = _compact_text((script or '').strip() or MINDFULNESS_FIXED_GUIDANCE)
    add_mindfulness_session(user_id, max(0, int(elapsed or 0)), script)
    gr.Info('本次训练记录已保存 The training record is saved')
    return (
        gr.update(value=script),
        script,
        None,
        None,
        gr.update(value='本次训练记录已保存 The training record is saved'),
        False,
        gr.update(active=False),
        0,
        gr.update(value=_timer_text(0)),
    )


def on_timer_tick(elapsed: int, running: bool):
    if running:
        elapsed += 1
    return elapsed, gr.update(value=_timer_text(elapsed))


def format_mindfulness_history(user_id: int) -> str:
    sessions = list_mindfulness_sessions(user_id, limit=20)
    if not sessions:
        return '暂无训练记录。\nNo practice records yet.'
    lines = ['| 次数 / No. | 练习时长 / Duration | 练习日期 / DateTime |', '| --- | --- | --- |']
    for idx, item in enumerate(sessions, start=1):
        seconds = int(item.get('duration_sec') or 0)
        mm, ss = divmod(seconds, 60)
        date_text = _format_local_datetime(item.get('created_at')) or '-'
        lines.append(f'| {idx} | {mm:02d}:{ss:02d} | {date_text} |')
    return '\n'.join(lines)


def open_mind_history_modal(user_id: int):
    return gr.update(visible=True), format_mindfulness_history(user_id)


def close_mind_history_modal():
    return gr.update(visible=False)


def _diary_progress_text(step_index: int) -> str:
    return f'{step_index}/{MAX_DIARY_STEPS}'


def _guided_prompt_label(step_index: int) -> str:
    return f"{STEP_LABELS.get(step_index, f'模块{step_index}')}（{_diary_progress_text(step_index)}）"


def _guided_button_updates(step_index: int):
    step_index = max(1, min(MAX_DIARY_STEPS, int(step_index or 1)))
    return (
        gr.update(visible=step_index > 1, interactive=step_index > 1, value='\u4e0a\u4e00\u6b65 / Previous'),
        gr.update(visible=step_index < MAX_DIARY_STEPS, interactive=step_index < MAX_DIARY_STEPS, value='\u4e0b\u4e00\u6b65 / Next'),
        gr.update(visible=step_index == MAX_DIARY_STEPS, interactive=step_index == MAX_DIARY_STEPS, value='\u6211\u5199\u5b8c\u4e86 / I Finished'),
        gr.update(visible=False, interactive=False, value='\u6211\u5199\u5b8c\u4e86 / Submit'),
    )


def _free_button_updates():
    return (
        gr.update(visible=False, interactive=False, value='\u4e0a\u4e00\u6b65 / Previous'),
        gr.update(visible=False, interactive=False, value='\u4e0b\u4e00\u6b65 / Next'),
        gr.update(visible=False, interactive=False, value='\u6211\u5199\u5b8c\u4e86 / I Finished'),
        gr.update(visible=True, interactive=True, value='\u6211\u5199\u5b8c\u4e86 / Submit'),
    )


def keep_diary_state(diary_state: dict | None, diary_mode: str):
    return (
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        diary_state,
        diary_mode,
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
    )


def _free_diary_updates(content: str = '', status_text: str = ''):
    prev_btn, next_btn, finish_btn, free_btn = _free_button_updates()
    return (
        gr.update(value=_compact_text(FREE_DIARY_FIXED_PROMPT), label='\u5199\u4f5c\u63d0\u793a / Prompt', visible=True),
        gr.update(value=content or '', label='\u8bf7\u5728\u8fd9\u91cc\u8f93\u5165\u4f60\u7684\u65e5\u8bb0 / Write your journal here', visible=True),
        gr.update(value='', visible=False),
        gr.update(value=status_text),
        None,
        'free',
        prev_btn,
        next_btn,
        finish_btn,
        free_btn,
    )


def _guided_diary_updates(diary_state: dict | None, status_text: str = '', content_override: str | None = None):
    if not diary_state:
        return _free_diary_updates(content_override or '', status_text)

    session_id = int(diary_state['session_id'])
    step_index = int(diary_state['step_index'])
    prompt, saved_content = load_step_content(session_id, step_index)
    prev_btn, next_btn, finish_btn, free_btn = _guided_button_updates(step_index)
    status_value = status_text or (
        f'\u5df2\u8fdb\u5165{_guided_prompt_label(step_index)}\uff0c\u5b8c\u6210\u540e\u7ee7\u7eed\u3002\n'
        f'Now in {_guided_prompt_label(step_index)}. Continue when ready.'
    )
    return (
        gr.update(value=_compact_text(prompt), label=_guided_prompt_label(step_index), visible=True),
        gr.update(value=saved_content if content_override is None else content_override, label='\u8bf7\u5728\u8fd9\u91cc\u8f93\u5165 / Write here', visible=True),
        gr.update(value=_diary_progress_text(step_index), visible=True),
        gr.update(value=status_value),
        {'session_id': session_id, 'step_index': step_index},
        'guided',
        prev_btn,
        next_btn,
        finish_btn,
        free_btn,
    )


def _free_diary_guard_message() -> str:
    return (
        '\u5f53\u524d\u662f\u56fa\u5b9a\u5199\u4f5c\u63d0\u793a\u9875\u9762\uff0c\u8bf7\u76f4\u63a5\u70b9\u51fb\u4e0b\u65b9\u201c\u6211\u5199\u5b8c\u4e86\u201d\u3002\n'
        'You are on the fixed journal page. Please use the "I Finished" button below.'
    )


def _guided_diary_guard_message() -> str:
    return (
        '\u5f53\u524d\u662fAI\u5f15\u5bfc\u5199\u4f5c\u9875\u9762\uff0c\u8bf7\u4f7f\u7528\u201c\u4e0b\u4e00\u6b65\u201d\u6216\u201c\u6211\u5199\u5b8c\u4e86\u201d\u5b8c\u6210\u5f53\u524d\u6a21\u5757\u3002\n'
        'You are on the guided journal page. Please use "Next" or "I Finished" for the current module.'
    )


def enter_free_diary():
    return _free_diary_updates()


def enter_guided_diary(user_id: int, chat_session_id: str):
    diary_session_id, step_index, _ = start_or_resume_diary(user_id, chat_session_id)
    return _guided_diary_updates({'session_id': diary_session_id, 'step_index': step_index})


def guided_next_step(content: str, user_id: int, chat_session_id: str, diary_state: dict | None):
    if not diary_state:
        prev_btn, next_btn, finish_btn, free_btn = _guided_button_updates(1)
        return (
            gr.update(), gr.update(), gr.update(), gr.update(value='请先进入写作模块。\nPlease enter the journal module first.'), diary_state, 'guided',
            prev_btn, next_btn, finish_btn, free_btn,
        )
    if not content or not content.strip():
        prev_btn, next_btn, finish_btn, free_btn = _guided_button_updates(int(diary_state['step_index']))
        return (
            gr.update(), gr.update(), gr.update(), gr.update(value='请先完成当前模块内容，再继续下一步。\nPlease finish this module before going next.'), diary_state, 'guided',
            prev_btn, next_btn, finish_btn, free_btn,
        )

    session_id = int(diary_state['session_id'])
    step_index = int(diary_state['step_index'])
    next_step, prompt, next_content = advance_guided_step(user_id, session_id, step_index, content.strip(), chat_session_id)
    prev_btn, next_btn, finish_btn, free_btn = _guided_button_updates(next_step)
    return (
        gr.update(value=_compact_text(prompt), label=_guided_prompt_label(next_step), visible=True),
        gr.update(value=next_content or '', label='请在这里输入 / Write here', visible=True),
        gr.update(value=_diary_progress_text(next_step), visible=True),
        gr.update(value=f'已进入{_guided_prompt_label(next_step)}，请继续。\nNow in {_guided_prompt_label(next_step)}. Please continue.'),
        {'session_id': session_id, 'step_index': next_step},
        'guided',
        prev_btn,
        next_btn,
        finish_btn,
        free_btn,
    )


def guided_prev_step(content: str, diary_state: dict | None):
    if not diary_state:
        prev_btn, next_btn, finish_btn, free_btn = _guided_button_updates(1)
        return (
            gr.update(), gr.update(), gr.update(), gr.update(value='当前没有可返回的模块。\nNo previous module is available.'), diary_state, 'guided',
            prev_btn, next_btn, finish_btn, free_btn,
        )

    session_id = int(diary_state['session_id'])
    step_index = int(diary_state['step_index'])
    prev_step, prompt, prev_content = retreat_guided_step(session_id, step_index, content.strip() if content else '')
    prev_btn, next_btn, finish_btn, free_btn = _guided_button_updates(prev_step)
    return (
        gr.update(value=_compact_text(prompt), label=_guided_prompt_label(prev_step), visible=True),
        gr.update(value=prev_content or '', label='请在这里输入 / Write here', visible=True),
        gr.update(value=_diary_progress_text(prev_step), visible=True),
        gr.update(value=f'已返回{_guided_prompt_label(prev_step)}。\nBack to {_guided_prompt_label(prev_step)}.'),
        {'session_id': session_id, 'step_index': prev_step},
        'guided',
        prev_btn,
        next_btn,
        finish_btn,
        free_btn,
    )


def guided_finish(content: str, diary_state: dict | None):
    if not diary_state:
        prev_btn, next_btn, finish_btn, free_btn = _guided_button_updates(1)
        return (
            gr.update(), gr.update(), gr.update(), gr.update(value='请先开始写作，再点击完成。\nPlease start writing before finishing.'), diary_state, 'guided',
            prev_btn, next_btn, finish_btn, free_btn,
            gr.update(visible=False), gr.update(value=''), gr.update(value=''),
        )

    if not content or not content.strip():
        step_index = int(diary_state['step_index'])
        prev_btn, next_btn, finish_btn, free_btn = _guided_button_updates(step_index)
        return (
            gr.update(), gr.update(), gr.update(), gr.update(value='请先完成当前模块内容，再点击“我写完了”。\nPlease finish this module before clicking \"I Finished\".'), diary_state, 'guided',
            prev_btn, next_btn, finish_btn, free_btn,
            gr.update(visible=False), gr.update(value=''), gr.update(value=''),
        )

    session_id = int(diary_state['session_id'])
    step_index = int(diary_state['step_index'])
    diary_full, feedback = finalize_guided_diary(session_id, step_index, content.strip())
    return (
        gr.update(value='你已经完成本次写作。\nYou have completed this writing session.', label='写作提示 / Prompt', visible=True),
        gr.update(value=content.strip(), label='请在这里输入 / Write here', visible=True),
        gr.update(value=_diary_progress_text(MAX_DIARY_STEPS), visible=True),
        gr.update(value='已完成，结果已生成。\nDone. The result is ready.'),
        None,
        'guided',
        gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
        gr.update(visible=True), gr.update(value=_compact_text(diary_full)), gr.update(value=_compact_text(feedback)),
    )


def route_guided_prev_step(content: str, diary_state: dict | None, diary_mode: str):
    if diary_mode != 'guided':
        return _free_diary_updates((content or '').strip(), _free_diary_guard_message())
    return guided_prev_step(content, diary_state)


def route_guided_next_step(content: str, user_id: int, chat_session_id: str, diary_state: dict | None, diary_mode: str):
    if diary_mode != 'guided':
        return _free_diary_updates((content or '').strip(), _free_diary_guard_message())
    return guided_next_step(content, user_id, chat_session_id, diary_state)


def route_guided_finish(content: str, diary_state: dict | None, diary_mode: str):
    if diary_mode != 'guided':
        return (
            *_free_diary_updates((content or '').strip(), _free_diary_guard_message()),
            gr.update(visible=False),
            gr.update(value=''),
            gr.update(value=''),
        )
    return guided_finish(content, diary_state)


def route_free_submit_diary(content: str, user_id: int, diary_state: dict | None, diary_mode: str):
    if diary_mode != 'free':
        return (
            *_guided_diary_updates(diary_state, _guided_diary_guard_message(), content_override=(content or '').strip()),
            gr.update(visible=False),
            gr.update(value=''),
            gr.update(value=''),
        )
    return free_submit_diary(content, user_id)


def free_submit_diary(content: str, user_id: int):
    if not content or not content.strip():
        prev_btn, next_btn, finish_btn, free_btn = _free_button_updates()
        return (
            gr.update(), gr.update(), gr.update(), gr.update(value='请先写下你的内容，再点击“我写完了”。\nPlease write first, then click \"Submit\".'), None, 'free',
            prev_btn, next_btn, finish_btn, free_btn,
            gr.update(visible=False), gr.update(value=''), gr.update(value=''),
        )

    diary_full, feedback = finalize_free_diary(user_id, content.strip())
    prev_btn, next_btn, finish_btn, free_btn = _free_button_updates()
    return (
        gr.update(value=_compact_text(FREE_DIARY_FIXED_PROMPT), label='写作提示 / Prompt', visible=True),
        gr.update(value=content.strip(), label='请在这里输入你的日记 / Write your journal here', visible=True),
        gr.update(value='', visible=False),
        gr.update(value='已完成，结果已生成。\nDone. The result is ready.'),
        None,
        'free',
        prev_btn,
        next_btn,
        finish_btn,
        free_btn,
        gr.update(visible=True),
        gr.update(value=_compact_text(diary_full)),
        gr.update(value=_compact_text(feedback)),
    )


def close_diary_result_modal():
    return gr.update(visible=False)


def _resolve_diary_status(item: dict) -> str:
    status = ((item or {}).get('status') or '').strip().lower()
    if status not in {'completed', 'abandoned', 'active'}:
        status = 'completed' if (item.get('summary') or item.get('feedback')) else 'active'
    if status == 'active' and item.get('completed_at'):
        status = 'completed' if (item.get('summary') or item.get('feedback')) else 'abandoned'
    return status


def _history_status_text(status: str) -> str:
    return {
        'completed': '已完成 / Completed',
        'abandoned': '已放弃 / Abandoned',
        'active': '进行中 / Active',
    }.get(status or '', f'{status or "未知"} / {status or "Unknown"}')


def _history_view_rows(sessions: list[dict]) -> list[dict]:
    rows = []
    for idx, item in enumerate(sessions, start=1):
        rows.append(
            {
                'index': idx,
                'session_id': str(item.get('id') or ''),
                'created': _format_local_datetime(item.get('created_at')) or '-',
                'completed': _format_local_datetime(item.get('completed_at')) or '-',
                'status': _history_status_text(_resolve_diary_status(item)),
            }
        )
    return rows


def _history_table_markdown(sessions: list[dict]) -> str:
    rows = _history_view_rows(sessions)
    if not rows:
        return '\u6682\u65e0\u5386\u53f2\u65e5\u8bb0\u8bb0\u5f55\u3002\nNo journal history yet.'
    lines = [
        '| \u5e8f\u53f7 / No. | \u4f1a\u8bddID / Session ID | \u521b\u5efa\u65f6\u95f4 / Created At | \u72b6\u6001 / Status | \u5b8c\u6210\u65f6\u95f4 / Completed At | \u67e5\u770b / View |',
        '| --- | --- | --- | --- | --- | --- |',
    ]
    for row in rows:
        lines.append(
            f"| {row['index']} | {row['session_id'] or '-'} | {row['created']} | {row['status']} | {row['completed']} | "
            '\u9009\u62e9\u540e\u70b9\u51fb\u201c\u52a0\u8f7d\u8be6\u60c5\u201d / Select then click "Load" |'
        )
    return '\n'.join(lines)


def _history_option_text(row: dict) -> str:
    return (
        f"\u7b2c{row['index']}\u6761 | ID {row['session_id'] or '-'} | {row['created']} | "
        f"{row['status']} | {row['completed']}"
    )


def _history_dropdown_update(sessions: list[dict]):
    rows = _history_view_rows(sessions)
    if not rows:
        return gr.update(choices=[], value=None)
    choices = [(_history_option_text(row), row['session_id']) for row in rows]
    return gr.update(choices=choices, value=rows[0]['session_id'])


def list_diary_history_options(user_id: int):
    sessions = list_recent_diary_sessions(user_id)
    return _history_dropdown_update(sessions), _history_table_markdown(sessions)


def refresh_diary_history_modal(user_id: int):
    sessions = list_recent_diary_sessions(user_id)
    dropdown_update = _history_dropdown_update(sessions)
    table_md = _history_table_markdown(sessions)
    if not sessions:
        return dropdown_update, table_md, '', ''
    first_full, first_feedback = load_diary_detail(str(sessions[0]['id']))
    return dropdown_update, table_md, first_full, first_feedback


def _extract_session_id(selection: str) -> int | None:
    value = (selection or '').strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    head = value.split('|')[0].strip()
    return int(head) if head.isdigit() else None


def load_diary_detail(selection: str):
    session_id = _extract_session_id(selection)
    if not session_id:
        return '', ''
    session = get_diary_session(session_id)
    if not session:
        return '', ''
    return _compact_text(session.get('summary') or ''), _compact_text(session.get('feedback') or '')


def open_diary_history_modal(user_id: int):
    dropdown_update, table_md, first_full, first_feedback = refresh_diary_history_modal(user_id)
    return gr.update(visible=True), dropdown_update, table_md, first_full, first_feedback


def close_diary_history_modal():
    return gr.update(visible=False)


def close_diary_modals():
    return gr.update(visible=False), gr.update(visible=False)


def close_all_modals():
    return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)


def cancel_diary_and_back(chat_state: list[dict], user_id: int, session_id: str, diary_state: dict | None):
    if chat_state is None:
        chat_state = []
    if diary_state and diary_state.get('session_id'):
        try:
            cancel_diary(int(diary_state['session_id']))
        except Exception:
            pass
    assistant_reply = (
        '好的，我们先不写了。已经回到AI陪伴小助手，你现在最想先聊哪一件事？\n'
        'No problem, we can pause journaling for now. You are back in AI Companion. What would you like to talk about first?'
    )
    chat_state = chat_state + [{'role': 'assistant', 'content': assistant_reply}]
    save_chat_message(user_id, session_id, 'assistant', assistant_reply)
    diary_updates = enter_free_diary()
    rec_state, rec_actions, rec_yes_btn, rec_no_btn = _clear_recommendation_state()
    return _render_chat_html(chat_state), chat_state, *diary_updates, rec_state, rec_actions, rec_yes_btn, rec_no_btn




def reset_mindfulness_after_leave(script: str):
    return _mindfulness_reset(script, '\u70b9\u51fb\u201c\u5f00\u59cb\u201d\uff0c\u5c06\u64ad\u653e\u8bed\u97f3\u548c\u80cc\u666f\u97f3\u4e50\u3002\nTap Start to play voice guidance and BGM.')


def nav_to_chat(mind_script_state: str):
    rec_state, rec_actions, rec_yes_btn, rec_no_btn = _clear_recommendation_state()
    return (
        *_section_updates('chat'),
        rec_state,
        rec_actions,
        rec_yes_btn,
        rec_no_btn,
        *reset_mindfulness_after_leave(mind_script_state),
        *close_all_modals(),
    )


def nav_to_mindfulness():
    rec_state, rec_actions, rec_yes_btn, rec_no_btn = _clear_recommendation_state()
    return (
        *_section_updates('mindfulness'),
        rec_state,
        rec_actions,
        rec_yes_btn,
        rec_no_btn,
        *prepare_mindfulness_direct(),
        *close_all_modals(),
    )


def nav_to_diary(mind_script_state: str):
    rec_state, rec_actions, rec_yes_btn, rec_no_btn = _clear_recommendation_state()
    return (
        *_section_updates('diary'),
        rec_state,
        rec_actions,
        rec_yes_btn,
        rec_no_btn,
        *enter_free_diary(),
        *reset_mindfulness_after_leave(mind_script_state),
        *close_all_modals(),
    )


def _recommend_text(module: str, reason: str) -> str:
    module_name = '\u7ec3\u4e60\u5ba4\uff08\u6b63\u5ff5\u547c\u5438\uff09 / Practice Room (Mindful Breathing)' if module == 'mindfulness' else '\u65e5\u8bb0\uff08\u8868\u8fbe\u6027\u5199\u4f5c\uff09 / Journal (Expressive Writing)'
    return (
        f"{OVERALL_ADVICE}\n\n"
        f"\u76ee\u524d\u66f4\u63a8\u8350\uff1a{module_name}\u3002\u63a8\u8350\u539f\u56e0\uff1a{reason}\u3002\n"
        f"Current recommendation: {module_name}. Reason: {reason}.\n"
        '\u4f60\u613f\u610f\u73b0\u5728\u8df3\u8f6c\u5417\uff1f\nWould you like to jump now?'
    )

def initialize_session(user_id: int):
    session_id = start_new_chat_session(user_id)
    chat_state = _initial_chat_state()
    save_chat_message(user_id, session_id, 'assistant', WELCOME_TEXT)

    diary_updates = enter_free_diary()
    mind_updates = prepare_mindfulness_direct()
    rec_updates = _rec_hide_updates()

    return (
        session_id,
        chat_state,
        _render_chat_html(chat_state, {}),
        {},
        *rec_updates,
        '',
        None,
        *_section_updates('chat'),
        *diary_updates,
        *mind_updates,
        gr.update(visible=False),
        format_mindfulness_history(user_id),
        gr.update(visible=False),
        gr.update(value=''),
        gr.update(value=''),
        gr.update(visible=False),
        gr.update(choices=[], value=None),
        gr.update(value='暂无历史日记记录。\nNo journal history yet.'),
        gr.update(value=''),
        gr.update(value=''),
    )


def handle_chat(
    text,
    audio,
    chat_state,
    rec_state,
    user_id,
    session_id,
    diary_state,
    diary_mode,
    mind_script_state,
    timer_running,
    timer_elapsed,
):
    if chat_state is None:
        chat_state = []
    rec_state = rec_state or {}

    used_audio = audio is not None and (text is None or not text.strip())
    if used_audio:
        text = transcribe_audio(audio)
        if not text or not text.strip():
            detail = (iflytek.last_error or '').strip()
            if detail:
                fail_tip = (
                    '\u8bed\u97f3\u8bc6\u522b\u5931\u8d25\uff0c\u8bf7\u91cd\u8bd5\u6216\u76f4\u63a5\u8f93\u5165\u6587\u5b57\u3002\n'
                    f'Speech recognition failed. {detail}'
                )
            else:
                fail_tip = '\u8bed\u97f3\u8bc6\u522b\u5931\u8d25\uff0c\u8bf7\u91cd\u8bd5\u6216\u76f4\u63a5\u8f93\u5165\u6587\u5b57\u3002\nSpeech recognition failed, please retry or type your message.'
            chat_state = chat_state + [{'role': 'assistant', 'content': fail_tip}]
            save_chat_message(user_id, session_id, 'assistant', fail_tip)
            return (
                _render_chat_html(chat_state, rec_state),
                chat_state,
                '',
                None,
                *_section_updates('chat'),
                rec_state,
                *_rec_action_updates(rec_state),
                *keep_diary_state(diary_state, diary_mode),
                *keep_mindfulness_state(mind_script_state, timer_running, timer_elapsed),
            )

    if not text or not text.strip():
        return (
            _render_chat_html(chat_state, rec_state),
            chat_state,
            '',
            None,
            *_section_updates('chat'),
            rec_state,
            *_rec_action_updates(rec_state),
            *keep_diary_state(diary_state, diary_mode),
            *keep_mindfulness_state(mind_script_state, timer_running, timer_elapsed),
        )

    user_text = text.strip()
    direct_intent = _detect_direct_intent(user_text)

    if direct_intent:
        save_chat_message(user_id, session_id, 'user', user_text)
        if direct_intent == 'mindfulness':
            reply = '\u597d\u7684\uff0c\u5df2\u76f4\u63a5\u5e26\u4f60\u8fdb\u5165\u7ec3\u4e60\u5ba4\u3002\nDone. Taking you directly to the Practice Room.'
            save_chat_message(user_id, session_id, 'assistant', reply)
            chat_state = chat_state + [{'role': 'user', 'content': user_text}, {'role': 'assistant', 'content': reply}]
            return (
                _render_chat_html(chat_state),
                chat_state,
                '',
                None,
                *_section_updates('mindfulness'),
                {},
                *_rec_hide_updates(),
                *keep_diary_state(diary_state, diary_mode),
                *prepare_mindfulness_ai(user_id, session_id),
            )

        reply = '\u597d\u7684\uff0c\u5df2\u76f4\u63a5\u5e26\u4f60\u8fdb\u5165\u65e5\u8bb0\u3002\nDone. Taking you directly to Journal.'
        save_chat_message(user_id, session_id, 'assistant', reply)
        chat_state = chat_state + [{'role': 'user', 'content': user_text}, {'role': 'assistant', 'content': reply}]
        return (
            _render_chat_html(chat_state),
            chat_state,
            '',
            None,
            *_section_updates('diary'),
            {},
            *_rec_hide_updates(),
            *enter_guided_diary(user_id, session_id),
            *_mindfulness_reset(mind_script_state, '\u70b9\u51fb\u201c\u5f00\u59cb\u201d\uff0c\u5c06\u64ad\u653e\u8bed\u97f3\u548c\u80cc\u666f\u97f3\u4e50\u3002\nTap Start to play voice guidance and BGM.'),
        )

    if rec_state:
        if _is_affirmative(user_text):
            module = rec_state.get('module')
            accept_latest_recommendation(user_id, session_id)
            save_chat_message(user_id, session_id, 'user', user_text)
            if module == 'mindfulness':
                reply = '\u597d\u7684\uff0c\u5df2\u4e3a\u4f60\u5207\u6362\u5230\u7ec3\u4e60\u5ba4\u3002\nGreat, switched to Practice Room.'
                chat_state = chat_state + [{'role': 'user', 'content': user_text}, {'role': 'assistant', 'content': reply}]
                save_chat_message(user_id, session_id, 'assistant', reply)
                return (
                    _render_chat_html(chat_state),
                    chat_state,
                    '',
                    None,
                    *_section_updates('mindfulness'),
                    {},
                    *_rec_hide_updates(),
                    *keep_diary_state(diary_state, diary_mode),
                    *prepare_mindfulness_ai(user_id, session_id),
                )
            if module == 'diary':
                reply = '\u597d\u7684\uff0c\u5df2\u4e3a\u4f60\u5207\u6362\u5230\u65e5\u8bb0\u6a21\u5757\u3002\nGreat, switched to Journal.'
                chat_state = chat_state + [{'role': 'user', 'content': user_text}, {'role': 'assistant', 'content': reply}]
                save_chat_message(user_id, session_id, 'assistant', reply)
                return (
                    _render_chat_html(chat_state),
                    chat_state,
                    '',
                    None,
                    *_section_updates('diary'),
                    {},
                    *_rec_hide_updates(),
                    *enter_guided_diary(user_id, session_id),
                    *_mindfulness_reset(mind_script_state, '\u70b9\u51fb\u201c\u5f00\u59cb\u201d\uff0c\u5c06\u64ad\u653e\u8bed\u97f3\u548c\u80cc\u666f\u97f3\u4e50\u3002\nTap Start to play voice guidance and BGM.'),
                )

        if _is_negative(user_text):
            reply = '\u6ca1\u95ee\u9898\uff0c\u6211\u4eec\u5148\u4e0d\u8df3\u8f6c\u3002\u90a3\u4f60\u6700\u8fd1\u6700\u56f0\u6270\u7684\u4e00\u4ef6\u4e8b\u662f\u4ec0\u4e48\uff1f\nNo problem, we can stay in chat. What is bothering you most recently?'
            save_chat_message(user_id, session_id, 'user', user_text)
            save_chat_message(user_id, session_id, 'assistant', reply)
            chat_state = chat_state + [{'role': 'user', 'content': user_text}, {'role': 'assistant', 'content': reply}]
            return (
                _render_chat_html(chat_state),
                chat_state,
                '',
                None,
                *_section_updates('chat'),
                {},
                *_rec_hide_updates(),
                *keep_diary_state(diary_state, diary_mode),
                *keep_mindfulness_state(mind_script_state, timer_running, timer_elapsed),
            )

    reply, recommendation, _, _ = process_user_message(user_id, session_id, user_text)
    chat_state = chat_state + [{'role': 'user', 'content': user_text}, {'role': 'assistant', 'content': reply}]
    rec_state = recommendation or {}

    return (
        _render_chat_html(chat_state, rec_state),
        chat_state,
        '',
        None,
        *_section_updates('chat'),
        rec_state,
        *_rec_action_updates(rec_state),
        *keep_diary_state(diary_state, diary_mode),
        *keep_mindfulness_state(mind_script_state, timer_running, timer_elapsed),
    )

def accept_rec_action(chat_state, rec_state, user_id, session_id, diary_state, diary_mode, mind_script_state):
    if chat_state is None:
        chat_state = []
    rec_state = rec_state or {}
    module = rec_state.get('module')
    if module not in {'mindfulness', 'diary'}:
        return (
            _render_chat_html(chat_state),
            chat_state,
            *_section_updates('chat'),
            {},
            *_rec_hide_updates(),
            *keep_diary_state(diary_state, diary_mode),
            *keep_mindfulness_state(mind_script_state, False, 0),
        )

    accept_latest_recommendation(user_id, session_id)
    choice_text = (
        '\u8fdb\u5165\u7ec3\u4e60\u5ba4 / Go to Practice Room'
        if module == 'mindfulness'
        else '\u8fdb\u5165\u65e5\u8bb0 / Go to Journal'
    )
    reply = ('\u597d\u7684\uff0c\u5df2\u4e3a\u4f60\u5207\u6362\u5230\u7ec3\u4e60\u5ba4\u3002\nGreat, switched to Practice Room.' if module == 'mindfulness' else '\u597d\u7684\uff0c\u5df2\u4e3a\u4f60\u5207\u6362\u5230\u65e5\u8bb0\u6a21\u5757\u3002\nGreat, switched to Journal.')
    save_chat_message(user_id, session_id, 'user', choice_text)
    save_chat_message(user_id, session_id, 'assistant', reply)
    chat_state = chat_state + [{'role': 'user', 'content': choice_text}, {'role': 'assistant', 'content': reply}]

    if module == 'mindfulness':
        return (
            _render_chat_html(chat_state),
            chat_state,
            *_section_updates('mindfulness'),
            {},
            *_rec_hide_updates(),
            *keep_diary_state(diary_state, diary_mode),
            *prepare_mindfulness_ai(user_id, session_id),
        )

    return (
        _render_chat_html(chat_state),
        chat_state,
        *_section_updates('diary'),
        {},
        *_rec_hide_updates(),
        *enter_guided_diary(user_id, session_id),
        *_mindfulness_reset(mind_script_state, '\u70b9\u51fb\u201c\u5f00\u59cb\u201d\uff0c\u5c06\u64ad\u653e\u8bed\u97f3\u548c\u80cc\u666f\u97f3\u4e50\u3002\nTap Start to play voice guidance and BGM.'),
    )


def decline_rec_action(chat_state, rec_state, user_id, session_id, diary_state, diary_mode, mind_script_state):
    if chat_state is None:
        chat_state = []
    user_text = '\u6682\u4e0d\u8df3\u8f6c / Stay in Chat'
    reply = '\u6ca1\u95ee\u9898\uff0c\u6211\u4eec\u7ee7\u7eed\u804a\u3002\u6700\u8fd1\u6700\u8ba9\u4f60\u6709\u538b\u529b\u7684\u662f\u54ea\u4e00\u90e8\u5206\uff1f\nNo problem, we can keep chatting. Which part is stressing you most recently?'
    save_chat_message(user_id, session_id, 'user', user_text)
    save_chat_message(user_id, session_id, 'assistant', reply)
    chat_state = chat_state + [{'role': 'user', 'content': user_text}, {'role': 'assistant', 'content': reply}]

    return (
        _render_chat_html(chat_state),
        chat_state,
        *_section_updates('chat'),
        {},
        *_rec_hide_updates(),
        *keep_diary_state(diary_state, diary_mode),
        *keep_mindfulness_state(mind_script_state, False, 0),
    )


def build_gradio_app() -> gr.Blocks:
    with gr.Blocks(title='AI陪伴小助手') as demo:
        user_id_state = gr.State(1)
        session_id_state = gr.State('')
        chat_state = gr.State(_initial_chat_state())
        rec_state = gr.State({})
        diary_state = gr.State(None)
        diary_mode_state = gr.State('free')

        mind_script_state = gr.State(MINDFULNESS_FIXED_GUIDANCE)
        timer_elapsed_state = gr.State(0)
        timer_running_state = gr.State(False)

        with gr.Column(elem_id='app-root'):
            with gr.Column(visible=True, elem_id='section-chat') as chat_section:
                with gr.Column(elem_id='chat-panel'):
                    gr.HTML('<div class=\"top-title\">\u0041\u0049\u966a\u4f34\u5c0f\u52a9\u624b / AI Companion</div>')
                    with gr.Column(elem_id='chat-window'):
                        chat_html = gr.HTML(_render_chat_html(_initial_chat_state(), {}), elem_id='chat-html')
                        with gr.Row(elem_id='rec-actions', visible=False) as rec_actions:
                            rec_yes_btn = gr.Button('\u8fdb\u5165\u7ec3\u4e60\u5ba4 / Go to Practice Room', elem_classes=['primary'], elem_id='rec-yes-btn')
                            rec_no_btn = gr.Button('\u6682\u4e0d\u8df3\u8f6c / Stay in Chat', elem_id='rec-no-btn')
                        gr.HTML(REC_BUBBLE_JS)

                    with gr.Row(elem_id='wechat-input'):
                        audio_input = gr.Audio(
                            label='',
                            show_label=False,
                            sources=['microphone'],
                            type='numpy',
                            elem_id='wechat-audio',
                            container=False,
                            interactive=True,
                        )
                        text_input = gr.Textbox(
                            label='',
                            show_label=False,
                            placeholder='\u8f93\u5165\u6d88\u606f / Type a message',
                            lines=1,
                            max_lines=4,
                            elem_id='wechat-text',
                            container=False,
                        )
                        send_btn = gr.Button('\u53d1\u9001 / Send', elem_id='wechat-send')

            with gr.Column(visible=False, elem_id='section-mindfulness') as mindfulness_section:
                with gr.Column(elem_id='mind-shell'):
                    gr.HTML('<div class=\"top-title\">\u7ec3\u4e60\u5ba4 / Practice Room</div>')
                    with gr.Column(elem_id='mind-stage'):
                        mind_history_open_btn = gr.Button('\u8bad\u7ec3\u8bb0\u5f55 / Session History', elem_id='mind-history-open')
                        gr.HTML('<div class="breath-ball"></div>')
                        mindfulness_script = gr.Markdown(MINDFULNESS_FIXED_GUIDANCE, elem_id='mind-script')
                        timer_display = gr.Markdown(_timer_text(0), elem_id='mind-timer')
                        gr.Markdown(MINDFULNESS_OPERATION_HINT, elem_id='mind-hint')

                    with gr.Row(elem_id='mind-controls'):
                        pause_btn = gr.Button('\u6682\u505c / Pause', elem_id='mind-pause')
                        start_btn = gr.Button('\u5f00\u59cb / Start', elem_id='mind-start')
                        stop_btn = gr.Button('\u7ec8\u6b62 / Stop', elem_id='mind-stop')

                    guidance_audio = gr.Audio(
                        visible=True,
                        show_label=False,
                        container=False,
                        interactive=False,
                        autoplay=True,
                        elem_id='mind-guidance-audio',
                    )
                    music_audio = gr.Audio(
                        visible=True,
                        show_label=False,
                        container=False,
                        interactive=False,
                        autoplay=True,
                        loop=True,
                        elem_id='mind-bgm-audio',
                    )
                    mindfulness_status = gr.Markdown('\u70b9\u51fb\u201c\u5f00\u59cb\u201d\uff0c\u5c06\u64ad\u653e\u8bed\u97f3\u548c\u80cc\u666f\u97f3\u4e50\u3002\nTap Start to play voice guidance and BGM.', elem_id='mind-status')
                    timer = gr.Timer(value=1.0, active=False)

            with gr.Column(visible=False, elem_id='section-diary') as diary_section:
                with gr.Column(elem_id='diary-shell'):
                    gr.HTML('<div class=\"top-title\">\u65e5\u8bb0 / Journal</div>')
                    gr.Markdown(DIARY_INTRO_TEXT, elem_id='diary-intro')
                    diary_progress = gr.Markdown('', visible=False, elem_id='diary-progress')
                    diary_prompt = gr.Textbox(
                        label='\u5199\u4f5c\u63d0\u793a / Prompt',
                        lines=14,
                        max_lines=30,
                        interactive=False,
                        elem_id='diary-prompt',
                    )
                    diary_content = gr.Textbox(
                        label='\u8bf7\u5728\u8fd9\u91cc\u8f93\u5165\u4f60\u7684\u65e5\u8bb0 / Write your journal here',
                        lines=14,
                        max_lines=30,
                        elem_id='diary-content',
                    )
                    with gr.Row(elem_id='diary-actions'):
                        prev_btn = gr.Button('\u4e0a\u4e00\u6b65 / Previous', visible=False, elem_id='btn-prev')
                        next_btn = gr.Button('\u4e0b\u4e00\u6b65 / Next', visible=False, elem_id='btn-next')
                        finish_btn = gr.Button('\u6211\u5199\u5b8c\u4e86 / I Finished', visible=False, elem_id='btn-finish')
                        free_submit_btn = gr.Button('\u6211\u5199\u5b8c\u4e86 / Submit', visible=True, elem_id='btn-free-submit')
                    with gr.Row(elem_id='diary-tools'):
                        diary_cancel_btn = gr.Button('\u6211\u4e0d\u60f3\u5199 / Cancel', elem_id='btn-cancel')
                        diary_history_btn = gr.Button('\u5386\u53f2\u65e5\u8bb0 / History', elem_id='btn-history')
                    diary_status = gr.Markdown('', elem_id='diary-status')

            with gr.Row(elem_id='bottom-nav'):
                nav_chat_btn = gr.Button('AI\u966a\u4f34 / Chat', elem_id='nav-chat')
                nav_mindfulness_btn = gr.Button('\u7ec3\u4e60\u5ba4 / Practice Room', elem_id='nav-mind')
                nav_diary_btn = gr.Button('\u65e5\u8bb0 / Journal', elem_id='nav-diary')

            with gr.Column(visible=False, elem_classes=['overlay-modal']) as mind_history_modal:
                with gr.Column(elem_classes=['modal-card']):
                    gr.Markdown('## \u7ec3\u4e60\u5386\u53f2\u8bb0\u5f55 / Practice History')
                    mind_history_table = gr.Markdown('\u6682\u65e0\u8bad\u7ec3\u8bb0\u5f55\u3002\nNo practice records yet.', elem_id='mind-history-table')
                    mind_history_close_btn = gr.Button('\u5173\u95ed / Close')

            with gr.Column(visible=False, elem_classes=['overlay-modal']) as diary_result_modal:
                with gr.Column(elem_classes=['modal-card']):
                    gr.Markdown('## \u5199\u4f5c\u7ed3\u679c / Result')
                    result_full = gr.Textbox(label='\u6574\u5408\u540e\u7684\u5b8c\u6574\u65e5\u8bb0 / Full Journal', lines=8, interactive=False)
                    result_feedback = gr.Textbox(label='AI\u53cd\u9988 / AI Feedback', lines=4, interactive=False)
                    diary_result_close_btn = gr.Button('\u5173\u95ed / Close')

            with gr.Column(visible=False, elem_classes=['overlay-modal']) as diary_history_modal:
                with gr.Column(elem_classes=['modal-card']):
                    gr.Markdown('## \u5386\u53f2\u65e5\u8bb0 / Journal History')
                    with gr.Row():
                        history_refresh_btn = gr.Button('\u5237\u65b0\u5386\u53f2\u5217\u8868 / Refresh')
                        history_select = gr.Dropdown(label='\u5386\u53f2\u65e5\u8bb0\u9009\u62e9 / Select History', choices=[], value=None)
                        history_load_btn = gr.Button('\u52a0\u8f7d\u8be6\u60c5 / Load')
                    history_table = gr.Markdown('\u6682\u65e0\u5386\u53f2\u65e5\u8bb0\u8bb0\u5f55\u3002\nNo journal history yet.', elem_id='diary-history-table')
                    history_full = gr.Textbox(label='\u5386\u53f2\u65e5\u8bb0\u5168\u6587 / Full Text', lines=8, interactive=False)
                    history_feedback = gr.Textbox(label='\u5386\u53f2AI\u53cd\u9988 / AI Feedback', lines=4, interactive=False, elem_id='history-feedback')
                    diary_history_close_btn = gr.Button('\u5173\u95ed / Close')

        audio_input.change(transcribe_audio, inputs=[audio_input], outputs=[text_input])

        send_btn.click(
            handle_chat,
            inputs=[
                text_input,
                audio_input,
                chat_state,
                rec_state,
                user_id_state,
                session_id_state,
                diary_state,
                diary_mode_state,
                mind_script_state,
                timer_running_state,
                timer_elapsed_state,
            ],
            outputs=[
                chat_html,
                chat_state,
                text_input,
                audio_input,
                chat_section,
                mindfulness_section,
                diary_section,
                rec_state,
                rec_actions,
                rec_yes_btn,
                rec_no_btn,
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
            ],
        )

        text_input.submit(
            handle_chat,
            inputs=[
                text_input,
                audio_input,
                chat_state,
                rec_state,
                user_id_state,
                session_id_state,
                diary_state,
                diary_mode_state,
                mind_script_state,
                timer_running_state,
                timer_elapsed_state,
            ],
            outputs=[
                chat_html,
                chat_state,
                text_input,
                audio_input,
                chat_section,
                mindfulness_section,
                diary_section,
                rec_state,
                rec_actions,
                rec_yes_btn,
                rec_no_btn,
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
            ],
        )

        rec_yes_btn.click(
            accept_rec_action,
            inputs=[chat_state, rec_state, user_id_state, session_id_state, diary_state, diary_mode_state, mind_script_state],
            outputs=[
                chat_html,
                chat_state,
                chat_section,
                mindfulness_section,
                diary_section,
                rec_state,
                rec_actions,
                rec_yes_btn,
                rec_no_btn,
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
            ],
            queue=False,
        )

        rec_no_btn.click(
            decline_rec_action,
            inputs=[chat_state, rec_state, user_id_state, session_id_state, diary_state, diary_mode_state, mind_script_state],
            outputs=[
                chat_html,
                chat_state,
                chat_section,
                mindfulness_section,
                diary_section,
                rec_state,
                rec_actions,
                rec_yes_btn,
                rec_no_btn,
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
            ],
            queue=False,
        )

        nav_chat_btn.click(
            nav_to_chat,
            inputs=[mind_script_state],
            outputs=[
                chat_section,
                mindfulness_section,
                diary_section,
                rec_state,
                rec_actions,
                rec_yes_btn,
                rec_no_btn,
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
                mind_history_modal,
                diary_result_modal,
                diary_history_modal,
            ],
            queue=False,
        )

        nav_mindfulness_btn.click(
            nav_to_mindfulness,
            outputs=[
                chat_section,
                mindfulness_section,
                diary_section,
                rec_state,
                rec_actions,
                rec_yes_btn,
                rec_no_btn,
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
                mind_history_modal,
                diary_result_modal,
                diary_history_modal,
            ],
            queue=False,
        )

        nav_diary_btn.click(
            nav_to_diary,
            inputs=[mind_script_state],
            outputs=[
                chat_section,
                mindfulness_section,
                diary_section,
                rec_state,
                rec_actions,
                rec_yes_btn,
                rec_no_btn,
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
                mind_history_modal,
                diary_result_modal,
                diary_history_modal,
            ],
            queue=False,
        )

        start_btn.click(
            start_mindfulness,
            inputs=[user_id_state, session_id_state, mind_script_state],
            outputs=[
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
            ],
        )

        pause_btn.click(
            pause_mindfulness,
            inputs=[mind_script_state, timer_elapsed_state],
            outputs=[
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
            ],
        )

        stop_btn.click(
            stop_mindfulness,
            inputs=[user_id_state, mind_script_state, timer_elapsed_state],
            outputs=[
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
            ],
        )

        timer.tick(on_timer_tick, inputs=[timer_elapsed_state, timer_running_state], outputs=[timer_elapsed_state, timer_display])

        mind_history_open_btn.click(open_mind_history_modal, inputs=[user_id_state], outputs=[mind_history_modal, mind_history_table])
        mind_history_close_btn.click(close_all_modals, outputs=[mind_history_modal, diary_result_modal, diary_history_modal])

        prev_btn.click(
            route_guided_prev_step,
            inputs=[diary_content, diary_state, diary_mode_state],
            outputs=[
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
            ],
        )

        next_btn.click(
            route_guided_next_step,
            inputs=[diary_content, user_id_state, session_id_state, diary_state, diary_mode_state],
            outputs=[
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
            ],
        )

        finish_btn.click(
            route_guided_finish,
            inputs=[diary_content, diary_state, diary_mode_state],
            outputs=[
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
                diary_result_modal,
                result_full,
                result_feedback,
            ],
        )

        free_submit_btn.click(
            route_free_submit_diary,
            inputs=[diary_content, user_id_state, diary_state, diary_mode_state],
            outputs=[
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
                diary_result_modal,
                result_full,
                result_feedback,
            ],
        )

        diary_result_close_btn.click(close_all_modals, outputs=[mind_history_modal, diary_result_modal, diary_history_modal])

        diary_history_btn.click(
            open_diary_history_modal,
            inputs=[user_id_state],
            outputs=[diary_history_modal, history_select, history_table, history_full, history_feedback],
        )
        history_refresh_btn.click(
            refresh_diary_history_modal,
            inputs=[user_id_state],
            outputs=[history_select, history_table, history_full, history_feedback],
        )
        history_select.change(load_diary_detail, inputs=[history_select], outputs=[history_full, history_feedback])
        history_load_btn.click(load_diary_detail, inputs=[history_select], outputs=[history_full, history_feedback])
        diary_history_close_btn.click(close_all_modals, outputs=[mind_history_modal, diary_result_modal, diary_history_modal])

        diary_cancel_btn.click(
            cancel_diary_and_back,
            inputs=[chat_state, user_id_state, session_id_state, diary_state],
            outputs=[
                chat_html,
                chat_state,
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
                rec_state,
                rec_actions,
                rec_yes_btn,
                rec_no_btn,
            ],
        ).then(
            lambda: _section_updates('chat'),
            outputs=[chat_section, mindfulness_section, diary_section],
        ).then(
            close_all_modals,
            outputs=[mind_history_modal, diary_result_modal, diary_history_modal],
        ).then(
            reset_mindfulness_after_leave,
            inputs=[mind_script_state],
            outputs=[
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
            ],
        )

        demo.load(
            initialize_session,
            inputs=[user_id_state],
            outputs=[
                session_id_state,
                chat_state,
                chat_html,
                rec_state,
                rec_actions,
                rec_yes_btn,
                rec_no_btn,
                text_input,
                audio_input,
                chat_section,
                mindfulness_section,
                diary_section,
                diary_prompt,
                diary_content,
                diary_progress,
                diary_status,
                diary_state,
                diary_mode_state,
                prev_btn,
                next_btn,
                finish_btn,
                free_submit_btn,
                mindfulness_script,
                mind_script_state,
                guidance_audio,
                music_audio,
                mindfulness_status,
                timer_running_state,
                timer,
                timer_elapsed_state,
                timer_display,
                mind_history_modal,
                mind_history_table,
                diary_result_modal,
                result_full,
                result_feedback,
                diary_history_modal,
                history_select,
                history_table,
                history_full,
                history_feedback,
            ],
        )

    return demo
