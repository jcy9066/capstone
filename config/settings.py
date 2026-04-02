import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SPATIAL_THRESHOLD_IOU = float(os.getenv("SPATIAL_THRESHOLD_IOU", 0.1))
SPATIAL_THRESHOLD_DIST = float(os.getenv("SPATIAL_THRESHOLD_DIST", 150.0))
TEMPORAL_THRESHOLD_FRAMES = int(os.getenv("TEMPORAL_THRESHOLD_FRAMES", 5))
RTSP_URL = os.getenv("RTSP_URL", "0")