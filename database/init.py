# database/init.py (개선된 버전)

from pathlib import Path
import sqlite3
from typing import Optional

DB_PATH: Optional[str] = None

# ... (set_db_path, _resolve_db_path, connect 함수는 이전과 동일) ...
def set_db_path(path: str) -> None:
    global DB_PATH
    DB_PATH = path

def _resolve_db_path() -> str:
    if DB_PATH:
        return DB_PATH
    try:
        from config import DB_PATH as CFG_DB_PATH
        return str(CFG_DB_PATH)
    except Exception:
        return "database.db"

def connect() -> sqlite3.Connection:
    path = _resolve_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_tables() -> None:
    sql_sensor = """
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        soil_moisture REAL,
        air_temperature REAL,
        air_humidity REAL,
        light_intensity REAL,
        water_level REAL
    );
    """

    sql_img = """
    CREATE TABLE IF NOT EXISTS image_capture (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        file_path TEXT NOT NULL UNIQUE
    );
    """
    #                       ▲▲▲▲▲▲ (개선) UNIQUE 제약 조건 추가

    sql_ai = """
    CREATE TABLE IF NOT EXISTS ai_result (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_id INTEGER NOT NULL,
        ripeness_score REAL,
        flower_count INTEGER,
    #   ▲▲▲▲▲▲▲▲▲▲▲▲ (개선) score -> count, REAL -> INTEGER 로 변경
        ripeness_text TEXT,
        flower_text TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(image_id) REFERENCES image_capture(id) ON DELETE CASCADE
    );
    """
    idx_sensor_ts = "CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_data (timestamp DESC);"
    idx_img_ts = "CREATE INDEX IF NOT EXISTS idx_image_timestamp ON image_capture (timestamp DESC);"
    idx_ai_img = "CREATE INDEX IF NOT EXISTS idx_ai_image_id ON ai_result (image_id);"

    with connect() as conn:
        conn.execute(sql_sensor)
        conn.execute(sql_img)
        conn.execute(sql_ai)
        conn.execute(idx_sensor_ts)
        conn.execute(idx_img_ts)
        conn.execute(idx_ai_img)
        conn.commit()

def init_db(drop_all: bool = False) -> None:
    # ... (이전과 동일) ...
    with connect() as conn:
        cur = conn.cursor()
        if drop_all:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            for (tname,) in cur.fetchall():
                cur.execute(f"DROP TABLE IF EXISTS {tname}")
            conn.commit()
            cur.execute("VACUUM")
            conn.commit()
    create_tables()

# (개선) 어떤 테이블이든 정리할 수 있도록 함수 일반화
def clean_old_records(table_name: str, retention_days: int) -> int:
    """지정된 테이블에서 retention_days보다 오래된 레코드를 삭제합니다."""
    # 테이블 이름에 허용되지 않는 문자가 있는지 간단히 확인 (SQL Injection 방지)
    if not table_name.isidentifier():
        raise ValueError(f"Invalid table name: {table_name}")

    with connect() as conn:
        cur = conn.cursor()
        # f-string을 사용해 동적으로 쿼리 생성
        query = f"DELETE FROM {table_name} WHERE datetime(timestamp) < datetime('now', ?)"
        cur.execute(query, (f"-{retention_days} days",))
        deleted = cur.rowcount or 0
        conn.commit()
        return deleted