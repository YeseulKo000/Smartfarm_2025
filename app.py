import os
import time
import logging
import threading
from datetime import timedelta
from flask import Flask, render_template, request, jsonify

# --- 1. 프로젝트 필수 모듈 임포트 (코드 2 기반) ---
try:
    from config import PORT
    from database import db_manager
    from ai_module.strawberry_analyzer import analyze_ripeness, analyze_flowers
except ImportError as e:
    logging.error(f"필수 모듈 로딩 실패: {e}. 'config.py', 'database/db_manager.py', 'ai_module' 폴더가 올바르게 있는지 확인해주세요.")
    exit()

# DB 정리 유틸리티 (선택적 로드 - 코드 1 기반)
try:
    from init_db import clean_old_records
except ImportError:
    clean_old_records = None # 파일이 없어도 서버는 실행됨

# --- 2. 기본 설정 및 절대 경로 구성 (코드 1 방식 적용) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)

# 경로 설정 — 절대경로 일관 적용
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 절대경로 변환 헬퍼
def ensure_abs(path: str):
    return path if os.path.isabs(path) else os.path.abspath(os.path.join(BASE_DIR, path))

# 업로드 폴더 준비 (절대경로 보장)
UPLOAD_FOLDER = ensure_abs("temp_images")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
logging.info(f"업로드 폴더(절대경로)가 '{app.config['UPLOAD_FOLDER']}'로 설정되었습니다.")


# --- 3. 백그라운드 작업 (코드 1에서 가져옴) ---

def _cleanup_every_30_days():
    """30일 주기로 오래된 DB 레코드를 정리합니다."""
    if not clean_old_records:
        logging.info("[scheduler] 'clean_old_records' 함수가 없어 DB 정리 작업을 건너뜁니다.")
        return
    
    # 서버 시작 후 바로 실행하지 않고, 30일을 기다린 후 첫 실행
    wait_seconds = int(timedelta(days=30).total_seconds())
    while True:
        time.sleep(wait_seconds)
        try:
            logging.info("[scheduler] 30일이 경과하여 오래된 DB 레코드 정리를 시작합니다.")
            clean_old_records()
        except Exception as e:
            logging.error(f"[scheduler] 주기적 DB 정리 작업 중 오류 발생: {e}")

def _camera_every_12_hours():
    """12시간마다 ESP32 카메라 촬영을 자동으로 트리거합니다."""
    # ==== TODO [CAMERA_TRIGGER] ====
    # 아래 로직은 실제 ESP32의 IP와 통신 방식에 맞게 구현해야 합니다.
    # 예: requests.get(f"http://{ESP32_IP}/capture")
    # ===============================
    wait_seconds = 12 * 60 * 60
    while True:
        time.sleep(wait_seconds) # 12시간 대기 후 실행
        try:
            logging.info("[camera-scheduler] 12시간 주기 카메라 촬영을 트리거합니다. (실제 로직 구현 필요)")
            # << 여기에 실제 카메라 촬영을 요청하는 코드를 추가하세요 >>
        except Exception as e:
            logging.error(f"[camera-scheduler] 자동 카메라 트리거 중 오류 발생: {e}")

# 데몬 스레드 기동
threading.Thread(target=_cleanup_every_30_days, daemon=True).start()
threading.Thread(target=_camera_every_12_hours, daemon=True).start()
logging.info("백그라운드 스케줄러(DB 정리, 자동 촬영) 스레드가 시작되었습니다.")


# --- 4. 웹 페이지 및 API 라우트 (코드 2 기반) ---

@app.route('/')
def index():
    try:
        sensor_data_rows = db_manager.get_all_sensor_data()
        return render_template('index.html', sensor_data=sensor_data_rows)
    except Exception as e:
        logging.error(f"Index 페이지 로딩 오류: {e}")
        return "데이터베이스 조회에 실패했습니다.", 500

@app.route('/api/latest_data', methods=['GET'])
def get_latest_data():
    try:
        latest_data = db_manager.get_latest_sensor_data()
        if latest_data:
            return jsonify(dict(latest_data)), 200
        else:
            return jsonify({'message': 'No data available'}), 404
    except Exception as e:
        logging.error(f"최신 데이터 API 오류: {e}")
        return jsonify({'error': str(e)}), 500


# --- 5. ESP32 통신 라우트 (코드 2 기반, AI 연동 방식 유지) ---

@app.route('/sensor', methods=['POST'])
def receive_sensor_data():
    try:
        data = request.json
        logging.info(f"센서 데이터 수신: {data}")
        db_manager.save_sensor_data(
            soil_moisture=data.get('soil_moisture'),
            air_temperature=data.get('air_temperature'),
            air_humidity=data.get('air_humidity'),
            light_intensity=data.get('light_intensity'),
            water_level=data.get('water_level')
        )
        return jsonify({'status': 'Sensor data saved'}), 200
    except Exception as e:
        logging.error(f"센서 데이터 처리 오류: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/camera/callback', methods=['POST'])
def camera_callback():
    """이미지 수신, AI 분석, DB에 '기록'을 한 번에 처리합니다."""
    image_data = request.data
    if not image_data:
        return jsonify({'error': 'No image data received'}), 400

    # 절대 경로를 사용하도록 수정됨
    temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{int(time.time())}.jpg")
    
    try:
        with open(temp_filepath, 'wb') as f:
            f.write(image_data)
        logging.info(f"이미지 임시 저장: {temp_filepath}")

        # AI 분석 모듈 직접 호출
        ripeness_score, ripeness_text = analyze_ripeness(temp_filepath)
        flower_count, flower_status = analyze_flowers(temp_filepath)
        logging.info(f"AI 분석 결과: 딸기='{ripeness_text}'({ripeness_score}), 꽃={flower_count}개")

        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # (수정된 부분)
        # 개선된 통합 함수를 호출하여 모든 정보를 '새로운 기록'으로 저장합니다.
        db_manager.save_image_analysis_result(
            file_path=temp_filepath,
            ripeness_score=ripeness_score,
            ripeness_text=ripeness_text,
            flower_count=flower_count,
            flower_text=flower_status  # flower_status 정보도 추가
        )
        logging.info("DB에 새로운 이미지 및 AI 분석 결과 기록 완료")
        # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
        
        return jsonify({'status': 'Image analyzed and result saved'}), 200
    except Exception as e:
        logging.error(f"이미지 처리 및 AI 분석 오류: {e}")
        return jsonify({'error': 'Image processing failed'}), 500
    finally:
        # 분석 완료 후 임시 파일 삭제
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
            logging.info(f"임시 이미지 삭제: {temp_filepath}")
            
@app.route('/analysis')
def analysis_page():
    """(새로 추가) AI 분석 결과 확인 페이지"""
    try:
        # 1단계에서 만든 함수를 호출해 데이터를 가져옵니다.
        analysis_data = db_manager.get_all_analysis_data()
        # 'analysis.html'이라는 새 템플릿에 데이터를 전달합니다.
        return render_template('analysis.html', analysis_data=analysis_data)
    except Exception as e:
        logging.error(f"Analysis 페이지 로딩 오류: {e}")
        return "AI 분석 기록 조회에 실패했습니다.", 500
# --- 6. 앱 실행 ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)