import time

import cv2
import numpy as np

from frontend import state
from frontend.config import CAMERA_TIMEOUT_SEC, ROBOT_STATUS_TIMEOUT_SEC
from frontend.services.status_frame_service import build_status_frame


def upload_frame_bytes(raw_data):
    nparr = np.frombuffer(raw_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is not None:
        # 향후 YOLOv8 적용 위치
        ret, buffer = cv2.imencode(".jpg", frame)
        if ret:
            state.current_frame = buffer.tobytes()
            state.last_frame_at = time.time()


def build_camera_status():
    now = time.time()

    last_frame_age = (
        None
        if state.last_frame_at is None
        else max(0.0, now - state.last_frame_at)
    )

    last_status_at = state.robot_status.get("updated_at")

    last_status_age = (
        None
        if last_status_at is None
        else max(0.0, now - last_status_at)
    )

    has_frame = state.current_frame is not None
    frame_is_live = (
        last_frame_age is not None
        and last_frame_age <= CAMERA_TIMEOUT_SEC
    )
    status_is_live = (
        last_status_age is not None
        and last_status_age <= ROBOT_STATUS_TIMEOUT_SEC
    )

    if frame_is_live:
        state_name = "live"
        message = "영상 수신 중"
        connected = True

    elif not has_frame and now - state.server_started_at < ROBOT_STATUS_TIMEOUT_SEC:
        state_name = "waiting"
        message = "카메라 신호 대기 중"
        connected = False

    elif status_is_live:
        state_name = "camera_disconnected"
        message = "카메라 연결이 끊겼습니다"
        connected = False

    else:
        state_name = "robot_disconnected"
        message = "라즈베리 파이와 연결이 끊겼습니다"
        connected = False

    return {
        "camera_state": state_name,
        "camera_connected": connected,
        "message": message,
        "last_frame_age_sec": last_frame_age,
        "last_status_age_sec": last_status_age,
        "camera_timeout_sec": CAMERA_TIMEOUT_SEC,
        "robot_status_timeout_sec": ROBOT_STATUS_TIMEOUT_SEC,
        "has_current_frame": has_frame,
        "received_fps": 0 if state_name != "live" else None,
    }


def generate_frames():
    while True:
        camera_status = build_camera_status()

        if state.current_frame is not None and camera_status["camera_state"] == "live":
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + state.current_frame
                + b"\r\n"
            )
            time.sleep(0.03)

        else:
            frame = build_status_frame(camera_status["message"])

            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
                time.sleep(0.5)

            else:
                time.sleep(0.1)