import importlib
import os
import subprocess
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

os.environ["INFERENCE_ENABLED"] = "false"
os.environ["VISUALIZATION_ENABLED"] = "false"
os.environ["MODEL_REQUIRED"] = "false"
os.environ["NAV_DRY_RUN_ENABLED"] = "true"
os.environ["ROBOT_CONTROL_TOKEN"] = "test-robot-token"
os.environ["ROBOT_ID"] = "pi-01"
os.environ["DASHBOARD_ESTOP_COOLDOWN_SEC"] = "1.5"
os.environ["DASHBOARD_GOAL_REACHED_TOLERANCE_M"] = "0.25"


class NavigationSnapshotApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            raise unittest.SkipTest(
                f"FastAPI test dependencies are unavailable: {exc}"
            )
        cls.server = importlib.import_module("server.app")
        cls.client = TestClient(cls.server.app)

    def setUp(self):
        with self.server.state_lock:
            self.server.navigation_state.update(
                {
                    "robot_id": "pi-01",
                    "mode": "mapping",
                    "mode_updated_at": None,
                    "map": None,
                    "pose": None,
                    "scan": None,
                    "decision": None,
                    "map_updated_at": None,
                    "map_revision": None,
                    "pose_updated_at": None,
                    "scan_updated_at": None,
                }
            )

    def test_snapshot_combines_status_pose_scan_and_initial_map(self):
        observed_at = time.time()
        revision = "revision-a"
        current_map = {
            "width": 2,
            "height": 1,
            "resolution": 0.05,
            "data": [[0, 2]],
        }
        pose = {"x": 1.0, "y": 2.0, "yaw": 0.5}
        scan = {"ranges": [0.4, 0.8], "received_at": observed_at}
        with self.server.state_lock:
            self.server.navigation_state.update(
                {
                    "map": current_map,
                    "pose": pose,
                    "scan": scan,
                    "map_updated_at": observed_at,
                    "map_revision": revision,
                    "pose_updated_at": observed_at,
                    "scan_updated_at": observed_at,
                }
            )

        body = self.client.get("/api/navigation/snapshot").json()

        self.assertTrue(body["ok"])
        self.assertEqual("mapping", body["status"]["status"])
        self.assertEqual(pose, body["pose"])
        self.assertEqual(scan, body["scan"])
        self.assertTrue(body["map_changed"])
        self.assertEqual(revision, body["map_revision"])
        self.assertEqual(current_map, body["map"])

    def test_snapshot_omits_unchanged_map_payload(self):
        map_payload = {
            "robot_id": "pi-01",
            "navigation_mode": "mapping",
            "frame_id": "map",
            "timestamp": "2026-08-30T00:00:00Z",
            "bridge_timestamp": "2026-08-30T00:00:01Z",
            "resolution": 0.05,
            "width": 1,
            "height": 1,
            "origin": {"x": 0, "y": 0, "yaw": 0},
            "data_encoding": "rle",
            "data": [[0, 1]],
        }
        first = self.client.post(
            "/navigation/map",
            json=map_payload,
            headers={"X-Robot-Control-Token": "test-robot-token"},
        )
        self.assertEqual(200, first.status_code)
        revision = self.client.get("/api/navigation/snapshot").json()[
            "map_revision"
        ]

        map_payload["bridge_timestamp"] = "2026-08-30T00:00:03Z"
        repeated = self.client.post(
            "/navigation/map",
            json=map_payload,
            headers={"X-Robot-Control-Token": "test-robot-token"},
        )
        self.assertEqual(200, repeated.status_code)

        body = self.client.get(
            "/api/navigation/snapshot",
            params={"map_revision": revision},
        ).json()

        self.assertTrue(body["map_available"])
        self.assertFalse(body["map_changed"])
        self.assertNotIn("map", body)

    def test_snapshot_includes_map_again_after_revision_changes(self):
        previous_revision = "revision-a"
        next_revision = "revision-b"
        next_map = {"width": 2, "height": 1, "data": [[0, 2]]}
        with self.server.state_lock:
            self.server.navigation_state.update(
                {
                    "map": next_map,
                    "map_updated_at": time.time(),
                    "map_revision": next_revision,
                }
            )

        body = self.client.get(
            "/api/navigation/snapshot",
            params={"map_revision": previous_revision},
        ).json()

        self.assertTrue(body["map_changed"])
        self.assertEqual(next_revision, body["map_revision"])
        self.assertEqual(next_map, body["map"])


class NavigationPollingEfficiencyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dashboard = (
            ROOT / "frontend/services/static/script.js"
        ).read_text(encoding="utf-8")
        cls.control = (
            ROOT / "frontend/services/static/navigation_control.js"
        ).read_text(encoding="utf-8")

    def test_visual_polling_uses_one_non_overlapping_snapshot_loop(self):
        self.assertIn("const NAVIGATION_SNAPSHOT_VISIBLE_MS = 500", self.dashboard)
        self.assertIn("const NAVIGATION_SNAPSHOT_HIDDEN_MS = 2000", self.dashboard)
        self.assertIn("const NAVIGATION_SNAPSHOT_TIMEOUT_MS = 1000", self.dashboard)
        self.assertIn("/api/navigation/snapshot?map_revision=", self.dashboard)
        self.assertIn("navigationSnapshotInFlight", self.dashboard)
        self.assertIn("document.hidden", self.dashboard)
        for obsolete in (
            "fetchOptionalJson('/api/navigation/status')",
            "fetchOptionalJson('/api/navigation/map')",
            "fetchOptionalJson('/api/navigation/pose')",
            "fetchOptionalJson('/api/navigation/scan')",
        ):
            self.assertNotIn(obsolete, self.dashboard)

    def test_authoritative_control_poll_remains_750ms_and_non_overlapping(self):
        self.assertIn("const POLL_MS = 750", self.control)
        self.assertIn("const CONTROL_REFRESH_TIMEOUT_MS = 700", self.control)
        self.assertIn("'/api/navigation/control/state',", self.control)
        self.assertIn("{ signal: controller.signal }", self.control)
        self.assertIn("() => controller.abort()", self.control)
        self.assertIn("if (state.controlRefreshPromise)", self.control)
        self.assertIn("window.setInterval(refreshState, POLL_MS)", self.control)

    def test_visible_and_hidden_request_rates_match_contract(self):
        control_rate = 1000 / 750
        visible_rate = control_rate + 1000 / 500
        hidden_rate = control_rate + 1000 / 2000
        self.assertAlmostEqual(3.333, visible_rate, places=3)
        self.assertAlmostEqual(1.833, hidden_rate, places=3)

    def test_hung_requests_abort_without_overlap_and_polling_can_resume(self):
        result = subprocess.run(
            ["node", "-e", r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const controlSource = fs.readFileSync(
    'frontend/services/static/navigation_control.js',
    'utf8',
);
const refreshLogic = controlSource.slice(
    controlSource.indexOf('function refreshState()'),
    controlSource.indexOf('function canSetGoal'),
);

async function verifyControlRecovery() {
    let requests = 0;
    const state = { controlRefreshPromise: null };
    const context = {
        AbortController,
        state,
        setFeedback: () => {},
        applyControlState: () => {},
        requestJson: (_url, { signal }) => {
            requests += 1;
            return new Promise((resolve, reject) => {
                signal.addEventListener('abort', () => reject(new Error('aborted')));
            });
        },
    };
    context.window = {
        setTimeout: (callback) => setTimeout(callback, 5),
        clearTimeout,
    };
    vm.createContext(context);
    vm.runInContext(
        `const CONTROL_REFRESH_TIMEOUT_MS = 5; ${refreshLogic}`,
        context,
    );
    const first = context.refreshState();
    const overlapping = context.refreshState();
    assert.strictEqual(first, overlapping);
    await first;
    assert.strictEqual(requests, 1);
    await context.refreshState();
    assert.strictEqual(requests, 2);
}

const dashboardSource = fs.readFileSync(
    'frontend/services/static/script.js',
    'utf8',
);
const snapshotLogic = dashboardSource.slice(
    dashboardSource.indexOf('let navigationSnapshotTimer'),
    dashboardSource.indexOf("window.addEventListener('resize'"),
);

async function verifySnapshotRecovery() {
    let aborts = 0;
    let renders = 0;
    let schedules = 0;
    const context = {
        AbortController,
        encodeURIComponent,
        performance,
        lidarState: {},
        noteScanUpdate: () => {},
        requestLidarRender: () => { renders += 1; },
        fetchOptionalJson: (_url, { signal }) => new Promise(resolve => {
            signal.addEventListener('abort', () => {
                aborts += 1;
                resolve(null);
            });
        }),
        document: {
            hidden: false,
            addEventListener: () => {},
        },
    };
    context.window = {
        setTimeout: (callback, delay) => {
            if (delay === 5) return setTimeout(callback, delay);
            schedules += 1;
            return schedules;
        },
        clearTimeout,
    };
    vm.createContext(context);
    vm.runInContext(
        `const NAVIGATION_SNAPSHOT_VISIBLE_MS = 50;
         const NAVIGATION_SNAPSHOT_HIDDEN_MS = 200;
         const NAVIGATION_SNAPSHOT_TIMEOUT_MS = 5;
         ${snapshotLogic}`,
        context,
    );
    await new Promise(resolve => setTimeout(resolve, 15));
    assert.strictEqual(aborts, 1);
    assert.strictEqual(renders, 1);
    assert.strictEqual(schedules, 1);
    await context.fetchNavigationSnapshot();
    assert.strictEqual(aborts, 2);
    assert.strictEqual(renders, 2);
}

(async () => {
    await verifyControlRecovery();
    await verifySnapshotRecovery();
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
"""],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
