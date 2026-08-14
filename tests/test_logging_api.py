import importlib
import os
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.database import DatabaseConfigurationError


os.environ["INFERENCE_ENABLED"] = "false"
os.environ["VISUALIZATION_ENABLED"] = "false"
os.environ["MODEL_REQUIRED"] = "false"
os.environ["COOKIE_SECURE"] = "false"


class FakeDatabase:
    def __init__(self):
        self.filters = None
        self.actions = []
        self.reported = []
        self.rows = {
            "system": [],
            "events": [{"event_id": 7, "detected_at": datetime(2026, 8, 14, 9)}],
            "actions": [],
        }

    def list_system_status(self, **filters):
        self.filters = filters
        return self.rows["system"]

    def list_events(self, **filters):
        self.filters = filters
        return self.rows["events"]

    def list_actions(self, **filters):
        self.filters = filters
        return self.rows["actions"]

    def insert_action(self, **values):
        self.actions.append(values)
        return len(self.actions)

    def mark_event_reported(self, event_id):
        self.reported.append(event_id)
        return True

    def event_exists(self, event_id):
        return event_id == 7


@pytest.fixture
def api():
    try:
        from fastapi.testclient import TestClient
    except ImportError as exc:
        pytest.skip(f"FastAPI test dependencies are unavailable: {exc}")
    server = importlib.import_module("server.app")
    client = TestClient(server.app)
    fake_database = FakeDatabase()
    original_database = server.database
    server.database = fake_database
    client.cookies.clear()
    try:
        yield server, client, fake_database
    finally:
        server.database = original_database
        client.close()


def login(server, client):
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    user = {"user_id": 11, "email": "tester@example.com", "name": "tester"}
    with patch.object(server, "call_auth", AsyncMock(return_value=(user, None))):
        response = client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"login_id": "tester@example.com", "password": "Password1"},
        )
    assert response.status_code == 200
    return client.get("/api/auth/csrf").json()["csrf_token"]


def test_read_apis_require_authentication_and_empty_is_200(api):
    server, client, database = api
    assert client.get("/api/logs/system-status").status_code == 401
    login(server, client)
    response = client.get("/api/logs/system-status")
    assert response.status_code == 200
    assert response.json() == []


def test_read_api_filters_latest_rows_with_a_bounded_limit(api):
    server, client, database = api
    login(server, client)
    response = client.get(
        "/api/logs/events",
        params={
            "start_at": "2026-08-01T00:00:00Z",
            "end_at": "2026-08-14T23:59:59Z",
            "limit": "25",
        },
    )
    assert response.status_code == 200
    assert response.json()[0]["event_id"] == 7
    assert database.filters["limit"] == 25
    assert database.filters["start_at"] == datetime(2026, 8, 1)
    assert database.filters["end_at"] == datetime(2026, 8, 14, 23, 59, 59)
    assert client.get("/api/logs/events?limit=501").status_code == 400


def test_database_unavailable_is_clear_503(api):
    server, client, database = api
    login(server, client)
    database.list_events = Mock(side_effect=DatabaseConfigurationError("offline"))
    response = client.get("/api/logs/events")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database is unavailable."


def test_action_api_uses_enum_and_has_no_cooldown(api):
    server, client, database = api
    csrf = login(server, client)
    for _ in range(2):
        response = client.post(
            "/api/logs/actions",
            headers={"X-CSRF-Token": csrf},
            json={"action_type": "NOTE", "event_id": None, "description": "checked"},
        )
        assert response.status_code == 201
    assert len(database.actions) == 2
    assert all(action["action_type"] == "NOTE" for action in database.actions)
    invalid = client.post(
        "/api/logs/actions",
        headers={"X-CSRF-Token": csrf},
        json={"action_type": "NEW_ENUM"},
    )
    assert invalid.status_code == 400


def test_manual_report_is_authenticated_csrf_protected_and_not_cooled_down(api):
    server, client, database = api
    original_token, original_chat = server.TELEGRAM_TOKEN, server.TELEGRAM_CHAT_ID
    server.TELEGRAM_TOKEN, server.TELEGRAM_CHAT_ID = "test-token", "test-chat"
    response = Mock(status_code=200)
    try:
        assert client.post("/send_telegram", json={}).status_code == 401
        csrf = login(server, client)
        assert client.post("/send_telegram", json={}).status_code == 403
        with patch.object(server.requests, "post", return_value=response) as sender:
            for _ in range(2):
                result = client.post(
                    "/send_telegram",
                    headers={"X-CSRF-Token": csrf},
                    json={"event_id": 7},
                )
                assert result.status_code == 200
        assert sender.call_count == 2
        assert len(database.actions) == 2
        assert database.reported == [7, 7]
    finally:
        server.TELEGRAM_TOKEN, server.TELEGRAM_CHAT_ID = original_token, original_chat


def test_manual_report_does_not_send_for_missing_event(api):
    server, client, database = api
    original_token, original_chat = server.TELEGRAM_TOKEN, server.TELEGRAM_CHAT_ID
    server.TELEGRAM_TOKEN, server.TELEGRAM_CHAT_ID = "test-token", "test-chat"
    try:
        csrf = login(server, client)
        with patch.object(server.requests, "post") as sender:
            result = client.post(
                "/send_telegram",
                headers={"X-CSRF-Token": csrf},
                json={"event_id": 999},
            )
        assert result.status_code == 404
        sender.assert_not_called()
        assert database.actions == []
    finally:
        server.TELEGRAM_TOKEN, server.TELEGRAM_CHAT_ID = original_token, original_chat


def test_manual_report_returns_success_if_post_send_event_update_fails(api):
    server, client, database = api
    original_token, original_chat = server.TELEGRAM_TOKEN, server.TELEGRAM_CHAT_ID
    server.TELEGRAM_TOKEN, server.TELEGRAM_CHAT_ID = "test-token", "test-chat"
    database.mark_event_reported = Mock(
        side_effect=DatabaseConfigurationError("offline")
    )
    try:
        csrf = login(server, client)
        with patch.object(server.requests, "post", return_value=Mock(status_code=200)):
            result = client.post(
                "/send_telegram",
                headers={"X-CSRF-Token": csrf},
                json={"event_id": 7},
            )
        assert result.status_code == 200
        payload = result.json()
        assert payload["status"] == "success"
        assert "persistence_warning" in payload
        assert len(database.actions) == 1
    finally:
        server.TELEGRAM_TOKEN, server.TELEGRAM_CHAT_ID = original_token, original_chat
