from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "frontend" / "services" / "static"
CONTROLS = ROOT / "frontend" / "components" / "controls"
TEMPLATE = ROOT / "frontend" / "templates" / "index.html"


class DashboardStateControlContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (STATIC / "script.js").read_text(encoding="utf-8")
        cls.state = (STATIC / "dashboard_state.js").read_text(encoding="utf-8")
        cls.navigation = (STATIC / "navigation_control.js").read_text(encoding="utf-8")
        cls.drive = (CONTROLS / "drive_mode_control.js").read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")

    def test_existing_lever_is_the_only_dashboard_drive_mode_control(self):
        self.assertEqual(self.template.count('data-dashboard-control="drive-mode"'), 1)
        self.assertEqual(self.template.count('onclick="togglePatrolMode()"'), 1)
        self.assertNotIn("createButton(root.ownerDocument, '자동'", self.drive)
        self.assertNotIn("createButton(root.ownerDocument, '수동'", self.drive)
        self.assertIn("root.querySelector('[data-dashboard-control=\"drive-mode\"]')", self.drive)

    def test_navigation_control_state_is_the_only_control_state_source(self):
        self.assertNotIn("robotState: '/api/robots/pi-01'", self.state)
        self.assertNotIn("pollRobotState", self.state)
        self.assertNotIn("dabom:system-control-status", self.state)
        self.assertNotIn("dabom:robot-status", self.state)
        self.assertIn("dabom:navigation-control-state", self.state)
        self.assertIn("window.applyServerPatrolMode?.(payload?.robot_mode)", self.navigation)
        telemetry = self.script[
            self.script.index("function fetchRobotStatus()"):
            self.script.index("// 카메라 연결 상태 폴링")
        ]
        self.assertNotIn("applyServerPatrolMode", telemetry)
        self.assertIn("dabom:telemetry-status", telemetry)

    def test_mode_lever_uses_the_navigation_command_path(self):
        toggle = self.script[
            self.script.index("async function togglePatrolMode()"):
            self.script.index("window.moveRobot")
        ]
        self.assertIn("window.navigationControl?.requestDriveMode", toggle)
        self.assertNotIn("sendRobotCommand({", toggle)

    def test_keyboard_allows_arrows_only_and_blocks_interactive_contexts(self):
        drive_keys = self.script[
            self.script.index("const DRIVE_KEYS"):
            self.script.index("let pointerMoveInterval")
        ]
        for key in ("ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"):
            self.assertIn(f"'{key}'", drive_keys)
        for key in ("'w'", "'a'", "'s'", "'d'"):
            self.assertNotIn(key, drive_keys)
        for selector in (
            "element?.matches('input, textarea, select')",
            "element?.isContentEditable",
            "[contenteditable]:not([contenteditable=\"false\"])",
            "modal.dataset.modalView",
            "modal.style.display === 'flex'",
            "classList.contains('open')",
        ):
            self.assertIn(selector, self.script)
        self.assertIn("isKeyboardDrivingBlocked(event.target)", self.script)

    def test_dpad_and_arrow_commands_follow_the_visible_direction(self):
        expected = {
            "↑": "forward",
            "↓": "backward",
            "←": "rotate_left",
            "→": "rotate_right",
            "↖": "forward_left",
            "↗": "forward_right",
            "↙": "backward_left",
            "↘": "backward_right",
        }
        mapping = self.script[
            self.script.index("function directionToCommand"):
            self.script.index("function robotCommandCsrfToken")
        ]
        for glyph, command in expected.items():
            self.assertIn(f"'{glyph}': '{command}'", mapping)

    def test_warning_is_connection_aware_but_report_is_independent(self):
        self.assertIn("document.querySelector('.action-warning')", self.navigation)
        self.assertIn("payload.connected !== true || state.warningPending", self.navigation)
        self.assertIn("if (state.control?.connected !== true)", self.navigation)
        self.assertNotIn(".action-report", self.navigation)
        self.assertIn("document.querySelector('.action-report')", self.script)
        self.assertNotIn("currentRobotConnected", self.script[
            self.script.index("async function reportDanger"):
            self.script.index("function warnTrespasser")
        ])

    def test_conflicts_have_user_facing_messages(self):
        for code in (
            "PI_OFFLINE",
            "DRIVING_MODE_REQUIRED",
            "NAVIGATION_NOT_READY",
            "AUTO_MODE_REQUIRED",
            "GOAL_OUT_OF_BOUNDS",
        ):
            self.assertIn(f"{code}:", self.navigation)
        self.assertIn("현재 Navigation 상태와 요청이 충돌했습니다.", self.navigation)
        self.assertIn("Pi가 연결되지 않아 명령을 전달하지 못했습니다.", self.script)

    def test_goal_uses_red_flag_and_alert_clear_has_a_cutoff(self):
        self.assertIn("ctx.fillText('🚩'", self.navigation)
        self.assertNotIn("ctx.strokeStyle = '#a855f7';\n        ctx.fillStyle = '#a855f7';", self.navigation)
        self.assertIn("dabom:alerts-cleared", self.script)
        self.assertIn("alertClearCutoffMs", self.state)
        self.assertIn("parsed.getTime() > alertClearCutoffMs", self.state)
        self.assertIn("state.hazardEntries = []", self.navigation)


if __name__ == "__main__":
    unittest.main()
