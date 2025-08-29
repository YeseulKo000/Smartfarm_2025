# config.py
import os

# 현재 파일의 절대 경로를 가져와 프로젝트의 루트 디렉터리로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# SQLite 데이터베이스 파일 경로 (절대 경로)
DB_PATH = os.path.join(BASE_DIR, 'database.db')

# 이미지 저장 폴더 경로 (절대 경로)
# Flask의 static 폴더 안에 uploads 폴더를 만들어 이미지를 저장합니다.
IMAGE_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')

# 웹 서버 포트
PORT = 8080

# --- ESP32 통신 및 카메라 설정 ---

# ESP32의 IP 주소 (스마트팜 ESP32의 실제 IP 주소로 변경하세요)
# 192.168.4.1은 ESP32가 Access Point 모드로 동작할 때 흔히 사용되는 IP입니다.
ESP32_IP = '192.168.4.1'