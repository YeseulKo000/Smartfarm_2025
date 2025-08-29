# database/db_manager.py
from typing import Any, Dict, List, Optional
import sqlite3
import os
from database import init as dbcore

# (기존 set_db_path, get_db_connection, _to_float, 센서 관련 함수들은 동일하므로 생략)
# ... (이전 코드와 동일한 부분) ...

def set_db_path(path: str) -> None:
    dbcore.set_db_path(path)

def get_db_connection():
    return dbcore.connect()

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
        cur.execute("SELECT * FROM sensor_data ORDER BY datetime(timestamp) DESC, id DESC")
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
        cur.execute("SELECT * FROM sensor_data ORDER BY datetime(timestamp) DESC, id DESC LIMIT 1")
        row = cur.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        raise RuntimeError(f"DB select failed: {e}") from e
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ AI 및 이미지 관련 (개선된 부분) ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# ---------------------------------------------------------------------------

def save_image_analysis_result(
    file_path: str,
    ripeness_score: Optional[float] = None,
    flower_count: Optional[int] = None, # score -> count 로 이름 변경
    ripeness_text: Optional[str] = None,
    flower_text: Optional[str] = None,
) -> Dict[str, int]:
    """
    (개선된 통합 함수)
    이미지 경로와 AI 분석 결과를 한 번의 트랜잭션으로 DB에 저장합니다.
    - image_capture 테이블에 파일 경로 저장
    - ai_result 테이블에 분석 결과 저장
    """
    if not file_path:
        raise ValueError("file_path is required")

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # 1. image_capture 테이블에 이미지 경로 저장
        cur.execute(
            "INSERT INTO image_capture (file_path) VALUES (?)",
            (file_path,)
        )
        image_id = cur.lastrowid # 방금 생성된 이미지 ID 가져오기

        # 2. ai_result 테이블에 위 ID를 사용하여 분석 결과 저장
        cur.execute(
            """
            INSERT INTO ai_result
            (image_id, ripeness_score, flower_count, ripeness_text, flower_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (image_id, ripeness_score, flower_count, ripeness_text, flower_text),
        )
        ai_result_id = cur.lastrowid

        # 3. 모든 작업이 성공하면 최종 확정(commit)
        conn.commit()

        return {"image_id": image_id, "ai_result_id": ai_result_id}

    except sqlite3.Error as e:
        conn.rollback() # 오류 발생 시 모든 작업을 취소
        raise RuntimeError(f"DB transaction failed for image analysis: {e}") from e
    finally:
        conn.close()


def find_image_id_by_path(file_path: str) -> Optional[int]:
    """절대경로 기준으로 image_capture.id 조회 (없으면 None)."""
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
        
def get_all_analysis_data(limit: int = 30) -> List[Dict[str, Any]]:
    """
    이미지 캡처 기록과 AI 분석 결과를 합쳐서 최신순으로 가져옵니다.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # image_capture 테이블과 ai_result 테이블을 id로 연결(JOIN)합니다.
        cur.execute(
            """
            SELECT
                ic.id,
                ic.timestamp,
                ic.file_path,
                ar.ripeness_text,
                ar.ripeness_score,
                ar.flower_count
            FROM image_capture ic
            JOIN ai_result ar ON ic.id = ar.image_id
            ORDER BY datetime(ic.timestamp) DESC, ic.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        raise RuntimeError(f"DB select failed for analysis data: {e}") from e
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 기존 함수 (대체됨) ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# ---------------------------------------------------------------------------

# (개선된 'save_image_analysis_result' 함수로 대체되었으므로 주석 처리 또는 삭제 권장)
# def save_image_capture(file_path: str) -> int:
#     ...

# (개선된 'save_image_analysis_result' 함수로 대체되었으므로 주석 처리 또는 삭제 권장)
# def save_ai_result(...) -> int:
#     ...