import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from .config import Config
from .services.state_snapshot import append_state_snapshot


def _db_path_from_url(url: str) -> str:
    if url.startswith('sqlite:///'):
        return url.replace('sqlite:///', '', 1)
    if url.startswith('sqlite://'):
        return url.replace('sqlite://', '', 1)
    return url


DB_PATH = _db_path_from_url(Config.DATABASE_URL)
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


CHAT_TABLE_SQL = {
    'user_state': '''
        CREATE TABLE user_state (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            total_chars INTEGER NOT NULL DEFAULT 0,
            next_trigger_at INTEGER NOT NULL DEFAULT 250,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''',
    'user_profiles': '''
        CREATE TABLE user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL UNIQUE,
            age_group TEXT NOT NULL DEFAULT 'unknown',
            occupation TEXT NOT NULL DEFAULT 'unknown',
            current_emotion TEXT NOT NULL DEFAULT '中性',
            stress_sources TEXT NOT NULL DEFAULT '',
            therapy_preferences TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
    ''',
    'emotion_analysis': '''
        CREATE TABLE emotion_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            primary_emotion TEXT NOT NULL,
            primary_intensity INTEGER NOT NULL DEFAULT 50,
            secondary_emotion TEXT,
            secondary_intensity INTEGER,
            detail_json TEXT NOT NULL,
            analyzed_at TEXT NOT NULL
        )
    ''',
    'chat_messages': '''
        CREATE TABLE chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            emotion_primary TEXT,
            char_count INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    ''',
    'recommendations': '''
        CREATE TABLE recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            module TEXT NOT NULL,
            reason TEXT NOT NULL,
            accepted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    ''',
}


CHAT_TABLE_COLUMNS = {
    'user_state': {'session_id', 'user_id', 'total_chars', 'next_trigger_at', 'created_at', 'updated_at'},
    'user_profiles': {
        'id',
        'user_id',
        'session_id',
        'age_group',
        'occupation',
        'current_emotion',
        'stress_sources',
        'therapy_preferences',
        'created_at',
    },
    'emotion_analysis': {
        'id',
        'user_id',
        'session_id',
        'primary_emotion',
        'primary_intensity',
        'secondary_emotion',
        'secondary_intensity',
        'detail_json',
        'analyzed_at',
    },
    'chat_messages': {
        'id',
        'user_id',
        'session_id',
        'role',
        'content',
        'emotion_primary',
        'char_count',
        'created_at',
    },
    'recommendations': {'id', 'user_id', 'session_id', 'module', 'reason', 'accepted', 'created_at'},
}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _table_columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    cur.execute(f'PRAGMA table_info({table})')
    return {row[1] for row in cur.fetchall()}


def _get_user_id_by_diary_session(cur: sqlite3.Cursor, session_id: int) -> int | None:
    cur.execute('SELECT user_id FROM diary_sessions WHERE id = ?', (session_id,))
    row = cur.fetchone()
    return int(row['user_id']) if row else None


def _get_diary_meta_by_step_id(cur: sqlite3.Cursor, step_id: int) -> tuple[int | None, int | None]:
    cur.execute(
        '''
        SELECT ds.id AS session_id, ds.user_id AS user_id
        FROM diary_steps dstep
        JOIN diary_sessions ds ON ds.id = dstep.session_id
        WHERE dstep.id = ?
        ''',
        (step_id,),
    )
    row = cur.fetchone()
    if not row:
        return None, None
    return int(row['session_id']), int(row['user_id'])


def _ensure_chat_table(cur: sqlite3.Cursor, table: str, create_sql: str, required_columns: set[str]) -> None:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,))
    exists = cur.fetchone() is not None
    if not exists:
        cur.execute(create_sql)
        return
    if not required_columns.issubset(_table_columns(cur, table)):
        cur.execute(f'DROP TABLE IF EXISTS {table}')
        cur.execute(create_sql)


def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()

    for table, create_sql in CHAT_TABLE_SQL.items():
        _ensure_chat_table(cur, table, create_sql, CHAT_TABLE_COLUMNS[table])

    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS diary_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            summary TEXT,
            feedback TEXT
        )
        '''
    )

    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS diary_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            step_index INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            content TEXT,
            created_at TEXT NOT NULL
        )
        '''
    )

    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS mindfulness_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            duration_sec INTEGER NOT NULL,
            script TEXT,
            created_at TEXT NOT NULL
        )
        '''
    )

    cur.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_emotion_analysis_session ON emotion_analysis(session_id, id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_recommendations_session ON recommendations(session_id, id)')

    conn.commit()
    conn.close()


def start_new_chat_session(user_id: int) -> str:
    session_id = uuid.uuid4().hex
    now = _now_iso()
    conn = get_db()
    cur = conn.cursor()

    # Keep historical records for memory/audit; only open a new session row.
    cur.execute(
        'INSERT INTO user_state (session_id, user_id, total_chars, next_trigger_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
        (session_id, user_id, 0, Config.TRIGGER_STEP, now, now),
    )
    conn.commit()
    conn.close()
    append_state_snapshot('start_new_chat_session', user_id, chat_session_id=session_id)
    return session_id


def ensure_user_state(user_id: int, session_id: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    created = False
    cur.execute('SELECT session_id FROM user_state WHERE session_id = ?', (session_id,))
    if not cur.fetchone():
        now = _now_iso()
        cur.execute(
            'INSERT INTO user_state (session_id, user_id, total_chars, next_trigger_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
            (session_id, user_id, 0, Config.TRIGGER_STEP, now, now),
        )
        conn.commit()
        created = True
    conn.close()
    if created:
        append_state_snapshot('ensure_user_state_insert', user_id, chat_session_id=session_id)


def get_total_chars(user_id: int, session_id: str) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        'SELECT COALESCE(SUM(char_count), 0) AS total FROM chat_messages WHERE user_id = ? AND session_id = ? AND role = ?',
        (user_id, session_id, 'user'),
    )
    row = cur.fetchone()
    conn.close()
    return int(row['total']) if row else 0


def update_user_state(user_id: int, session_id: str, added_chars: int) -> dict:
    ensure_user_state(user_id, session_id)
    total_chars = get_total_chars(user_id, session_id)

    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    cur.execute(
        'UPDATE user_state SET total_chars = ?, updated_at = ? WHERE session_id = ?',
        (total_chars, now, session_id),
    )
    conn.commit()
    cur.execute('SELECT * FROM user_state WHERE session_id = ?', (session_id,))
    row = cur.fetchone()
    conn.close()
    append_state_snapshot('update_user_state', user_id, chat_session_id=session_id, note=f'added_chars={added_chars}')
    return dict(row) if row else {'total_chars': total_chars, 'next_trigger_at': Config.TRIGGER_STEP}


def bump_trigger(user_id: int, session_id: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT next_trigger_at FROM user_state WHERE session_id = ?', (session_id,))
    row = cur.fetchone()
    if row:
        now = _now_iso()
        cur.execute(
            'UPDATE user_state SET next_trigger_at = ?, updated_at = ? WHERE session_id = ?',
            (int(row['next_trigger_at']) + Config.TRIGGER_STEP, now, session_id),
        )
        conn.commit()
    conn.close()
    if row:
        append_state_snapshot('bump_trigger', user_id, chat_session_id=session_id)


def set_user_state_total(user_id: int, session_id: str, total_chars: int) -> None:
    ensure_user_state(user_id, session_id)
    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    cur.execute(
        'UPDATE user_state SET total_chars = ?, updated_at = ? WHERE session_id = ?',
        (total_chars, now, session_id),
    )
    conn.commit()
    conn.close()
    append_state_snapshot('set_user_state_total', user_id, chat_session_id=session_id)


def save_chat_message(user_id: int, session_id: str, role: str, content: str, emotion_primary: str | None = None) -> None:
    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    cur.execute(
        'INSERT INTO chat_messages (user_id, session_id, role, content, emotion_primary, char_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (user_id, session_id, role, content, emotion_primary, len(content), now),
    )
    conn.commit()
    conn.close()
    append_state_snapshot('save_chat_message', user_id, chat_session_id=session_id, note=f'role={role}')


def list_recent_messages(user_id: int, session_id: str | None = None, limit: int = 20) -> list[dict]:
    conn = get_db()
    cur = conn.cursor()

    target_session = session_id
    if not target_session:
        cur.execute('SELECT session_id FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
        latest = cur.fetchone()
        target_session = latest['session_id'] if latest else None

    if not target_session:
        conn.close()
        return []

    cur.execute(
        'SELECT * FROM chat_messages WHERE user_id = ? AND session_id = ? ORDER BY id DESC LIMIT ?',
        (user_id, target_session, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows][::-1]


def save_emotion_record(
    user_id: int,
    session_id: str,
    primary_emotion: str,
    primary_percent: int,
    detail_json: str,
    secondary_emotion: str | None = None,
    secondary_percent: int | None = None,
) -> None:
    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    cur.execute(
        '''
        INSERT INTO emotion_analysis (
            user_id,
            session_id,
            primary_emotion,
            primary_intensity,
            secondary_emotion,
            secondary_intensity,
            detail_json,
            analyzed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            user_id,
            session_id,
            primary_emotion,
            primary_percent,
            secondary_emotion,
            secondary_percent,
            detail_json,
            now,
        ),
    )
    conn.commit()
    conn.close()
    append_state_snapshot('save_emotion_record', user_id, chat_session_id=session_id)


def upsert_profile(
    user_id: int,
    session_id: str,
    age: str,
    occupation: str,
    current_emotion: str,
    stressor: str,
    healing_preference: str,
) -> None:
    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    cur.execute(
        '''
        INSERT INTO user_profiles (
            user_id,
            session_id,
            age_group,
            occupation,
            current_emotion,
            stress_sources,
            therapy_preferences,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            age_group = excluded.age_group,
            occupation = excluded.occupation,
            current_emotion = excluded.current_emotion,
            stress_sources = excluded.stress_sources,
            therapy_preferences = excluded.therapy_preferences
        ''',
        (
            user_id,
            session_id,
            age or 'unknown',
            occupation or 'unknown',
            current_emotion or '中性',
            stressor or '',
            healing_preference or '',
            now,
        ),
    )
    conn.commit()
    conn.close()
    append_state_snapshot('upsert_profile', user_id, chat_session_id=session_id)


def _profile_row_to_payload(row: sqlite3.Row | None) -> dict | None:
    if not row:
        return None
    return {
        'id': row['id'],
        'user_id': row['user_id'],
        'session_id': row['session_id'],
        'age': row['age_group'] or 'unknown',
        'occupation': row['occupation'] or 'unknown',
        'current_emotion': row['current_emotion'] or '中性',
        'stressor': row['stress_sources'] or '',
        'healing_preference': row['therapy_preferences'] or '',
        'created_at': row['created_at'],
    }


def get_latest_profile(user_id: int, session_id: str | None = None) -> dict | None:
    conn = get_db()
    cur = conn.cursor()
    if session_id:
        cur.execute(
            'SELECT * FROM user_profiles WHERE user_id = ? AND session_id = ? ORDER BY id DESC LIMIT 1',
            (user_id, session_id),
        )
    else:
        cur.execute('SELECT * FROM user_profiles WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
    row = cur.fetchone()
    conn.close()
    return _profile_row_to_payload(row)


def _emotion_row_to_payload(row: sqlite3.Row | None) -> dict | None:
    if not row:
        return None
    payload = {
        'id': row['id'],
        'user_id': row['user_id'],
        'session_id': row['session_id'],
        'primary_emotion': row['primary_emotion'] or '未知',
        'primary_percent': int(row['primary_intensity'] or 0),
        'primary_intensity': int(row['primary_intensity'] or 0),
        'secondary_emotion': row['secondary_emotion'],
        'secondary_intensity': row['secondary_intensity'],
        'detail_json': row['detail_json'],
        'created_at': row['analyzed_at'],
    }
    try:
        detail = json.loads(row['detail_json']) if row['detail_json'] else {}
        if isinstance(detail, dict):
            payload.update(detail)
    except json.JSONDecodeError:
        pass
    return payload


def get_latest_emotion(user_id: int, session_id: str | None = None) -> dict | None:
    conn = get_db()
    cur = conn.cursor()
    if session_id:
        cur.execute(
            'SELECT * FROM emotion_analysis WHERE user_id = ? AND session_id = ? ORDER BY id DESC LIMIT 1',
            (user_id, session_id),
        )
    else:
        cur.execute('SELECT * FROM emotion_analysis WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
    row = cur.fetchone()
    conn.close()
    return _emotion_row_to_payload(row)


def save_recommendation(user_id: int, session_id: str, module: str, reason: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    cur.execute(
        'INSERT INTO recommendations (user_id, session_id, module, reason, accepted, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, session_id, module, reason, 0, now),
    )
    conn.commit()
    conn.close()
    append_state_snapshot('save_recommendation', user_id, chat_session_id=session_id, note=f'module={module}')


def accept_latest_recommendation(user_id: int, session_id: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        '''
        UPDATE recommendations
        SET accepted = 1
        WHERE id = (
            SELECT id FROM recommendations
            WHERE user_id = ? AND session_id = ?
            ORDER BY id DESC
            LIMIT 1
        )
        ''',
        (user_id, session_id),
    )
    conn.commit()
    conn.close()
    append_state_snapshot('accept_latest_recommendation', user_id, chat_session_id=session_id)


def create_diary_session(user_id: int) -> int:
    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    cur.execute(
        'INSERT INTO diary_sessions (user_id, status, created_at) VALUES (?, ?, ?)',
        (user_id, 'active', now),
    )
    session_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    append_state_snapshot('create_diary_session', user_id, diary_session_id=session_id)
    return session_id


def add_diary_step(session_id: int, step_index: int, prompt: str, content: str | None = None) -> None:
    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    cur.execute(
        'INSERT INTO diary_steps (session_id, step_index, prompt, content, created_at) VALUES (?, ?, ?, ?, ?)',
        (session_id, step_index, prompt, content, now),
    )
    user_id = _get_user_id_by_diary_session(cur, session_id)
    conn.commit()
    conn.close()
    append_state_snapshot(
        'add_diary_step',
        user_id,
        diary_session_id=session_id,
        note=f'step_index={step_index}',
    )


def update_diary_step_content(step_id: int, content: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    diary_session_id, user_id = _get_diary_meta_by_step_id(cur, step_id)
    cur.execute('UPDATE diary_steps SET content = ? WHERE id = ?', (content, step_id))
    conn.commit()
    conn.close()
    append_state_snapshot('update_diary_step_content', user_id, diary_session_id=diary_session_id)


def get_diary_steps(session_id: int) -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM diary_steps WHERE session_id = ? ORDER BY step_index ASC', (session_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def complete_diary_session(session_id: int, summary: str, feedback: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    user_id = _get_user_id_by_diary_session(cur, session_id)
    cur.execute(
        'UPDATE diary_sessions SET status = ?, completed_at = ?, summary = ?, feedback = ? WHERE id = ?',
        ('completed', now, summary, feedback, session_id),
    )
    conn.commit()
    conn.close()
    append_state_snapshot('complete_diary_session', user_id, diary_session_id=session_id)


def get_active_diary_session(user_id: int) -> dict | None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        'SELECT * FROM diary_sessions WHERE user_id = ? AND status = ? ORDER BY id DESC LIMIT 1',
        (user_id, 'active'),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_recent_diary_sessions(user_id: int, limit: int = 5) -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM diary_sessions WHERE user_id = ? ORDER BY id DESC LIMIT ?', (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_diary_session(session_id: int) -> dict | None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM diary_sessions WHERE id = ?', (session_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def abandon_diary_session(session_id: int) -> None:
    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    user_id = _get_user_id_by_diary_session(cur, session_id)
    cur.execute(
        'UPDATE diary_sessions SET status = ?, completed_at = ? WHERE id = ?',
        ('abandoned', now, session_id),
    )
    conn.commit()
    conn.close()
    append_state_snapshot('abandon_diary_session', user_id, diary_session_id=session_id)


def add_mindfulness_session(user_id: int, duration_sec: int, script: str | None) -> None:
    conn = get_db()
    cur = conn.cursor()
    now = _now_iso()
    cur.execute(
        'INSERT INTO mindfulness_sessions (user_id, duration_sec, script, created_at) VALUES (?, ?, ?, ?)',
        (user_id, duration_sec, script or '', now),
    )
    conn.commit()
    conn.close()
    append_state_snapshot('add_mindfulness_session', user_id, note=f'duration_sec={duration_sec}')


def list_mindfulness_sessions(user_id: int, limit: int = 5) -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM mindfulness_sessions WHERE user_id = ? ORDER BY id DESC LIMIT ?', (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]
