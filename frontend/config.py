import os

# capstone/.env에서 필요한 값만 읽습니다.
# 값이 없으면 기존 app.py와 동일한 기본값을 사용합니다.
CAMERA_TIMEOUT_SEC = float(os.getenv("CAMERA_TIMEOUT_SEC", "3.0"))
ROBOT_STATUS_TIMEOUT_SEC = float(os.getenv("ROBOT_STATUS_TIMEOUT_SEC", "5.0"))

STATUS_FRAME_WIDTH = 640
STATUS_FRAME_HEIGHT = 480

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")