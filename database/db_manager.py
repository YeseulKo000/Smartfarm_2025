# database/db_manager.py
from typing import Any, Dict, List, Optional
import sqlite3
from database import init as dbcore  # 연결/경로/스키마 관리는 코어에 위임

# 외부에서 DB 경로를 주입할 때(app.py에서) 사용
def set_db_path(path: str) -> None:
    dbcore.set_db_path(path)

def get_db_connection():
    # 코어의 connect()를 그대로 사용 (foreign_keys ON, row_factory 설정됨)
    return dbcore.connect()

# 숫자 변환 헬퍼
def _to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ValueError(f"numeric expected, got {v!r}")

def save_sensor_data(
    soil_moisture: Optional[float] = None,
    air_temperature: Optional[float] = None,
    air_humidity: Optional[float] = None,
    light_intensity: Optional[float] = None,
    water_level: Optional[float] = None,
) -> int:
    sm = _to_float(soil_moisture)
    at = _to_float(air_temperature)
    ah = _to_float(air_humidity)
    li = _to_float(light_intensity)
    wl = _to_float(water_level)
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sensor_data
            (soil_moisture, air_temperature, air_humidity, light_intensity, water_level)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sm, at, ah, li, wl),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.Error as e:
        raise RuntimeError(f"DB insert failed: {e}") from e
    finally:
        conn.close()

def get_all_sensor_data() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, timestamp, soil_moisture, air_temperature, air_humidity,
                   light_intensity, water_level
            FROM sensor_data
            ORDER BY datetime(timestamp) DESC, id DESC
            """
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        raise RuntimeError(f"DB select failed: {e}") from e
    finally:
        conn.close()

def get_latest_sensor_data() -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, timestamp, soil_moisture, air_temperature, air_humidity,
                   light_intensity, water_level
            FROM sensor_data
            ORDER BY datetime(timestamp) DESC, id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        raise RuntimeError(f"DB select failed: {e}") from e
    finally:
        conn.close()

def get_recent_combined_data(limit: int = 20) -> List[Dict[str, Any]]:
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        raise ValueError(f"limit must be int-like, got {limit!r}")
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, timestamp, soil_moisture, air_temperature, air_humidity,
                   light_intensity, water_level
            FROM sensor_data
            ORDER BY datetime(timestamp) DESC, id DESC
            LIMIT ?
            """,
            (lim,),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        raise RuntimeError(f"DB select failed: {e}") from e
    finally:
        conn.close()


def save_image_capture(file_path: str) -> int:
    """이미지 저장 기록."""
    if not file_path:
        raise ValueError("file_path is required")
    abs_path = file_path  # app.py에서 이미 절대경로로 넘겨줌
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO image_capture (file_path) VALUES (?)",
            (abs_path,),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.Error as e:
        raise RuntimeError(f"DB insert image_capture failed: {e}") from e
    finally:
        conn.close()


def find_image_id_by_path(file_path: str):
    """절대경로 기준으로 image_capture.id 조회 (없으면 None)."""
    import os
    abs_path = os.path.abspath(file_path)
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM image_capture WHERE file_path = ?", (abs_path,))
        row = cur.fetchone()
        return row["id"] if row else None
    except sqlite3.Error as e:
        raise RuntimeError(f"DB select image_capture failed: {e}") from e
    finally:
        conn.close()


def save_ai_result(
    image_id: int,
    ripeness_score: Optional[float] = None,
    flower_score: Optional[float] = None,
    ripeness_text: Optional[str] = None,
    flower_text: Optional[str] = None,
) -> int:
    """AI 분석 결과 저장 (image_id 필수)."""
    if not isinstance(image_id, int):
        raise ValueError("image_id must be int")
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ai_result
            (image_id, ripeness_score, flower_score, ripeness_text, flower_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (image_id, ripeness_score, flower_score, ripeness_text, flower_text),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.Error as e:
        raise RuntimeError(f"DB insert ai_result failed: {e}") from e
    finally:
        conn.close()