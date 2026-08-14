from pathlib import Path
from types import SimpleNamespace
import unittest

from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "frontend" / "templates"
STATIC_DIR = ROOT / "frontend" / "services" / "static"


class DashboardFrontendContractTests(unittest.TestCase):
    def setUp(self):
        self.template_source = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
        self.script_source = (STATIC_DIR / "script.js").read_text(encoding="utf-8")
        self.state_source = (STATIC_DIR / "dashboard_state.js").read_text(encoding="utf-8")

    def render_dashboard(self, user):
        environment = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(("html",)),
        )
        return environment.get_template("index.html").render(
            request=SimpleNamespace(session={"user": user}),
            url_for=lambda _name: "/video_feed",
        )

    def test_sidebar_renders_authenticated_account_without_duplicating_logout(self):
        rendered = self.render_dashboard({"name": "테스트 관리자", "login_id": "dashboard_test"})

        self.assertIn("테스트 관리자", rendered)
        self.assertIn("dashboard_test", rendered)
        self.assertEqual(rendered.count('id="logoutBtn"'), 1)
        self.assertIn('id="systemControlPanelSlot"', rendered)

    def test_initial_robot_mode_is_unknown_and_manual_controls_are_disabled(self):
        self.assertIn('id="robot-mode-status">UNKNOWN</span>', self.template_source)
        self.assertIn('class="toggle-switch unknown"', self.template_source)
        self.assertIn('class="card d-pad-container disabled"', self.template_source)
        self.assertIn("applyServerPatrolMode(null)", self.script_source)

    def test_state_module_uses_server_polling_and_optional_backend_contracts(self):
        self.assertIn("robotState: '/api/robots/pi-01'", self.state_source)
        self.assertIn("window.setInterval(pollRobotState, 1000)", self.state_source)
        self.assertIn("window.DABOM_DASHBOARD_ENDPOINTS", self.state_source)
        self.assertIn("fetchLogRows", self.state_source)
        self.assertIn("state: 'unavailable'", self.state_source)

    def test_disconnect_and_stale_state_fail_closed(self):
        self.assertIn("ROBOT_STATUS_STALE_MS = 5000", self.script_source)
        self.assertIn("currentRobotConnected !== false", self.script_source)
        self.assertIn("stopAllLocalInputs(false)", self.script_source)
        self.assertIn("clearRobotSnapshotState", self.state_source)
        self.assertIn("setText('emergency-stop-status', 'UNAVAILABLE')", self.state_source)

    def test_changed_assets_have_matching_cache_busters(self):
        version = "v=20260814-server-state"
        for asset in (
            "static/style.css",
            "static/script.js",
            "static/system_control.js",
            "static/navigation_map_control.js",
            "static/dashboard_state.js",
        ):
            self.assertIn(f'{asset}?{version}', self.template_source)

    def test_existing_safety_and_logout_contracts_remain_present(self):
        for contract in (
            "button_release",
            "pointer_cancel",
            "key_release",
            "window_blur",
            "page_hidden",
            "/api/auth/logout",
        ):
            self.assertIn(contract, self.script_source)

    def test_state_script_loads_after_existing_state_producers(self):
        script_position = self.template_source.index("static/script.js")
        system_position = self.template_source.index("static/system_control.js")
        map_position = self.template_source.index("static/navigation_map_control.js")
        state_position = self.template_source.index("static/dashboard_state.js")

        self.assertLess(script_position, state_position)
        self.assertLess(system_position, state_position)
        self.assertLess(map_position, state_position)


if __name__ == "__main__":
    unittest.main()
