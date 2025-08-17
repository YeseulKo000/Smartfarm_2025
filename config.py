# config.py

# SQLite 데이터베이스 파일 경로
DB_PATH = 'database.db'

# 웹 서버 포트
PORT = 8080

# --- ESP32 통신 및 카메라 설정 ---

# ESP32의 IP 주소 (스마트팜 ESP32의 실제 IP 주소로 변경하세요)
ESP32_IP = '192.168.179.109'

# 이미지 저장 폴더 경로 (카메라 기능 사용 시)
IMAGE_UPLOAD_FOLDER = 'images'

# 카메라 설정 (필요시 추가)
CAMERA_SETTINGS = {
    'RESOLUTION_WIDTH': 640,
    'RESOLUTION_HEIGHT': 480,
    'CAPTURE_INTERVAL_MINUTES': 60 # 몇 분마다 사진을 찍을지
}