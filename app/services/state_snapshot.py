import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ..config import BASE_DIR, Config


def _db_path_from_url(url: str) -> str:
    if url.startswith('sqlite:///'):
        return url.replace('sqlite:///', '', 1)
    if url.startswith('sqlite://'):
        return url.replace('sqlite://', '', 1)
    return url


SNAPSHOT_DIR = BASE_DIR / 'storage'
SNAPSHOT_FILE = SNAPSHOT_DIR / 'state.json'


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path_from_url(Config.DATABASE_URL), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_rows(cur: sqlite3.Cursor, sql: str, params: tuple = ()) -> list[dict]:
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def _safe_load() -> list[dict]:
    if not SNAPSHOT_FILE.exists():
        return []
    try:
        data = json.loads(SNAPSHOT_FILE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def list_state_snapshots(user_id: int | None = None) -> list[dict]:
    records = _safe_load()
    if user_id is None:
        return records
    return [item for item in records if int(item.get('user_id', -1)) == int(user_id)]


def _build_user_tables(user_id: int) -> dict:
    conn = _connect()
    cur = conn.cursor()
    try:
        diary_sessions = _fetch_rows(
            cur,
            'SELECT * FROM diary_sessions WHERE user_id = ? ORDER BY id ASC',
            (user_id,),
        )
        diary_ids = [int(row['id']) for row in diary_sessions]

        diary_steps: list[dict] = []
        if diary_ids:
            placeholders = ','.join(['?'] * len(diary_ids))
            diary_steps = _fetch_rows(
                cur,
                f'SELECT * FROM diary_steps WHERE session_id IN ({placeholders}) ORDER BY id ASC',
                tuple(diary_ids),
            )

        tables = {
            'user_state': _fetch_rows(
                cur,
                'SELECT * FROM user_state WHERE user_id = ? ORDER BY created_at ASC',
                (user_id,),
            ),
            'chat_messages': _fetch_rows(
                cur,
                'SELECT * FROM chat_messages WHERE user_id = ? ORDER BY id ASC',
                (user_id,),
            ),
            'user_profiles': _fetch_rows(
                cur,
                'SELECT * FROM user_profiles WHERE user_id = ? ORDER BY id ASC',
                (user_id,),
            ),
            'emotion_analysis': _fetch_rows(
                cur,
                'SELECT * FROM emotion_analysis WHERE user_id = ? ORDER BY id ASC',
                (user_id,),
            ),
            'recommendations': _fetch_rows(
                cur,
                'SELECT * FROM recommendations WHERE user_id = ? ORDER BY id ASC',
                (user_id,),
            ),
            'diary_sessions': diary_sessions,
            'diary_steps': diary_steps,
            'mindfulness_sessions': _fetch_rows(
                cur,
                'SELECT * FROM mindfulness_sessions WHERE user_id = ? ORDER BY id ASC',
                (user_id,),
            ),
        }
    finally:
        conn.close()
    return tables


def append_state_snapshot(
    event: str,
    user_id: int | None,
    chat_session_id: str | None = None,
    diary_session_id: int | None = None,
    note: str | None = None,
) -> None:
    if not user_id:
        return
    try:
        records = _safe_load()
        entry = {
            'step': len(records) + 1,
            'timestamp': datetime.utcnow().isoformat(),
            'event': event,
            'user_id': int(user_id),
            'chat_session_id': chat_session_id,
            'diary_session_id': diary_session_id,
            'note': note or '',
            'tables': _build_user_tables(int(user_id)),
        }
        records.append(entry)

        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        # Snapshot is for observability only; it should never block core features.
        return
