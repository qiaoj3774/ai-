# 数据库结构说明

数据库文件：`therapy_users.db`

## user_state（对话字数触发状态）
- user_id (INTEGER, PK)
- total_chars (INTEGER)
- next_trigger_at (INTEGER)
- created_at (TEXT)
- updated_at (TEXT)

## user_profiles（用户画像）
- user_id (INTEGER, PK)
- age (TEXT)
- occupation (TEXT)
- current_emotion (TEXT)
- stressor (TEXT)
- healing_preference (TEXT)
- updated_at (TEXT)

## emotion_records（情绪分析记录）
- id (INTEGER, PK)
- user_id (INTEGER)
- primary_emotion (TEXT)
- primary_percent (INTEGER)
- detail_json (TEXT)
- created_at (TEXT)

## chat_messages（对话记录）
- id (INTEGER, PK)
- user_id (INTEGER)
- role (TEXT)
- content (TEXT)
- emotion_primary (TEXT)
- char_count (INTEGER)
- created_at (TEXT)

## diary_sessions（日记会话）
- id (INTEGER, PK)
- user_id (INTEGER)
- status (TEXT)
- created_at (TEXT)
- completed_at (TEXT)
- summary (TEXT)
- feedback (TEXT)
状态说明：`active` 进行中，`completed` 已完成，`abandoned` 用户退出。

## diary_steps（日记分步内容）
- id (INTEGER, PK)
- session_id (INTEGER)
- step_index (INTEGER)
- prompt (TEXT)
- content (TEXT)
- created_at (TEXT)

## recommendations（疗愈推荐）
- id (INTEGER, PK)
- user_id (INTEGER)
- module (TEXT)
- reason (TEXT)
- accepted (INTEGER)
- created_at (TEXT)

---

建议截图：
- 创建后的空表结构（见 `docs/screenshots/04_db_schema.png`）
- 有数据时的示例记录（见 `docs/screenshots/05_db_sample.png`）
