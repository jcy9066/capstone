import argparse
import asyncio
import json
import os
import threading
import time

import cv2
import requests
from dotenv import load_dotenv

from controllers.motor_controller import MotorController
from controllers.speaker_controller import SpeakerController

try:
    import websockets
except ImportError:
    websockets = None


load_dotenv()


def collect_status(robot_id):
    return {
        "robot_id": robot_id,
        "cpu_usage": "0.0",
        "cpu_temp": "0.0",
        "ram_usage": "0.0",
        "battery": "100",
        "internet": "ok",
    }


class PiClient:
    def __init__(self, args):
        self.robot_id = args.robot_id
        self.server_base_url = args.server_base_url.rstrip("/")
        self.frame_url = f"{self.server_base_url}/frame?robot_id={self.robot_id}"
        self.status_url = f"{self.server_base_url}/status"
        self.ws_url = args.ws_url or self.server_base_url.replace("http://", "ws://").replace("https://", "wss://") + f"/ws/robot/{self.robot_id}"
        self.frame_fps = args.frame_fps
        self.frame_width = args.frame_width
        self.frame_height = args.frame_height
        self.jpeg_quality = args.jpeg_quality
        self.status_interval_sec = args.status_interval_sec
        self.ws_reconnect_delay_sec = args.ws_reconnect_delay_sec
        self.running = True
        self.motor = MotorController(command_timeout_sec=args.command_timeout_sec)
        self.speaker = SpeakerController()

    def start(self):
        threads = [
            threading.Thread(target=self.frame_loop, daemon=True),
            threading.Thread(target=self.status_loop, daemon=True),
            threading.Thread(target=self.failsafe_loop, daemon=True),
        ]
        for thread in threads:
            thread.start()

        if websockets is None:
            print("[ws] websockets 패키지가 없어 명령 채널을 시작하지 않습니다.")
            while self.running:
                time.sleep(1)
        else:
            asyncio.run(self.command_loop())

    def frame_loop(self):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        cap.set(cv2.CAP_PROP_FPS, self.frame_fps)
        if not cap.isOpened():
            print("[camera] 카메라를 열 수 없습니다.")
            return

        delay = 1.0 / max(self.frame_fps, 1)
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]

        while self.running:
            started = time.time()
            ret, frame = cap.read()
            if not ret:
                print("[camera] 프레임 캡처 실패")
                time.sleep(delay)
                continue

            ok, buffer = cv2.imencode(".jpg", frame, encode_param)
            if not ok:
                print("[camera] JPEG 인코딩 실패")
                time.sleep(delay)
                continue

            try:
                files = {"file": ("frame.jpg", buffer.tobytes(), "image/jpeg")}
                requests.post(self.frame_url, files=files, timeout=1.0)
            except requests.RequestException as exc:
                print(f"[frame] 전송 실패: {exc}")

            elapsed = time.time() - started
            time.sleep(max(0.0, delay - elapsed))

        cap.release()

    def status_loop(self):
        while self.running:
            try:
                requests.post(self.status_url, json=collect_status(self.robot_id), timeout=1.0)
            except requests.RequestException as exc:
                print(f"[status] 전송 실패: {exc}")
            time.sleep(self.status_interval_sec)

    def failsafe_loop(self):
        while self.running:
            self.motor.failsafe_tick()
            time.sleep(0.05)

    async def command_loop(self):
        while self.running:
            try:
                async with websockets.connect(self.ws_url, ping_interval=10, ping_timeout=5) as websocket:
                    print(f"[ws] connected: {self.ws_url}")
                    async for raw_message in websocket:
                        message = json.loads(raw_message)
                        await self.handle_command(websocket, message)
            except Exception as exc:
                print(f"[ws] disconnected: {exc}")
                self.motor.stop(reason="websocket disconnected")
                await asyncio.sleep(self.ws_reconnect_delay_sec)

    async def handle_command(self, websocket, message):
        command_type = message.get("type")
        ok = True
        error = None

        try:
            if command_type == "move":
                print(f"[dry-run] ignored move command: {message}")
            elif command_type in ("stop", "emergency_stop"):
                print(f"[dry-run] ignored {command_type} command")
            elif command_type == "speak":
                self.speaker.speak(message.get("text", ""))
            elif command_type == "mode":
                print(f"[mode] {message.get('mode')}")
            elif command_type == "camera_config":
                print(f"[camera_config] {message}")
            else:
                ok = False
                error = f"unknown command type: {command_type}"
        except Exception as exc:
            ok = False
            error = str(exc)

        await websocket.send(json.dumps({
            "type": "ack",
            "command_id": message.get("command_id"),
            "ok": ok,
            "error": error,
        }))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-base-url", default=os.getenv("SERVER_BASE_URL", "http://10.108.90.21:21063"))
    parser.add_argument("--robot-id", default=os.getenv("ROBOT_ID", "pi-01"))
    parser.add_argument("--ws-url", default=os.getenv("COMMAND_WS_URL"))
    parser.add_argument("--frame-fps", type=float, default=float(os.getenv("FRAME_FPS", "10")))
    parser.add_argument("--frame-width", type=int, default=int(os.getenv("FRAME_WIDTH", os.getenv("STREAM_WIDTH", "640"))))
    parser.add_argument("--frame-height", type=int, default=int(os.getenv("FRAME_HEIGHT", os.getenv("STREAM_HEIGHT", "480"))))
    parser.add_argument("--jpeg-quality", type=int, default=int(os.getenv("JPEG_QUALITY", "70")))
    parser.add_argument("--status-interval-sec", type=float, default=float(os.getenv("STATUS_INTERVAL_SEC", "1.0")))
    parser.add_argument("--command-timeout-sec", type=float, default=float(os.getenv("COMMAND_TIMEOUT_SEC", "0.5")))
    parser.add_argument("--ws-reconnect-delay-sec", type=float, default=float(os.getenv("WS_RECONNECT_DELAY_SEC", "1.0")))
    return parser.parse_args()


if __name__ == "__main__":
    PiClient(parse_args()).start()
