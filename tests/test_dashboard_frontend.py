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
        self.style_source = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
        self.app_source = (ROOT / "server" / "app.py").read_text(encoding="utf-8")

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
        version = "v=20260823-records-followup"
        for asset in (
            "static/style.css",
            "static/script.js",
            "static/system_control.js",
            "static/navigation_map_control.js",
            "static/dashboard_state.js",
        ):
            self.assertIn(f'{asset}?{version}', self.template_source)

    def test_robot_commands_include_session_csrf_contract(self):
        self.assertIn("function robotCommandCsrfToken()", self.script_source)
        self.assertIn("'/api/auth/csrf'", self.script_source)
        self.assertIn("'X-CSRF-Token': csrfToken", self.script_source)
        self.assertIn("credentials: 'same-origin'", self.script_source)

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

    def test_current_situation_frontend_matches_authenticated_json_api(self):
        for contract in (
            "/api/logs/current-situation/preview",
            "X-Frame-Token",
            "description_content: description",
            "include_image: includeImage",
            "frame_token: includeImage ? currentSituationState.frameToken : null",
            "JSON.stringify",
            "response.status === 503",
        ):
            self.assertIn(contract, self.script_source)
        self.assertIn('@app.post("/api/logs/current-situation/preview")', self.app_source)
        self.assertIn('@app.post("/api/logs/current-situation")', self.app_source)

    def test_gallery_filters_and_media_urls_match_backend_contract(self):
        for contract in (
            "/api/gallery?source=",
            "loadGallery('all')",
            "loadGallery('event')",
            "loadGallery('action')",
            "/api/media/events/",
            "/api/media/actions/",
        ):
            self.assertIn(contract, self.script_source)
        for route in (
            '@app.get("/api/gallery")',
            '@app.get("/api/media/events/{event_id}")',
            '@app.get("/api/media/actions/{action_id}")',
        ):
            self.assertIn(route, self.app_source)

    def test_dashboard_log_panels_use_existing_backend_endpoints(self):
        self.assertIn("deviceLogs: '/api/logs/system-status'", self.state_source)
        self.assertIn("patrolLogs: '/api/logs/events'", self.state_source)
        self.assertIn("actionLogs: '/api/logs/actions'", self.state_source)
        for route in (
            '@app.get("/api/logs/system-status")',
            '@app.get("/api/logs/events")',
            '@app.get("/api/logs/actions")',
        ):
            self.assertIn(route, self.app_source)

    def test_log_time_filters_are_sent_to_backend_queries(self):
        for contract in (
            "query.set('start_at', filters.startAt)",
            "query.set('end_at', filters.endAt)",
            "fetchLogRows(type, range)",
        ):
            self.assertIn(contract, self.state_source + self.script_source)
        self.assertNotIn("st.allRows.filter(row =>", self.script_source)

    def test_patrol_records_support_detected_time_false_alarm_and_gallery_detail(self):
        self.assertIn(
            "source.detected_at, source.timestamp, source.created_at",
            self.state_source,
        )
        self.assertIn("is_false_alarm: row.is_false_alarm === true", self.state_source)
        for contract in (
            "/api/logs/events/${encodeURIComponent(eventId)}/false-alarm",
            "method: 'PATCH'",
            "JSON.stringify({ is_false_alarm: Boolean(isFalseAlarm) })",
            "openPatrolGalleryDetail(this.dataset.recordId)",
            "findIndex(item => String(item.event_id ?? item.id) === String(eventId))",
        ):
            self.assertIn(contract, self.script_source)

    def test_header_is_compact_and_gallery_keeps_three_column_maximum(self):
        self.assertIn("min-height: 36px;", self.style_source)
        self.assertIn("margin: 0 0 6px;", self.style_source)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", self.style_source)

    def test_current_situation_has_no_browser_capture_or_binary_upload(self):
        block = self.script_source.split("// 현재 상황 기록", 1)[1].split("// 갤러리", 1)[0]
        for forbidden in ("getUserMedia", "toDataURL", "FormData", "multipart", "canvas"):
            self.assertNotIn(forbidden, block)
        self.assertIn("'Content-Type': 'application/json'", block)

    def test_gallery_delete_uses_frozen_contract_and_updates_detail_state(self):
        block = self.script_source.split("// 갤러리", 1)[1].split("// 텔레그램 신고", 1)[0]
        for contract in (
            "confirm('이 이미지를 갤러리에서 삭제하시겠습니까?')",
            "`/api/gallery/${source}/${encodeURIComponent(recordId)}`",
            "method: 'DELETE'",
            "credentials: 'same-origin'",
            "'X-CSRF-Token': csrfToken",
            "galleryState.items.splice(removedIndex, 1)",
            "openGalleryDetail(Math.min(removedIndex, galleryState.items.length - 1))",
            "closeGalleryDetail()",
        ):
            self.assertIn(contract, block)
        self.assertNotIn("loadGallery(galleryState.source)", block)

    def test_gallery_action_source_wins_over_related_event_id(self):
        block = self.script_source.split("// 갤러리", 1)[1].split("// 텔레그램 신고", 1)[0]
        explicit_source = "if (item.source === 'event' || item.source === 'action') return item.source;"
        event_fallback = "if (item.event_id != null) return 'event';"
        action_id = ": item.action_id ?? item.id;"
        self.assertIn(explicit_source, block)
        self.assertIn(event_fallback, block)
        self.assertLess(block.index(explicit_source), block.index(event_fallback))
        self.assertIn(action_id, block)
        self.assertIn("`/api/gallery/${source}/${encodeURIComponent(recordId)}`", block)


if __name__ == "__main__":
    unittest.main()
