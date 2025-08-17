# init_db.py
import sqlite3
import sys
from config import DB_PATH

RETENTION_DAYS = 30

CREATE_SENSOR_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    soil_moisture REAL,
    air_temperature REAL,
    air_humidity REAL,
    light_intensity REAL,
    water_level REAL,
    strawberry_ripeness_score REAL,
    strawberry_ripeness_text TEXT
);
"""

def _connect() -> sqlite3.Connection:
    print(f"[init_db] ▶ DB 연결 시도 → {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_or_reset_interactive() -> sqlite3.Connection:
    """
    - 사용자 테이블이 하나라도 있으면: 초기화할지 질문
      [y] → 모든 테이블 삭제 + VACUUM + 스키마 재생성
      [n] → 변경 없이 유지
    - 사용자 테이블이 없으면: 스키마 생성
    - 항상 '현재 상태의 연결'을 반환(스크립트 실행 시에는 __main__에서 닫아줌)
    """
    conn = _connect()
    cur = conn.cursor()

    print("[init_db] 사용자 테이블 존재 여부 확인 중...")
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1")
    has_tables = (cur.fetchone() is not None)

    if has_tables:
        ans = input(">> 기존 테이블이 있습니다. 빈 DB로 초기화할까요? [y/N] ").strip().lower()
        if ans == "y":
            print("[init_db] 모든 사용자 테이블 삭제 중...")
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [name for (name,) in cur.fetchall()]
            for t in tables:
                print(f"  - DROP TABLE {t}")
                cur.execute(f"DROP TABLE IF EXISTS {t}")
            conn.commit()

            print("[init_db] VACUUM 실행(디스크 공간 회수)...")
            cur.execute("VACUUM")
            conn.commit()

            print("[init_db] 스키마 재생성 중...")
            conn.execute(CREATE_SENSOR_TABLE_SQL)
            conn.commit()
            print("[init_db] ✅ 전체 초기화 완료")
        else:
            print("[init_db] 변경 없이 유지합니다.")
    else:
        print("[init_db] 사용자 테이블이 없습니다. 스키마 생성 중...")
        conn.execute(CREATE_SENSOR_TABLE_SQL)
        conn.commit()
        print(f"[init_db] ✅ 스키마 생성 완료 → {DB_PATH}")

    return conn

def clean_old_records() -> int:
    """
    sensor_data에서 '30일 이전' 레코드 삭제.
    (사용자 개입 없이 서버나 스케줄러에서 주기적으로 호출하도록 설계)
    """
    print(f"[clean] ▶ {RETENTION_DAYS}일 이전 레코드 정리 시작...")
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM sensor_data WHERE datetime(timestamp) < datetime('now', ?)",
            (f"-{RETENTION_DAYS} days",)
        )
        deleted = cur.rowcount or 0
        conn.commit()
        print(f"[clean] ✅ 정리 완료: 삭제 {deleted}건")
        return deleted
    finally:
        conn.close()
        print("[clean] ▶ DB 연결 종료")

def _usage():
    print("사용법:\n"
          "  python init_db.py           # 대화형 초기화(존재 시 물어봄)\n"
          "  python init_db.py init      # 대화형 초기화(위와 동일)\n"
          "  python init_db.py clean     # 30일 이전 데이터 정리\n")

if __name__ == "__main__":
    # 인자 없으면 곧바로 '대화형 초기화' 실행
    if len(sys.argv) == 1:
        conn = init_or_reset_interactive()
        conn.close()
        print("[init_db] ▶ 종료")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == "init":
        conn = init_or_reset_interactive()
        conn.close()
        print("[init_db] ▶ 종료")
    elif cmd == "clean":
        clean_old_records()
        print("[init_db] ▶ 종료")
    else:
        _usage()