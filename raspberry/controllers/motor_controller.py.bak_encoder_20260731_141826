from __future__ import annotations

import re
import threading
import time
from typing import Optional

try:
    import serial
except ImportError:
    serial = None


ALLOWED_DIRECTIONS = frozenset(
    {
        "forward",
        "backward",
        "left",
        "right",
        "forward_left",
        "forward_right",
        "backward_left",
        "backward_right",
        "rotate_left",
        "rotate_right",
    }
)

_REASON_PATTERN = re.compile(r"[^a-zA-Z0-9_-]+")


class MotorControllerError(RuntimeError):
    """Pi-Pico UART 모터 제어 오류."""


class MotorController:
    """
    Raspberry Pi에서 UART를 통해 Pico W로 모터 명령을 전달한다.

    프로토콜:
      MOVE,<direction>,<speed>
      STOP,<reason>
      PING
    """

    def __init__(
        self,
        serial_port: str = "/dev/serial0",
        baudrate: int = 115200,
        command_timeout_sec: float = 0.45,
        serial_timeout_sec: float = 0.25,
    ) -> None:
        self.serial_port = serial_port
        self.baudrate = int(baudrate)
        self.command_timeout_sec = max(0.1, float(command_timeout_sec))
        self.serial_timeout_sec = max(0.05, float(serial_timeout_sec))

        self.last_command_at = 0.0
        self.current_motion = "stop"

        self._serial: Optional[object] = None
        self._lock = threading.RLock()

    @property
    def connected(self) -> bool:
        with self._lock:
            return bool(
                self._serial is not None
                and self._serial.is_open
            )

    def _close_serial_locked(self) -> None:
        serial_device = self._serial
        self._serial = None

        if serial_device is not None:
            try:
                serial_device.close()
            except Exception:
                pass

    def _exchange_locked(self, command: str) -> str:
        if self._serial is None or not self._serial.is_open:
            raise MotorControllerError(
                "Pico W UART가 연결되지 않았습니다."
            )

        try:
            self._serial.reset_input_buffer()
            self._serial.write(
                (command + "\n").encode("ascii")
            )
            self._serial.flush()

            response = (
                self._serial.readline()
                .decode("ascii", errors="replace")
                .strip()
            )
        except Exception as exc:
            self._close_serial_locked()
            raise MotorControllerError(
                f"Pico W UART 통신 실패: {exc}"
            ) from exc

        if not response:
            self._close_serial_locked()
            raise MotorControllerError(
                "Pico W 응답 시간 초과"
            )

        if not response.startswith("OK"):
            raise MotorControllerError(
                f"Pico W 명령 거부: {response}"
            )

        return response

    def _ensure_connected_locked(self) -> None:
        if self._serial is not None and self._serial.is_open:
            return

        if serial is None:
            raise MotorControllerError(
                "pyserial이 설치되지 않았습니다. "
                "python3 -m pip install "
                "-r raspberry/requirements.txt 를 실행하십시오."
            )

        try:
            self._serial = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                timeout=self.serial_timeout_sec,
                write_timeout=self.serial_timeout_sec,
            )

            self._exchange_locked("PING")
            self._exchange_locked("STOP,pi_connected")

            print(
                f"[motor] Pico W connected: "
                f"{self.serial_port} @ {self.baudrate}"
            )

        except Exception:
            self._close_serial_locked()
            raise

    @staticmethod
    def _sanitize_reason(reason: str) -> str:
        cleaned = _REASON_PATTERN.sub(
            "_",
            str(reason),
        ).strip("_")

        return (cleaned or "stop")[:48]

    def move(
        self,
        direction: str,
        speed: float = 0.35,
    ) -> None:
        direction = str(direction).strip().lower()

        if direction not in ALLOWED_DIRECTIONS:
            raise MotorControllerError(
                f"지원하지 않는 이동 방향: {direction}"
            )

        try:
            normalized_speed = float(speed)
        except (TypeError, ValueError) as exc:
            raise MotorControllerError(
                f"잘못된 속도 값: {speed}"
            ) from exc

        normalized_speed = max(
            0.0,
            min(normalized_speed, 1.0),
        )

        if normalized_speed <= 0.0:
            self.stop(reason="zero_speed")
            return

        with self._lock:
            self._ensure_connected_locked()

            self._exchange_locked(
                f"MOVE,{direction},{normalized_speed:.3f}"
            )

            self.last_command_at = time.monotonic()
            self.current_motion = direction

    def stop(
        self,
        reason: str = "stop",
        suppress_errors: bool = False,
    ) -> None:
        error: Optional[Exception] = None

        with self._lock:
            self.current_motion = "stop"
            self.last_command_at = time.monotonic()

            try:
                self._ensure_connected_locked()

                self._exchange_locked(
                    f"STOP,{self._sanitize_reason(reason)}"
                )

            except Exception as exc:
                error = exc
                self._close_serial_locked()

        if error is not None:
            if suppress_errors:
                print(
                    f"[motor] stop 전달 실패 "
                    f"({reason}): {error}"
                )
                return

            raise MotorControllerError(
                str(error)
            ) from error

    def failsafe_tick(self) -> None:
        with self._lock:
            expired = (
                self.current_motion != "stop"
                and time.monotonic() - self.last_command_at
                > self.command_timeout_sec
            )

        if expired:
            print("[motor] command timeout -> stop")

            self.stop(
                reason="command_timeout",
                suppress_errors=True,
            )

    def close(self) -> None:
        self.stop(
            reason="controller_close",
            suppress_errors=True,
        )

        with self._lock:
            self._close_serial_locked()