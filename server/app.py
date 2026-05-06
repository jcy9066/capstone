import asyncio
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import ClientDisconnect

ROOT_DIR = Path(__file__).resolve().parents[1]
PERCEPTION_DIR = ROOT_DIR / "perception"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(PERCEPTION_DIR) not in sys.path:
    sys.path.insert(0, str(PERCEPTION_DIR))

from perception.frame_processor import FrameProcessor
from perception.pipeline_factory import PIPELINE_OPTIONS, create_pipeline

load_dotenv(ROOT_DIR / ".env")
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(title="AI Patrol Robot Integrated Server")
app.mount("/static", StaticFiles(directory=ROOT_DIR / "frontend" / "static"), name="static")
templates = Jinja2Templates(directory=ROOT_DIR / "frontend" / "templates")

SERVER_ROBOT_ID = os.getenv("ROBOT_ID", "pi-01")
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "21063"))
PIPELINE = os.getenv("PIPELINE", "1")
MODEL_REQUIRED = os.getenv("MODEL_REQUIRED", "false").lower() == "true"
SAVE_RECEIVED_FRAMES = os.getenv("SAVE_RECEIVED_FRAMES", "true").lower() == "true"
STREAM_WIDTH = int(os.getenv("STREAM_WIDTH", "640"))
STREAM_HEIGHT = int(os.getenv("STREAM_HEIGHT", "480"))
STREAM_FPS = int(os.getenv("STREAM_FPS", "15"))
INFERENCE_ENABLED = os.getenv("INFERENCE_ENABLED", "true").lower() == "true"
STREAM_INFER_EVERY_N = max(1, int(os.getenv("STREAM_INFER_EVERY_N", "1")))
CAMERA_TIMEOUT_SEC = float(os.getenv("CAMERA_TIMEOUT_SEC", "3.0"))
ROBOT_STATUS_TIMEOUT_SEC = float(os.getenv("ROBOT_STATUS_TIMEOUT_SEC", "5.0"))
SAVE_DIR = ROOT_DIR / "received_frames"
SAVE_DIR.mkdir(exist_ok=True)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

state_lock = threading.Lock()
server_started_at = time.time()
current_frame = None
latest_result = {
    "ok": True,
    "robot_id": SERVER_ROBOT_ID,
    "detections": [],
    "danger": False,
    "pipeline": None,
    "model_error": None,
}
robot_status = {
    "robot_id": SERVER_ROBOT_ID,
    "cpu_usage": "0.0",
    "cpu_temp": "0.0",
    "battery": "100",
    "ram_usage": "0.0",
    "internet": "unknown",
    "mode": "auto",
    "updated_at": None,
}
frame_stats = {"last_time": time.time(), "count": 0, "fps": 0}
stream_stats = {
    "connected": False,
    "robot_id": None,
    "connected_at": None,
    "disconnected_at": None,
    "bytes_received": 0,
    "frames_received": 0,
    "last_byte_at": None,
    "frames_decoded": 0,
    "frames_inferred": 0,
    "last_frame_at": None,
    "last_error": None,
    "ffmpeg_returncode": None,
    "ffmpeg_stderr_tail": [],
}
status_frame_cache = {"key": None, "frame": None}
frame_processor = None
model_error = None
processing_lock = threading.Lock()


class RobotConnectionManager:
    def __init__(self):
        self.active = {}
        self.lock = asyncio.Lock()

    async def connect(self, robot_id, websocket):
        await websocket.accept()
        async with self.lock:
            old = self.active.get(robot_id)
            if old is not None:
                try:
                    await old.close()
                except Exception:
                    pass
            self.active[robot_id] = websocket

    async def disconnect(self, robot_id, websocket):
        async with self.lock:
            if self.active.get(robot_id) is websocket:
                self.active.pop(robot_id, None)

    async def send_command(self, robot_id, command):
        async with self.lock:
            websocket = self.active.get(robot_id)
        if websocket is None:
            return False
        await websocket.send_json(command)
        return True

    async def is_connected(self, robot_id):
        async with self.lock:
            return robot_id in self.active


connections = RobotConnectionManager()


@app.on_event("startup")
async def startup():
    global frame_processor, model_error
    try:
        pipeline = create_pipeline(PIPELINE)
        frame_processor = FrameProcessor(
            detector=pipeline["detector"],
            action_analyzer=pipeline["action_analyzer"],
        )
        latest_result["pipeline"] = pipeline["name"]
        print(f"[model] pipeline loaded: {pipeline['name']}")
    except Exception as exc:
        model_error = str(exc)
        latest_result["model_error"] = model_error
        print(f"[model] pipeline load failed: {model_error}")
        if MODEL_REQUIRED:
            raise


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/send_telegram")
async def send_telegram():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return JSONResponse({"status": "error", "error": "telegram env missing"}, status_code=500)

    message = "[긴급] 순찰 로봇 위험 감지! 관제 센터에서 신고가 접수되었습니다."
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=5)
        if response.status_code == 200:
            return {"status": "success"}
        return JSONResponse({"status": "error"}, status_code=500)
    except Exception as exc:
        print(f"텔레그램 전송 오류: {exc}")
        return JSONResponse({"status": "error"}, status_code=500)


@app.post("/status")
@app.post("/update_status")
async def update_status(request: Request):
    global robot_status
    data = await request.json()
    if not data:
        return JSONResponse({"ok": False, "error": "empty status"}, status_code=400)

    with state_lock:
        robot_status.update(
            {
                "robot_id": data.get("robot_id", robot_status["robot_id"]),
                "cpu_usage": str(data.get("cpu_usage", robot_status["cpu_usage"])),
                "cpu_temp": str(data.get("cpu_temp", robot_status["cpu_temp"])),
                "battery": str(data.get("battery", robot_status["battery"])),
                "ram_usage": str(data.get("ram_usage", robot_status["ram_usage"])),
                "internet": str(data.get("internet", robot_status["internet"])),
                "mode": str(data.get("mode", robot_status.get("mode", "auto"))),
                "updated_at": time.time(),
            }
        )
    return {"ok": True}


@app.get("/get_status")
async def get_status():
    with state_lock:
        return dict(robot_status)


@app.get("/api/robots/{robot_id}")
async def get_robot(robot_id: str):
    with state_lock:
        status = dict(robot_status)
        result = dict(latest_result)
    return {
        "robot_id": robot_id,
        "connected": await connections.is_connected(robot_id),
        "status": status,
        "latest_result": result,
    }


def process_and_publish_frame(frame, robot_id=SERVER_ROBOT_ID, original_bytes=None, infer=True):
    global current_frame, latest_result

    result_frame = frame
    result = {
        "ok": True,
        "robot_id": robot_id,
        "detections": [],
        "danger": False,
        "pipeline": latest_result.get("pipeline"),
        "model_error": model_error,
    }

    if infer and frame_processor is not None:
        with processing_lock:
            processed = frame_processor.process(frame)
        result_frame = processed["frame"]
        result["detections"] = processed["detections"]
        result["danger"] = processed["danger"]

    ok, buffer = cv2.imencode(".jpg", result_frame)
    if not ok:
        raise RuntimeError("encode failed")

    frame_bytes = buffer.tobytes()
    with state_lock:
        now = time.time()
        current_frame = frame_bytes
        latest_result = result
        stream_stats["connected"] = True
        stream_stats["robot_id"] = robot_id
        stream_stats["frames_received"] = stream_stats.get("frames_received", 0) + 1
        stream_stats["last_frame_at"] = now
        stream_stats["last_error"] = None
        frame_stats["count"] += 1
        if now - frame_stats["last_time"] >= 1.0:
            frame_stats["fps"] = frame_stats["count"]
            print(f"received fps: {frame_stats['fps']}, frame shape: {frame.shape}")
            frame_stats["count"] = 0
            frame_stats["last_time"] = now

    if SAVE_RECEIVED_FRAMES:
        if original_bytes is not None:
            (SAVE_DIR / "latest.jpg").write_bytes(original_bytes)

    return result


def build_camera_status(now=None):
    now = now or time.time()
    last_frame_at = stream_stats.get("last_frame_at")
    last_status_at = robot_status.get("updated_at")
    last_frame_age = None if last_frame_at is None else max(0.0, now - last_frame_at)
    last_status_age = None if last_status_at is None else max(0.0, now - last_status_at)
    has_frame = current_frame is not None
    frame_is_live = last_frame_age is not None and last_frame_age <= CAMERA_TIMEOUT_SEC
    status_is_live = last_status_age is not None and last_status_age <= ROBOT_STATUS_TIMEOUT_SEC
    startup_age = now - server_started_at
    last_error = stream_stats.get("last_error")
    disconnected_at = stream_stats.get("disconnected_at")
    stream_is_closed = (
        disconnected_at is not None
        and last_frame_at is not None
        and disconnected_at >= last_frame_at
        and not stream_stats.get("connected")
    )

    if not has_frame and startup_age < ROBOT_STATUS_TIMEOUT_SEC:
        state = "waiting"
        message = "카메라 신호 대기 중"
        connected = False
    elif stream_is_closed or not stream_stats.get("connected"):
        if status_is_live:
            state = "camera_disconnected"
            message = "카메라 연결이 끊겼습니다"
        else:
            state = "robot_disconnected"
            message = "라즈베리 파이와 연결이 끊겼습니다"
        connected = False
    elif frame_is_live:
        state = "live"
        message = "영상 수신 중"
        connected = True
    elif status_is_live:
        state = "camera_disconnected"
        message = "카메라 연결이 끊겼습니다"
        connected = False
    elif last_error:
        state = "error"
        message = "카메라 스트림 오류"
        connected = False
    elif not has_frame:
        state = "robot_disconnected"
        message = "라즈베리 파이와 연결이 끊겼습니다"
        connected = False
    else:
        state = "robot_disconnected"
        message = "라즈베리 파이와 연결이 끊겼습니다"
        connected = False

    return {
        "camera_state": state,
        "camera_connected": connected,
        "message": message,
        "last_frame_age_sec": last_frame_age,
        "last_status_age_sec": last_status_age,
        "camera_timeout_sec": CAMERA_TIMEOUT_SEC,
        "robot_status_timeout_sec": ROBOT_STATUS_TIMEOUT_SEC,
    }


def build_status_frame(message):
    key = (STREAM_WIDTH, STREAM_HEIGHT, message)
    if status_frame_cache["key"] == key and status_frame_cache["frame"] is not None:
        return status_frame_cache["frame"]

    frame = np.full((STREAM_HEIGHT, STREAM_WIDTH, 3), 209, dtype=np.uint8)
    panel_w = min(STREAM_WIDTH - 48, 430)
    panel_h = 116
    x1 = max(16, (STREAM_WIDTH - panel_w) // 2)
    y1 = max(16, (STREAM_HEIGHT - panel_h) // 2)
    x2 = x1 + panel_w
    y2 = y1 + panel_h
    cv2.rectangle(frame, (x1, y1), (x2, y2), (90, 96, 106), thickness=-1)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (156, 163, 175), thickness=2)

    title = "CAMERA OFFLINE"
    detail = "Check Raspberry Pi / camera connection"
    title_size = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
    detail_size = cv2.getTextSize(detail, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)[0]
    cv2.putText(
        frame,
        title,
        ((STREAM_WIDTH - title_size[0]) // 2, y1 + 46),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        detail,
        ((STREAM_WIDTH - detail_size[0]) // 2, y1 + 78),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (229, 231, 235),
        1,
        cv2.LINE_AA,
    )

    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    status_frame_cache["key"] = key
    status_frame_cache["frame"] = buffer.tobytes()
    return status_frame_cache["frame"]


@app.post("/frame")
async def receive_frame(request: Request, file: UploadFile | None = File(None)):
    if file is not None:
        data = await file.read()
    else:
        data = await request.body()

    np_arr = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if frame is None:
        return JSONResponse({"ok": False, "error": "decode failed"}, status_code=400)

    try:
        return process_and_publish_frame(
            frame,
            robot_id=request.query_params.get("robot_id", SERVER_ROBOT_ID),
            original_bytes=data,
        )
    except RuntimeError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


def read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def h264_decode_loop(proc, robot_id, infer):
    frame_size = STREAM_WIDTH * STREAM_HEIGHT * 3
    frame_index = 0
    try:
        while True:
            raw_frame = read_exact(proc.stdout, frame_size)
            if raw_frame is None:
                break
            frame = np.frombuffer(raw_frame, np.uint8).reshape((STREAM_HEIGHT, STREAM_WIDTH, 3))
            frame_index += 1
            should_infer = infer and (frame_index % STREAM_INFER_EVERY_N == 0)
            process_and_publish_frame(frame, robot_id=robot_id, infer=should_infer)
            with state_lock:
                stream_stats["frames_decoded"] += 1
                if should_infer:
                    stream_stats["frames_inferred"] += 1
                stream_stats["last_frame_at"] = time.time()
                stream_stats["ffmpeg_returncode"] = proc.poll()
    except Exception as exc:
        message = str(exc)
        with state_lock:
            stream_stats["last_error"] = message
        print(f"[stream/h264] decode loop error: {message}")


def ffmpeg_stderr_loop(proc):
    if proc.stderr is None:
        return
    try:
        for raw_line in iter(proc.stderr.readline, b""):
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            with state_lock:
                stream_stats["ffmpeg_stderr_tail"].append(line)
                stream_stats["ffmpeg_stderr_tail"] = stream_stats["ffmpeg_stderr_tail"][-20:]
                stream_stats["last_error"] = line
            print(f"[ffmpeg] {line}")
    except Exception as exc:
        print(f"[ffmpeg] stderr reader error: {exc}")


@app.api_route("/stream/h264", methods=["POST", "PUT"])
async def receive_h264_stream(request: Request):
    robot_id = request.query_params.get("robot_id", SERVER_ROBOT_ID)
    infer_param = request.query_params.get("infer")
    infer = INFERENCE_ENABLED if infer_param is None else infer_param.lower() in ("1", "true", "yes", "on")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-analyzeduration",
        "100000",
        "-probesize",
        "100000",
        "-f",
        "h264",
        "-i",
        "pipe:0",
        "-vf",
        f"scale={STREAM_WIDTH}:{STREAM_HEIGHT},fps={STREAM_FPS}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]

    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "ffmpeg not found"}, status_code=500)

    reader = threading.Thread(target=h264_decode_loop, args=(proc, robot_id, infer), daemon=True)
    stderr_reader = threading.Thread(target=ffmpeg_stderr_loop, args=(proc,), daemon=True)
    reader.start()
    stderr_reader.start()
    with state_lock:
        stream_stats.update(
            {
                "connected": True,
                "robot_id": robot_id,
                "connected_at": time.time(),
                "disconnected_at": None,
                "bytes_received": 0,
                "frames_received": 0,
                "last_byte_at": None,
                "frames_decoded": 0,
                "frames_inferred": 0,
                "last_frame_at": None,
                "last_error": None,
                "ffmpeg_returncode": None,
                "ffmpeg_stderr_tail": [],
                "infer": infer,
            }
        )
    print(f"[stream/h264] connected robot_id={robot_id} infer={infer}")

    try:
        async for chunk in request.stream():
            if not chunk:
                continue
            with state_lock:
                stream_stats["bytes_received"] += len(chunk)
                stream_stats["last_byte_at"] = time.time()
                stream_stats["ffmpeg_returncode"] = proc.poll()
            if proc.stdin is None:
                break
            if proc.poll() is not None:
                with state_lock:
                    stream_stats["ffmpeg_returncode"] = proc.returncode
                break
            try:
                await asyncio.to_thread(proc.stdin.write, chunk)
                await asyncio.to_thread(proc.stdin.flush)
            except BrokenPipeError:
                with state_lock:
                    stream_stats["last_error"] = "ffmpeg stdin broken pipe"
                    stream_stats["ffmpeg_returncode"] = proc.poll()
                break
    except ClientDisconnect:
        with state_lock:
            stream_stats["connected"] = False
            stream_stats["disconnected_at"] = time.time()
            stream_stats["ffmpeg_returncode"] = proc.poll()
    finally:
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except Exception:
                pass
        try:
            proc.terminate()
        except Exception:
            pass
        reader.join(timeout=2.0)
        stderr_reader.join(timeout=1.0)
        with state_lock:
            stream_stats["connected"] = False
            stream_stats["disconnected_at"] = time.time()
            stream_stats["ffmpeg_returncode"] = proc.poll()

    print(f"[stream/h264] disconnected robot_id={robot_id}")
    return {"ok": True, "robot_id": robot_id}


def generate_frames():
    while True:
        with state_lock:
            camera_status = build_camera_status()
            is_live = camera_status["camera_state"] == "live"
            frame = current_frame if is_live else build_status_frame(camera_status["message"])
        if frame is not None:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(0.03 if is_live else 0.5)
        else:
            time.sleep(0.1)


@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/latest_result")
async def get_latest_result():
    with state_lock:
        return dict(latest_result)


@app.get("/api/stream_status")
async def get_stream_status():
    with state_lock:
        status = dict(stream_stats)
        status.update(build_camera_status())
        status["has_current_frame"] = current_frame is not None
        status["received_fps"] = frame_stats["fps"] if status["camera_state"] == "live" else 0
        status["stream_width"] = STREAM_WIDTH
        status["stream_height"] = STREAM_HEIGHT
        status["stream_fps"] = STREAM_FPS
        status["inference_enabled"] = INFERENCE_ENABLED
        status["stream_infer_every_n"] = STREAM_INFER_EVERY_N
        return status


@app.websocket("/ws/robot/{robot_id}")
async def robot_websocket(websocket: WebSocket, robot_id: str):
    await connections.connect(robot_id, websocket)
    print(f"[ws] robot connected: {robot_id}")
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "status":
                with state_lock:
                    robot_status.update(message.get("data", {}))
                    robot_status["robot_id"] = robot_id
                    robot_status["updated_at"] = time.time()
            elif message.get("type") == "ack":
                print(f"[ws] ack from {robot_id}: {message}")
    except WebSocketDisconnect:
        print(f"[ws] robot disconnected: {robot_id}")
    finally:
        await connections.disconnect(robot_id, websocket)


@app.post("/api/robots/{robot_id}/command")
async def send_robot_command(robot_id: str, request: Request):
    payload = await request.json()
    command = {
        "command_id": payload.get("command_id", str(uuid4())),
        "type": payload.get("type", "move"),
        "issued_at": time.time(),
        **payload,
    }

    delivered = await connections.send_command(robot_id, command)
    status_code = 200 if delivered else 409
    return JSONResponse(
        {
            "ok": delivered,
            "delivered": delivered,
            "robot_id": robot_id,
            "command": command,
            "error": None if delivered else "robot not connected",
        },
        status_code=status_code,
    )


@app.get("/api/pipelines")
async def get_pipelines():
    return {"pipelines": PIPELINE_OPTIONS, "selected": PIPELINE}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.app:app", host=SERVER_HOST, port=SERVER_PORT, reload=False, access_log=False)
