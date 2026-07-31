from __future__ import annotations

import argparse
import asyncio
import json
import os
import threading
import time
from pathlib import Path

import requests
import websockets
from dotenv import load_dotenv

from controllers.motor_controller import MotorController
from controllers.speaker_controller import SpeakerController


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


class RobotCommandClient:
    def __init__(self, args: argparse.Namespace) -> None:
        self.robot_id = args.robot_id
        self.server_base_url = args.server_base_url.rstrip("/")

        self.status_url = (
            f"{self.server_base_url}/status"
        )

        self.ws_url = (
            args.ws_url
            or self.server_base_url
            .replace("http://", "ws://")
            .replace("https://", "wss://")
            + f"/ws/robot/{self.robot_id}"
        )

        self.status_interval_sec = (
            args.status_interval_sec
        )
        self.ws_reconnect_delay_sec = (
            args.ws_reconnect_delay_sec
        )
        self.encoder_interval_sec = (
            args.encoder_interval_sec
        )

        self.running = True
        self.current_mode = "auto"

        self.motor = MotorController(
            serial_port=args.serial_port,
            baudrate=args.serial_baudrate,
            command_timeout_sec=args.command_timeout_sec,
            serial_timeout_sec=args.serial_timeout_sec,
        )

        self.speaker = SpeakerController()

    def start(self) -> None:
        threads = [
            threading.Thread(
                target=self.status_loop,
                daemon=True,
            ),
            threading.Thread(
                target=self.failsafe_loop,
                daemon=True,
            ),
        ]

        for thread in threads:
            thread.start()

        try:
            asyncio.run(self.command_loop())

        except KeyboardInterrupt:
            print("\n[robot-client] 종료 요청")

        finally:
            self.running = False
            self.motor.close()

    def status_payload(self) -> dict:
        return {
            "robot_id": self.robot_id,
            "cpu_usage": "0.0",
            "cpu_temp": "0.0",
            "ram_usage": "0.0",
            "battery": "100",
            "internet": "ok",
            "mode": self.current_mode,
            "motor_connected": self.motor.connected,
            "motor_motion": self.motor.current_motion,
        }

    def status_loop(self) -> None:
        while self.running:
            try:
                requests.post(
                    self.status_url,
                    json=self.status_payload(),
                    timeout=1.0,
                )

            except requests.RequestException as exc:
                print(f"[status] 전송 실패: {exc}")

            time.sleep(self.status_interval_sec)

    def failsafe_loop(self) -> None:
        while self.running:
            self.motor.failsafe_tick()
            time.sleep(0.05)

    async def command_loop(self) -> None:
        while self.running:
            try:
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=10,
                    ping_timeout=5,
                    close_timeout=1,
                    max_queue=16,
                ) as websocket:

                    print(
                        f"[ws] connected: {self.ws_url}"
                    )

                    encoder_task = asyncio.create_task(
                        self.encoder_telemetry_loop(
                            websocket
                        )
                    )

                    try:
                        async for raw_message in websocket:
                            message = json.loads(raw_message)

                            await self.handle_command(
                                websocket,
                                message,
                            )

                    finally:
                        encoder_task.cancel()

                        try:
                            await encoder_task
                        except asyncio.CancelledError:
                            pass

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                print(f"[ws] disconnected: {exc}")

                self.motor.stop(
                    reason="websocket_disconnected",
                    suppress_errors=True,
                )

                await asyncio.sleep(
                    self.ws_reconnect_delay_sec
                )

    async def encoder_telemetry_loop(
        self,
        websocket,
    ) -> None:
        while self.running:
            try:
                await asyncio.to_thread(
                    self.motor.start_encoder_stream
                )
                break

            except Exception as exc:
                print(
                    f"[encoder] UART 연결 실패: {exc}"
                )

                await asyncio.sleep(1.0)

        previous_sequence = -1

        while self.running:
            snapshot = self.motor.encoder_snapshot()

            if (
                snapshot is not None
                and snapshot["sequence"]
                != previous_sequence
            ):
                previous_sequence = snapshot["sequence"]

                message = {
                    "type": "encoder",
                    "robot_id": self.robot_id,
                    "data": {
                        "sequence": snapshot[
                            "sequence"
                        ],
                        "left_front_ticks": snapshot[
                            "left_front_ticks"
                        ],
                        "right_front_ticks": snapshot[
                            "right_front_ticks"
                        ],
                        "left_rear_ticks": snapshot[
                            "left_rear_ticks"
                        ],
                        "right_rear_ticks": snapshot[
                            "right_rear_ticks"
                        ],
                        "pico_timestamp_ms": snapshot[
                            "pico_timestamp_ms"
                        ],
                        "pi_timestamp": snapshot[
                            "updated_at"
                        ],
                    },
                }

                await websocket.send(
                    json.dumps(
                        message,
                        separators=(",", ":"),
                    )
                )

            await asyncio.sleep(
                self.encoder_interval_sec
            )


    async def handle_command(
        self,
        websocket,
        message: dict,
    ) -> None:
        command_type = str(
            message.get("type", "")
        ).strip().lower()

        ok = True
        error = None

        try:
            if command_type == "move":
                if self.current_mode != "manual":
                    raise RuntimeError(
                        "수동 모드가 아니므로 "
                        "이동 명령을 거부했습니다."
                    )

                await asyncio.to_thread(
                    self.motor.move,
                    message.get("direction", ""),
                    message.get("speed", 0.35),
                )

            elif command_type == "stop":
                await asyncio.to_thread(
                    self.motor.stop,
                    message.get(
                        "reason",
                        "manual_stop",
                    ),
                )

            elif command_type == "emergency_stop":
                await asyncio.to_thread(
                    self.motor.stop,
                    "emergency_stop",
                )

            elif command_type == "mode":
                target_mode = str(
                    message.get("mode", "")
                ).strip().lower()

                if target_mode not in {
                    "auto",
                    "manual",
                }:
                    raise RuntimeError(
                        f"지원하지 않는 모드: "
                        f"{target_mode}"
                    )

                if target_mode == "auto":
                    await asyncio.to_thread(
                        self.motor.stop,
                        "auto_mode",
                    )

                self.current_mode = target_mode
                print(f"[mode] {self.current_mode}")

            elif command_type == "speak":
                self.speaker.speak(
                    str(message.get("text", ""))
                )

            elif command_type == "camera_config":
                print(
                    f"[camera_config] {message}"
                )

            else:
                raise RuntimeError(
                    f"unknown command type: "
                    f"{command_type}"
                )

        except Exception as exc:
            ok = False
            error = str(exc)

            if command_type == "move":
                self.motor.stop(
                    reason="move_error",
                    suppress_errors=True,
                )

        await websocket.send(
            json.dumps(
                {
                    "type": "ack",
                    "command_id": message.get(
                        "command_id"
                    ),
                    "ok": ok,
                    "error": error,
                    "mode": self.current_mode,
                    "motion": self.motor.current_motion,
                    "motor_connected": (
                        self.motor.connected
                    ),
                }
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--server-base-url",
        default=os.getenv("SERVER_BASE_URL"),
    )

    parser.add_argument(
        "--robot-id",
        default=os.getenv(
            "ROBOT_ID",
            "pi-01",
        ),
    )

    parser.add_argument(
        "--ws-url",
        default=os.getenv("COMMAND_WS_URL"),
    )

    parser.add_argument(
        "--serial-port",
        default=os.getenv(
            "MOTOR_SERIAL_PORT",
            "/dev/serial0",
        ),
    )

    parser.add_argument(
        "--serial-baudrate",
        type=int,
        default=int(
            os.getenv(
                "MOTOR_SERIAL_BAUDRATE",
                "115200",
            )
        ),
    )

    parser.add_argument(
        "--serial-timeout-sec",
        type=float,
        default=float(
            os.getenv(
                "MOTOR_SERIAL_TIMEOUT_SEC",
                "0.25",
            )
        ),
    )

    parser.add_argument(
        "--command-timeout-sec",
        type=float,
        default=float(
            os.getenv(
                "COMMAND_TIMEOUT_SEC",
                "0.45",
            )
        ),
    )

    parser.add_argument(
        "--status-interval-sec",
        type=float,
        default=float(
            os.getenv(
                "STATUS_INTERVAL_SEC",
                "1.0",
            )
        ),
    )

    parser.add_argument(
        "--ws-reconnect-delay-sec",
        type=float,
        default=float(
            os.getenv(
                "WS_RECONNECT_DELAY_SEC",
                "1.0",
            )
        ),
    )

    parser.add_argument(
        "--encoder-interval-sec",
        type=float,
        default=float(
            os.getenv(
                "ENCODER_INTERVAL_SEC",
                "0.05",
            )
        ),
    )

    args = parser.parse_args()

    if not args.server_base_url:
        parser.error(
            "SERVER_BASE_URL 또는 "
            "--server-base-url이 필요합니다."
        )

    return args


if __name__ == "__main__":
    RobotCommandClient(parse_args()).start()