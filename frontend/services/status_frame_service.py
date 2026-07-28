import cv2
import numpy as np

from frontend import state
from frontend.config import STATUS_FRAME_HEIGHT, STATUS_FRAME_WIDTH


def build_status_frame(message):
    key = (STATUS_FRAME_WIDTH, STATUS_FRAME_HEIGHT, message)

    if (
        state.status_frame_cache["key"] == key
        and state.status_frame_cache["frame"] is not None
    ):
        return state.status_frame_cache["frame"]

    frame = np.full(
        (STATUS_FRAME_HEIGHT, STATUS_FRAME_WIDTH, 3),
        209,
        dtype=np.uint8,
    )

    panel_w = 430
    panel_h = 116

    x1 = (STATUS_FRAME_WIDTH - panel_w) // 2
    y1 = (STATUS_FRAME_HEIGHT - panel_h) // 2
    x2 = x1 + panel_w
    y2 = y1 + panel_h

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        (90, 96, 106),
        thickness=-1,
    )

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        (156, 163, 175),
        thickness=2,
    )

    title = "CAMERA OFFLINE"
    detail = "Check Raspberry Pi / camera connection"

    title_size = cv2.getTextSize(
        title,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        2,
    )[0]

    detail_size = cv2.getTextSize(
        detail,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        1,
    )[0]

    cv2.putText(
        frame,
        title,
        ((STATUS_FRAME_WIDTH - title_size[0]) // 2, y1 + 46),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        detail,
        ((STATUS_FRAME_WIDTH - detail_size[0]) // 2, y1 + 78),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (229, 231, 235),
        1,
        cv2.LINE_AA,
    )

    ret, buffer = cv2.imencode(".jpg", frame)

    if not ret:
        return None

    state.status_frame_cache["key"] = key
    state.status_frame_cache["frame"] = buffer.tobytes()

    return state.status_frame_cache["frame"]