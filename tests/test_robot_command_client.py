import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock


RASPBERRY_DIR = Path(__file__).resolve().parents[1] / "raspberry"
if str(RASPBERRY_DIR) not in sys.path:
    sys.path.insert(0, str(RASPBERRY_DIR))

from robot_command_client import RobotCommandClient  # noqa: E402


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(json.loads(message))


class RobotCommandClientTests(unittest.IsolatedAsyncioTestCase):
    def make_client(self):
        client = RobotCommandClient.__new__(RobotCommandClient)
        client.current_mode = "manual"
        client.navigation_mode = "mapping"
        client.emergency_stop_latched = False
        client.led_enabled = False
        client._led_task = None
        client.motor = Mock()
        client.motor.current_motion = "stop"
        client.motor.connected = True
        client.speaker = Mock()
        return client

    async def test_emergency_stop_is_latched_until_resume(self):
        client = self.make_client()
        socket = FakeWebSocket()

        await client.handle_command(socket, {"type": "emergency_stop", "command_id": "stop"})
        self.assertTrue(client.emergency_stop_latched)
        self.assertTrue(socket.messages[-1]["ok"])

        client.current_mode = "auto"
        await client.handle_command(
            socket,
            {"type": "auto_drive", "left_mps": 0.1, "right_mps": 0.1, "command_id": "drive"},
        )
        self.assertFalse(socket.messages[-1]["ok"])
        client.motor.drive.assert_not_called()

        await client.handle_command(socket, {"type": "resume_navigation", "command_id": "resume"})
        self.assertFalse(client.emergency_stop_latched)
        self.assertTrue(socket.messages[-1]["ok"])

    async def test_navigation_mode_does_not_change_auto_manual_mode(self):
        client = self.make_client()
        socket = FakeWebSocket()
        await client.handle_command(
            socket,
            {"type": "navigation_mode", "mode": "driving", "command_id": "mode"},
        )
        self.assertEqual("driving", client.navigation_mode)
        self.assertEqual("manual", client.current_mode)
        self.assertTrue(socket.messages[-1]["ok"])

    async def test_led_and_warning_use_pico_led_contract_and_existing_speaker(self):
        client = self.make_client()
        socket = FakeWebSocket()
        await client.handle_command(
            socket,
            {"type": "led", "enabled": True, "duration_ms": 0, "command_id": "led"},
        )
        client.motor.set_led.assert_called_with(True)
        self.assertTrue(client.led_enabled)

        await client.handle_command(
            socket,
            {"type": "warning", "text": "warning", "led_duration_ms": 0, "command_id": "warning"},
        )
        client.motor.set_led.assert_called_with(True)
        client.speaker.speak.assert_called_with("warning")
        self.assertTrue(socket.messages[-1]["ok"])

    def test_duration_rejects_fractional_values(self):
        with self.assertRaisesRegex(RuntimeError, "integer"):
            RobotCommandClient._duration_ms(1.5)


if __name__ == "__main__":
    unittest.main()
