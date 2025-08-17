# db_manager.py

import sqlite3
from config import DB_PATH # config.py에서 DB_PATH를 가져옵니다.

def get_db_connection():
    """데이터베이스 연결 객체를 반환합니다."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # 결과를 딕셔너리 형태로 가져올 수 있도록 설정
    return conn

def save_sensor_data(soil_moisture, air_temperature, air_humidity, 
                     light_intensity, water_level, 
                     strawberry_ripeness_score=None, strawberry_ripeness_text=None):
    """
    센서 데이터를 데이터베이스에 저장합니다.
    딸기 익은 정도 데이터는 선택 사항입니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO sensor_data (
                soil_moisture, air_temperature, air_humidity, light_intensity, water_level,
                strawberry_ripeness_score, strawberry_ripeness_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (soil_moisture, air_temperature, air_humidity, light_intensity, water_level,
              strawberry_ripeness_score, strawberry_ripeness_text))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"데이터 저장 중 오류 발생: {e}")
        return False
    finally:
        conn.close()

def get_all_sensor_data():
    """데이터베이스의 모든 센서 데이터를 최신순으로 반환합니다."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sensor_data ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_latest_sensor_data():
    """데이터베이스의 가장 최신 센서 데이터 1개를 반환합니다."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sensor_data ORDER BY id DESC LIMIT 1')
    latest_data = cursor.fetchone()
    conn.close()
    return latest_data

# 이 파일 자체를 직접 실행할 경우 데이터베이스 초기화 함수를 호출할 수 있습니다.
# 하지만 보통은 init_db.py를 별도로 두는 것이 더 명확합니다.
if __name__ == '__main__':
    # 이 부분은 init_db.py의 내용과 유사합니다.
    # db_manager.py에서는 주로 데이터 조작 함수를 정의합니다.
    # 데이터베이스 초기화는 init_db.py에서 담당하는 것이 좋습니다.
    print("db_manager.py는 주로 데이터베이스 조작 함수를 정의합니다.")
    print("데이터베이스 초기화는 init_db.py를 실행하세요.")