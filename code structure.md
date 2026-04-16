# AI 心理疗愈陪伴平台 - 项目架构文档

## 1. 项目概述
本项目是基于DeepSeek 大模型 + 讯飞语音（STT/TTS）+ Gradio 可视化界面搭建的 AI 心理疗愈平台，包含AI 陪伴对话、正念呼吸练习、表达性写作日记三大核心模块，支持情绪分析、用户画像、智能推荐、语音交互等能力。

- 框架：FastAPI + Flask + Gradio
- 模型：DeepSeek API
- 语音：科大讯飞 STT/TTS
- 数据库：SQLite
- 部署：Windows 一键启动

---

## 2. 整体架构分层
```
┌─────────────────────────────────────────────────────┐
│                   前端界面层 (Gradio)                 │
├───────────────┬───────────────┬─────────────────────┤
│  AI 陪伴对话   │ 正念呼吸练习室 │ 表达性写作日记      │
└───────────────┴───────────────┴─────────────────────┘

┌─────────────────────────────────────────────────────┐
│                   接口网关层 (FastAPI+Flask)          │
└─────────────────────────────────────────────────────┘

┌────────────────┬────────────┬────────────┬──────────┐
│ 业务逻辑层      │ 服务封装层  │  数据层    │  配置层  │
│ - chat.py      │ - 模型调用  │ - db.py    │ - .env   │
│ - diary.py     │ - 语音服务  │ - 快照(存档)│ - config │
│ - mindfulness.py│- 提示词模板│            │          │
└────────────────┴────────────┴────────────┴──────────┘

┌─────────────────────────────────────────────────────┐
│                    外部依赖服务                       │
│ - DeepSeek API  │  讯飞语音 API  │  SQLite 文件库     │
└─────────────────────────────────────────────────────┘
```

---

## 3. 目录结构
```
/
├── .env                      # 密钥、端口、语音配置
├── main.py                   # 项目入口，服务挂载
├── requirements.txt          # 依赖清单
├── start_demo.bat            # Windows 一键启动脚本
├── therapy_users.db          # 用的是轻量级的 SQLite 数据库，持久化存储用户的所有核心数据，确保用户信息在系统重启后不会丢失
│
├── app/
│   ├── __init__.py
│   ├── config.py             # 统一配置读取，设置250达到跳转条件
│   ├── db.py                 # 数据库建表与 CRUD
│   │
│   ├── logic/                # 业务逻辑核心
│   │   ├── __init__.py
│   │   ├── chat.py           # 对话、情绪分析、画像更新
│   │   ├── diary.py          # 日记分步引导、生成、反馈
│   │   └── mindfulness.py    # 正念引导词、音频生成
│   │
│   ├── services/             # 外部服务封装
│   │   ├── __init__.py
│   │   ├── deepseek_client.py # DeepSeek API 封装
│   │   ├── iflytek_client.py  # 讯飞 STT/TTS 封装
│   │   ├── prompts.py         # 所有提示词模板
│   │   ├── recommendation.py  # 模块推荐规则
│   │   ├── utils.py           # JSON、音频分片工具
│   │   └── state_snapshot.py  # 状态快照（调试用），快照逻辑：读写 storage/state.json
│   │
│   └── ui/
│       ├── __init__.py
│       └── gradio_app.py     # Gradio 界面、交互、样式
├── storage/             # 新增！临时状态存储目录
│   └── state.json       # 状态快照落地文件（JSON格式）
├── assets/
│   ├── music/                # 正念背景音乐
│   └── generated/            # TTS 音频输出


```

---

## 4. 核心模块说明
### 4.1 入口与服务挂载
- `main.py`：统一启动入口
  - 初始化数据库
  - 启动 Flask API
  - 挂载 Gradio 前端
  - FastAPI 作为宿主统一托管

### 4.2 三大功能模块
1. AI 陪伴小助手
   - 情绪共情对话（多模态输入——语音+文字）
   - 字数触发：默认 250 字自动分析
   - 情绪识别 + 用户画像更新
   - 智能推荐正念/日记模块
   - 中英双语回复

2. 正念呼吸练习室
   - AI 生成正念引导词
   - 讯飞 TTS 语音播报
   - 随机背景纯音乐
   - 计时、暂停、停止、记录历史

3. 表达性写作日记
   - 分步引导写作（4步）
   - 自由写作模式
   - 内容整合 + AI 反馈
   - 历史日记保存与查看

### 4.3 情绪与画像机制
- 触发条件：用户累计输入 ≥ 250 字 自动触发
- 流程：
  1. 情绪分析（最多 5 种情绪）
  2. 更新用户画像（年龄、职业、情绪、压力源、偏好）
  3. 生成疗愈建议
  4. 推荐对应模块

### 4.4 智能推荐规则
- 焦虑/紧张/压力 → 推荐正念练习室
- 悲伤/委屈/失落 → 推荐表达性写作日记
- 可根据用户疗愈偏好优先推荐

---

## 5. 数据库设计（SQLite）
文件：`therapy_users.db`

- `user_state`：用户字数统计、触发状态
- `user_profiles`：用户画像
- `emotion_records`：情绪分析记录
- `chat_messages`：对话消息
- `diary_sessions`：日记会话
- `diary_steps`：日记分步内容
- `recommendations`：推荐记录
- `mindfulness_sessions`：正念练习记录

---

## 6. 外部 API 依赖
1. DeepSeek API
   - 对话回复
   - 情绪分析
   - 用户画像更新
   - 正念/日记内容生成

2. 科大讯飞 API
   - STT：语音转文字
   - TTS：文字转语音（叶子音色）
   - 支持语速、音调、音量调节

---

## 7. 关键配置项
- 端口：`PORT=7881`
- 触发字数：`TRIGGER_STEP=250`
- 最大情绪类别：`MAX_EMOTIONS=5`
- TTS 音色：`IFLYTEK_TTS_VOICE=x4_yezi`
- 调试模式：`DEBUG=True`

---

## 8. 启动与运行
1. 安装依赖：`pip install -r requirements.txt`
2. 配置 `.env` 中的 API 密钥
3. 运行：`python main.py` 或双击 `start_demo.bat`
4. 访问：`http://localhost:7881`

---

## 9. 技术栈
- 后端：FastAPI、Flask、Uvicorn
- 前端：Gradio
- 数据库：SQLite
- 模型：DeepSeek Chat
- 语音：讯飞 STT/TTS
- 工具：python-dotenv、websocket、numpy

---
