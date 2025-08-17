# Smartfarm 2025

ESP32 + Raspberry Pi 기반 스마트팜 시스템  
Flask 서버 + SQLite DB + YOLOv8 인공지능 연동

# 주요 기능
- 센서 데이터 수집
- 이미지 업로드 및 분석
- 장치 제어 (펌프, 팬, LED 등)
- 웹 대시보드 및 안드로이드 앱 연동

# 명령어
// 필요한 패키지 다운 (터미널에서 아래의 명령어 실행)  
pip install -r requirements.txt

// 필요한 패키지 업데이트 (마찬가지로 터미널에서)  
pip freeze > requirements.txt

// 더미데이터 입력 및 삭제 (터미널에서)  
DB 초기화: python model_sensor.py init  
더미데이터 insert: python model_sensor.py insert  
더미데이터 삭제: python model_sensor.py delete