import importlib
import math
import os
import time
import unittest


os.environ["INFERENCE_ENABLED"] = "false"
os.environ["VISUALIZATION_ENABLED"] = "false"
os.environ["MODEL_REQUIRED"] = "false"
os.environ["NAV_DRY_RUN_ENABLED"] = "true"


def valid_scan(front=0.32, left=1.4, right=0.72):
    ranges = [2.0] * 181
    for degree in range(-90, 91):
        index = degree + 90
        if -20 <= degree <= 20:
            ranges[index] = front
        elif 20 < degree <= 90:
            ranges[index] = left
        elif -90 <= degree < -20:
            ranges[index] = right
    return {
        "robot_id": "pi-01",
        "frame_id": "laser",
        "timestamp": "2026-07-28T00:00:00Z",
        "angle_min": -math.pi / 2,
        "angle_max": math.pi / 2,
        "angle_increment": math.pi / 180,
        "range_min": 0.12,
        "range_max": 5.0,
        "ranges": ranges,
    }


class NavigationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            raise unittest.SkipTest(f"FastAPI test dependencies are unavailable: {exc}")
        cls.server = importlib.import_module("server.app")
        cls.client = TestClient(cls.server.app)

    def setUp(self):
        with self.server.state_lock:
            self.server.navigation_state.update(
                {
                    "robot_id": "pi-01",
                    "scan": None,
                    "decision": None,
                    "scan_updated_at": None,
                    "map": None,
                    "pose": None,
                    "map_updated_at": None,
                    "pose_updated_at": None,
                }
            )

    def test_scan_post_and_decision_get(self):
        posted = self.client.post("/navigation/scan", json=valid_scan())
        self.assertEqual(200, posted.status_code)
        self.assertEqual({"ok": True}, posted.json())

        decision = self.client.get("/api/navigation/decision")
        self.assertEqual(200, decision.status_code)
        body = decision.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["dry_run"])
        self.assertFalse(body["motor_output_enabled"])
        self.assertEqual("TURN_LEFT", body["action"])
        self.assertEqual(0.32, body["front_distance_m"])

    def test_stale_scan_returns_stop(self):
        self.client.post("/navigation/scan", json=valid_scan(front=1.5))
        with self.server.state_lock:
            self.server.navigation_state["scan_updated_at"] = time.time() - self.server.NAV_DRY_RUN_CONFIG.scan_timeout_sec - 0.05
        body = self.client.get("/api/navigation/decision").json()
        self.assertEqual("STOP", body["action"])
        self.assertEqual("SCAN_TIMEOUT", body["reason"])

    def test_bad_scan_payload_returns_400(self):
        response = self.client.post("/navigation/scan", json={"ranges": []})
        self.assertEqual(400, response.status_code)
        self.assertFalse(response.json()["ok"])


if __name__ == "__main__":
    unittest.main()
