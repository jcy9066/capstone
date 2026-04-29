import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SPATIAL_THRESHOLD_IOU = float(os.getenv("SPATIAL_THRESHOLD_IOU", 0.1))
SPATIAL_THRESHOLD_DIST = float(os.getenv("SPATIAL_THRESHOLD_DIST", 150.0))
TEMPORAL_THRESHOLD_FRAMES = int(os.getenv("TEMPORAL_THRESHOLD_FRAMES", 5))
RTSP_URL = os.getenv("RTSP_URL", "0")
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 21063))
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://10.108.90.21:21063")
ROBOT_ID = os.getenv("ROBOT_ID", "pi-01")
PIPELINE = os.getenv("PIPELINE", "1")
FRAME_FPS = float(os.getenv("FRAME_FPS", 10))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", 70))
COMMAND_TIMEOUT_SEC = float(os.getenv("COMMAND_TIMEOUT_SEC", 0.5))
WS_RECONNECT_DELAY_SEC = float(os.getenv("WS_RECONNECT_DELAY_SEC", 1.0))
