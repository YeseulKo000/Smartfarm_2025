# app.py
from flask import Flask, render_template, request, jsonify
from config import PORT
from database import db_manager
import logging
from init_db import clean_old_records
import threading
from datetime import timedelta

# 로깅 설정: 디버깅 정보를 콘솔에 출력하도록 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# 30일마다 자동 정리(서버 구동 시 스레드 1개 기동)
def _cleanup_every_30_days():
    # 최초 기동 직후 한 번 실행 (선택): 주석 처리 가능
    try:
        clean_old_records()
    except Exception as e:
        print(f"[scheduler] 초기 clean 오류: {e}")

    wait_seconds = int(timedelta(days=30).total_seconds())
    while True:
        try:
            threading.Event().wait(wait_seconds)
            clean_old_records()
        except Exception as e:
            print(f"[scheduler] 주기 clean 오류: {e}")

threading.Thread(target=_cleanup_every_30_days, daemon=True).start()


# --- 웹 서버 라우트 ---

# 1. 루트 페이지: 웹 브라우저에서 접속하면 센서 데이터를 표로 보여줍니다.
@app.route('/')
def index():
    # db_manager에서 모든 센서 데이터를 최신순으로 가져옵니다.
    sensor_data_rows = db_manager.get_all_sensor_data()
    
    # templates/index.html 파일을 렌더링하고, 데이터를 전달합니다.
    return render_template('index.html', sensor_data=sensor_data_rows)


# 2. 센서 데이터 조회 API: 안드로이드 앱에서 최신 데이터를 요청할 때 사용됩니다.
@app.route('/api/latest_sensor_data', methods=['GET'])
def get_latest_sensor_data():
    try:
        # db_manager에서 가장 최근 센서 데이터 1개를 가져옵니다.
        latest_data = db_manager.get_latest_sensor_data()
        if latest_data:
            # SQLite의 Row 객체를 딕셔너리로 변환하여 JSON으로 보냅니다.
            data_dict = dict(latest_data)
            return jsonify(data_dict), 200
        else:
            return jsonify({'message': 'No sensor data available'}), 404
    except Exception as e:
        logging.error(f"Error fetching latest sensor data: {e}")
        return jsonify({'error': str(e)}), 500


# --- ESP32 통신 라우트 ---

# 3. 센서 데이터 수신 API: ESP32가 이 주소로 HTTP POST 요청을 보냅니다.
@app.route('/sensor', methods=['POST'])
def receive_sensor_data():
    try:
        data = request.json
        if not data:
            logging.warning("No JSON data received.")
            return jsonify({'error': 'No JSON data received'}), 400

        logging.info(f"Received sensor data: {data}")

        # db_manager를 통해 데이터를 데이터베이스에 저장합니다.
        success = db_manager.save_sensor_data(
            soil_moisture=data.get('soil_moisture'),
            air_temperature=data.get('air_temperature'),
            air_humidity=data.get('air_humidity'),
            light_intensity=data.get('light_intensity'),
            water_level=data.get('water_level'),
            strawberry_ripeness_score=None,
            strawberry_ripeness_text=None
        )

        if success:
            return jsonify({'status': 'Data saved successfully'}), 200
        else:
            return jsonify({'error': 'Failed to save data to database'}), 500

    except Exception as e:
        logging.error(f"Error while receiving sensor data: {e}")
        return jsonify({'error': str(e)}), 500


# --- 제어 명령 라우트 ---

# 4. 제어 명령 수신 API: 앱에서 라즈베리파이로 제어 명령을 보낼 때 사용됩니다.
@app.route('/control', methods=['POST'])
def control_device():
    data = request.json
    if not data:
        return jsonify({'error': 'No data received'}), 400

    device = data.get('device')
    command = data.get('command')

    if not device or not command:
        return jsonify({'error': 'Missing device or command'}), 400

    # 이 라우트에서 ESP32로 제어 명령을 전달하는 로직을 추가해야 합니다.
    # 예: MQTT를 통해 ESP32로 'fan_on' 명령을 보냅니다.
    print(f"제어 명령 수신: {device} -> {command}")
    return jsonify({'status': 'Control command received and processed'}), 200


if __name__ == '__main__':
    # 웹 서버를 시작합니다.
    # host='0.0.0.0'는 외부에서 접속할 수 있도록 모든 IP 주소를 허용합니다.
    # port는 config.py에서 설정한 포트를 사용합니다.
    app.run(host='0.0.0.0', port=PORT, debug=True)