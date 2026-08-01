import math
import time
import unittest

from navigation.dry_run_planner import DryRunPlannerConfig, plan_scan, sector_distances, validate_scan_payload


CONFIG = DryRunPlannerConfig()


def make_scan(front=2.0, left=2.0, right=2.0):
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


class DryRunPlannerTests(unittest.TestCase):
    def decision(self, scan, age=0.0):
        now = time.time()
        return plan_scan(scan, now - age, CONFIG, now=now)

    def test_forward_when_front_is_clear(self):
        decision = self.decision(make_scan(front=1.5))
        self.assertEqual("FORWARD", decision["action"])
        self.assertEqual(0.25, decision["linear_x"])
        self.assertEqual(0.0, decision["angular_z"])

    def test_front_obstacle_turns_left_when_left_is_clearer(self):
        decision = self.decision(make_scan(front=0.32, left=1.4, right=0.7))
        self.assertEqual("TURN_LEFT", decision["action"])
        self.assertEqual(0.65, decision["angular_z"])

    def test_front_obstacle_turns_right_when_right_is_clearer(self):
        decision = self.decision(make_scan(front=0.32, left=0.7, right=1.4))
        self.assertEqual("TURN_RIGHT", decision["action"])
        self.assertEqual(-0.65, decision["angular_z"])

    def test_slow_avoid_uses_open_side(self):
        decision = self.decision(make_scan(front=0.70, left=1.6, right=0.8))
        self.assertEqual("SLOW_AVOID", decision["action"])
        self.assertEqual(0.10, decision["linear_x"])
        self.assertEqual(0.65, decision["angular_z"])

    def test_no_scan_waits(self):
        decision = plan_scan(None, None, CONFIG, now=time.time())
        self.assertEqual("WAITING_FOR_SCAN", decision["action"])

    def test_stale_scan_stops(self):
        decision = self.decision(make_scan(), age=CONFIG.scan_timeout_sec + 0.01)
        self.assertEqual("STOP", decision["action"])
        self.assertEqual("SCAN_TIMEOUT", decision["reason"])

    def test_non_finite_and_out_of_range_values_are_ignored(self):
        scan = make_scan(front=2.0)
        scan["ranges"][170] = None
        scan["ranges"][171] = float("nan")
        scan["ranges"][172] = float("inf")
        scan["ranges"][173] = 0.0
        scan["ranges"][174] = 6.0
        scan["ranges"][175] = 0.8
        front, left, right = sector_distances(scan)
        self.assertEqual(2.0, front)
        self.assertEqual(2.0, left)
        self.assertEqual(2.0, right)

    def test_validation_normalizes_non_finite_ranges_to_null(self):
        scan = make_scan()
        scan["ranges"][90] = float("nan")
        scan["ranges"][91] = float("inf")
        normalized = validate_scan_payload(scan)
        self.assertIsNone(normalized["ranges"][90])
        self.assertIsNone(normalized["ranges"][91])
    def test_all_invalid_front_ranges_stop(self):
        scan = make_scan(front=2.0)
        for degree in range(-20, 21):
            scan["ranges"][degree + 90] = None
        decision = self.decision(scan)
        self.assertEqual("STOP", decision["action"])
        self.assertEqual("FRONT_SECTOR_UNAVAILABLE", decision["reason"])

    def test_stop_and_slow_thresholds_are_inclusive(self):
        stop_decision = self.decision(make_scan(front=0.45, left=1.5, right=0.7))
        slow_decision = self.decision(make_scan(front=0.90, left=1.5, right=0.7))
        self.assertEqual("TURN_LEFT", stop_decision["action"])
        self.assertEqual("SLOW_AVOID", slow_decision["action"])


if __name__ == "__main__":
    unittest.main()
