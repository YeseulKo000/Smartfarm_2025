# app.py — 라우트 기본 골격(통합 스켈레톤, 절대경로 적용)
# 기능 구현 지점을 눈에 잘 띄게 표시했습니다. (==== TODO ==== 마커)
# 이후 단계에서 두 버전의 코드를 참고해 각 라우트의 실제 로직을 채워넣습니다.

from flask import Flask, render_template, request, jsonify
import requests
import logging
import threading
import time
import os
from datetime import timedelta

# ---------------------------------------------------------------------------
# 경로/설정 — 절대경로 일관 적용
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# config 안전 로드 (없으면 기본값 사용)
try:
    from config import PORT  # 필수
except Exception:
    PORT = 5000

try:
    from config import IMAGE_UPLOAD_FOLDER  # 선택(상대경로여도 절대경로로 변환)
except Exception:
    IMAGE_UPLOAD_FOLDER = "static/uploads"

# (추가) DB_PATH도 가져오되, 없으면 None
try:
    from config import DB_PATH  # 선택
except Exception:
    DB_PATH = None

# 절대경로 변환 헬퍼
def ensure_abs(path: str):
    if not path:
        return BASE_DIR
    return path if os.path.isabs(path) else os.path.abspath(os.path.join(BASE_DIR, path))

# DB 레이어(실제 구현은 기존 db_manager를 참고)
try:
    from database import db_manager
except Exception:
    db_manager = None  # 이후 단계에서 실제 객체 주입 또는 모듈 확인

# (선택) 오래된 레코드 정리 유틸 — 첫 번째 버전 개념 반영
try:
    from init_db import clean_old_records
except Exception:
    clean_old_records = None

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)


# 업로드 폴더 준비(두 번째 버전 개념 반영) — 절대경로 보장
UPLOAD_FOLDER = ensure_abs(IMAGE_UPLOAD_FOLDER or "static/uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ==== DIAG [DB_PATH] =========================================================
# PC에서 먼저 진단 가능하도록, DB 경로 상태를 로그로 남깁니다.
_resolved_db_path = ensure_abs(DB_PATH) if DB_PATH else None
_is_abs = os.path.isabs(DB_PATH) if DB_PATH else None
logging.info(f"[config] DB_PATH={DB_PATH} (abs={_is_abs}); RESOLVED_DB_PATH={_resolved_db_path}")
# db_manager가 경로 설정 메서드를 제공한다면(선택), 안전하게 연결
try:
    if db_manager and _resolved_db_path:
        if hasattr(db_manager, 'set_db_path'):
            db_manager.set_db_path(_resolved_db_path)
        elif hasattr(db_manager, 'configure_path'):
            db_manager.configure_path(_resolved_db_path)
        # 메서드가 없으면 단순 로깅만 합니다.
except Exception as e:
    logging.warning(f"[config] db_manager에 DB 경로 주입 실패: {e}")
# ============================================================================

# ---------------------------------------------------------------------------
# 백그라운드 작업: (1) 30일 주기 DB 정리, (2) 12시간 주기 카메라 트리거
# ---------------------------------------------------------------------------

def _cleanup_every_30_days():
    if not clean_old_records:
        logging.info("[scheduler] clean_old_records 미구현 — 추후 연결 예정")
        return
    try:
        clean_old_records()  # 서버 기동 직후 1회 실행(선택)
    except Exception as e:
        logging.error(f"[scheduler] 초기 clean 오류: {e}")
    wait_seconds = int(timedelta(days=30).total_seconds())
    while True:
        try:
            time.sleep(wait_seconds)
            clean_old_records()
        except Exception as e:
            logging.error(f"[scheduler] 주기 clean 오류: {e}")


def _camera_every_12_hours():
    """ESP32 카메라 트리거(12시간마다). 실제 명령 전송/이미지 수신 로직은 추후 구현.
    ==== TODO [CAMERA_TRIGGER] ===============================================
    - ESP32로 촬영 명령 전송 (HTTP/MQTT 등)
    - 수신 이미지 저장 및 DB 기록 (콜백은 /camera/callback)
    ==========================================================================
    """
    wait_seconds = 12 * 60 * 60
    while True:
        try:
            logging.info("[camera-scheduler] 12시간 주기 카메라 촬영 트리거 예정")
            # TODO: trigger_camera_capture()  # ← 구현 지점
        except Exception as e:
            logging.error(f"[camera-scheduler] 오류: {e}")
        finally:
            time.sleep(wait_seconds)

# 데몬 스레드 기동 (필요 시 주석 처리 가능)
threading.Thread(target=_cleanup_every_30_days, daemon=True).start()
threading.Thread(target=_camera_every_12_hours, daemon=True).start()

# ---------------------------------------------------------------------------
# 1) '/' 기본 라우터 — 최근 데이터 몇 개만 보여주기 (뷰)
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    """최근 데이터 N개 조회하여 템플릿에 렌더링.
    ==== TODO [INDEX_QUERY] ===================================================
    - N 값 config/쿼리파라미터로 조절 (기본 20)
    - db_manager.get_recent_combined_data(limit=N) 구현/연결
    ==========================================================================
    """
    limit = int(request.args.get('limit', 20))
    recent_rows = []
    if db_manager and hasattr(db_manager, 'get_recent_combined_data'):
        try:
            recent_rows = db_manager.get_recent_combined_data(limit=limit)
        except Exception as e:
            logging.error(f"index() 데이터 조회 오류: {e}")
    # 템플릿 없으면 JSON으로 대체
    try:
        return render_template('index.html', sensor_data=recent_rows)
    except Exception:
        return jsonify({"items": recent_rows, "note": "템플릿 미구현 — 임시 JSON"})

# ---------------------------------------------------------------------------
# 2) '/latest_data' 내부 집계 저장용 — 사용자 뷰 불필요 (POST only)
# ---------------------------------------------------------------------------
@app.route('/latest_data', methods=['POST'])
def save_latest_data():
    """각종 최신 데이터(센서, AI 등)를 수집·가공해서 저장.
    - 내부 엔드포인트라 화면 응답은 비움(204)
    ==== TODO [LATEST_SNAPSHOT] ===============================================
    - 간단한 토큰 검증(예: X-API-KEY) 또는 내부망 제한
    - db_manager.upsert_latest_snapshot(payload) 스키마 정의/연결
    ==========================================================================
    """
    # TODO: 토큰 검증 예시 — 필요 시 활성화
    # api_key = request.headers.get('X-API-KEY')
    # if api_key != os.environ.get('INTERNAL_API_KEY'):
    #     return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    logging.info(f"/latest_data 수신 payload: {payload}")
    if db_manager and hasattr(db_manager, 'upsert_latest_snapshot'):
        try:
            db_manager.upsert_latest_snapshot(payload)
            return ('', 204)  # 화면 불필요 → 내용 없음
        except Exception as e:
            logging.error(f"/latest_data 저장 오류: {e}")
            return jsonify({"error": "save_failed"}), 500
    return jsonify({"status": "stub", "note": "db_manager 미연결"}), 200

# ---------------------------------------------------------------------------
# 3) '/sensor' — 아두이노 센서 데이터 및 버튼/제어 입력 저장
# ---------------------------------------------------------------------------
@app.route('/sensor', methods=['POST'])
def receive_sensor():
    """센서 측정값/버튼 이벤트 저장.
    ==== TODO [SENSOR_DB_SAVE] ===============================================
    - db_manager.save_sensor_data(...) 연결(첫 번째/두 번째 버전 참고)
    - 제어 신호는 별도 테이블 저장 필요 시 save_control_event 도입
    ==========================================================================
    """
    data = request.get_json(silent=True) or {}
    logging.info(f"/sensor 수신: {data}")
    if db_manager and hasattr(db_manager, 'save_sensor_data'):
        try:
            db_manager.save_sensor_data(
                soil_moisture=data.get('soil_moisture'),
                air_temperature=data.get('air_temperature'),
                air_humidity=data.get('air_humidity'),
                light_intensity=data.get('light_intensity'),
                water_level=data.get('water_level'),
            )
        except Exception as e:
            logging.error(f"/sensor 저장 오류: {e}")
            return jsonify({"error": "save_failed"}), 500
    return jsonify({"status": "ok"}), 200

# ---------------------------------------------------------------------------
# 4) '/ai' — AI 통신: 사진 업로드/판단 결과 수신
# ---------------------------------------------------------------------------
@app.route('/ai', methods=['POST'])
def ai_hook():
    """AI 모델과의 통신 엔드포인트.
    - A: 바이너리 이미지 수신 → 파일 저장(절대경로) + image_capture 기록
    - B: JSON 결과 수신 → ai_result 저장 (image_id 또는 file_path 기준 연결)
    """
    content_type = request.headers.get('Content-Type', '')
    try:
        # B) JSON 결과 수신
        if 'application/json' in content_type:
            payload = request.get_json(silent=True) or {}
            # 우선순위: image_id → file_path
            image_id = payload.get('image_id')
            file_path = payload.get('file_path')

            if not image_id and file_path and db_manager and hasattr(db_manager, 'find_image_id_by_path'):
                try:
                    image_id = db_manager.find_image_id_by_path(file_path)
                except Exception as e:
                    logging.error(f"/ai file_path→image_id 조회 오류: {e}")
                    image_id = None

            if not image_id:
                return jsonify({"error": "image_id_required"}), 400

            if db_manager and hasattr(db_manager, 'save_ai_result'):
                try:
                    ai_id = db_manager.save_ai_result(
                        image_id=int(image_id),
                        ripeness_score=payload.get('ripeness_score'),
                        flower_score=payload.get('flower_score'),
                        ripeness_text=payload.get('ripeness_text'),
                        flower_text=payload.get('flower_text'),
                    )
                    return jsonify({"status": "ok", "ai_result_id": ai_id}), 200
                except Exception as e:
                    logging.error(f"/ai 결과 저장 오류: {e}")
                    return jsonify({"error": "save_failed"}), 500

            return jsonify({"status": "stub", "note": "db_manager 미연결"}), 200

        # A) 바이너리 이미지 수신
        raw = request.get_data(cache=False)
        if not raw:
            return jsonify({"error": "no_image"}), 400

        filename = f"strawberry_{int(time.time())}.jpg"
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        path = os.path.abspath(path)  # 절대경로 보장

        with open(path, 'wb') as f:
            f.write(raw)
        logging.info(f"/ai 이미지 저장: {path}")

        saved_image_id = None
        if db_manager and hasattr(db_manager, 'save_image_capture'):
            try:
                saved_image_id = db_manager.save_image_capture(file_path=path)
            except Exception as e:
                logging.error(f"/ai 이미지 DB 기록 오류: {e}")

        return jsonify({
            "status": "image_saved",
            "path": path,
            "image_id": saved_image_id
        }), 200

    except Exception as e:
        logging.error(f"/ai 처리 오류: {e}")
        return jsonify({"error": "ai_hook_failed"}), 500

# ---------------------------------------------------------------------------
# 5) '/camera' — ESP32 카메라 제어/사진 수신 및 저장 명령
# ---------------------------------------------------------------------------
@app.route('/camera', methods=['POST'])
def camera_control():
    """ESP32 카메라 조작 명령 수신(수동 트리거)."""
    payload = request.get_json(silent=True) or {}
    command = payload.get("command")
    logging.info(f"/camera 명령: {payload}")

    if command == "capture":
        try:
            # ESP32로 촬영 요청 전송 (예: http://<ESP32_IP>/capture)
            from config import ESP32_IP
            resp = requests.get(f"http://{ESP32_IP}/capture", timeout=5)
            return jsonify({"status": "sent", "esp32_response": resp.text}), 200
        except Exception as e:
            logging.error(f"/camera ESP32 요청 실패: {e}")
            return jsonify({"error": "esp32_failed"}), 500

    return jsonify({"status": "unknown_command"}), 400

# 카메라가 서버로 이미지를 푸시하는 콜백(절대경로 저장)
@app.route('/camera/callback', methods=['POST'])
def camera_callback():
    """ESP32에서 촬영 이미지를 서버로 전송하는 콜백."""
    raw = request.get_data(cache=False)
    if not raw:
        return jsonify({"error": "no_image"}), 400

    filename = f"camera_{int(time.time())}.jpg"
    path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    try:
        with open(path, 'wb') as f:
            f.write(raw)
        logging.info(f"/camera/callback 이미지 저장: {path}")

        saved_image_id = None
        if db_manager and hasattr(db_manager, 'save_image_capture'):
            try:
                saved_image_id = db_manager.save_image_capture(file_path=path)
            except Exception as e:
                logging.error(f"/camera/callback DB 기록 오류: {e}")

        return jsonify({"status": "saved", "path": path, "image_id": saved_image_id}), 200
    except Exception as e:
        logging.error(f"/camera/callback 오류: {e}")
        return jsonify({"error": "save_failed"}), 500

# ---------------------------------------------------------------------------
# 6) '/android' — 안드로이드 앱 연동: 데이터 저장/분석(도전과제 등)
# ---------------------------------------------------------------------------
@app.route('/android', methods=['POST'])
def android_hook():
    """안드로이드 앱에서 오는 요청 수신.
    - 예: 활동 로그/도전과제 진행률 업로드, 앱 단 데이터 동기화 등
    ==== TODO [ANDROID_ACTIONS] ==============================================
    - 액션 타입별 분기(action: "sync", "achievement", ...)
    - db_manager.save_app_event / evaluate_achievements 등 연결
    ==========================================================================
    """
    payload = request.get_json(silent=True) or {}
    action = payload.get('action')
    logging.info(f"/android action={action}, payload={payload}")
    return jsonify({"status": "ok", "action": action}), 200

# ---------------------------------------------------------------------------
# 보조) 상태 점검 엔드포인트 — 개발/운영 헬스체크
# ---------------------------------------------------------------------------
@app.route('/health', methods=['GET'])
def health():
    """헬스체크용 경량 엔드포인트.
    - 기본은 단순 200 OK. `?verbose=1`이면 DB 경로 진단 정보를 함께 제공합니다(민감정보 제외).
    """
    if request.args.get('verbose') == '1':
        return jsonify({
            "status": "up",
            "db_path": DB_PATH,
            "resolved_db_path": _resolved_db_path,
            "db_path_is_abs": _is_abs,
        }), 200
    return jsonify({"status": "up"}), 200

# ---------------------------------------------------------------------------
# 앱 실행
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)