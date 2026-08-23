from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import threading
import time

from server.database import Database, DatabaseConfig
from server.logging_service import EventLogWorker, SystemStatusWriter


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.executions = []
        self.lastrowid = 41
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        self.executions.append((" ".join(sql.split()), params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class DatabaseHarness(Database):
    def __init__(self, cursor):
        super().__init__(DatabaseConfig("host", 3306, "dabom", "user", "pw", 1))
        self.cursor = cursor

    @contextmanager
    def transaction(self):
        yield FakeConnection(self.cursor)


def test_database_writes_schema_columns_and_nulls_with_bound_parameters():
    cursor = FakeCursor()
    database = DatabaseHarness(cursor)
    status_id = database.insert_system_status(
        {
            "cpu_usage": 20.5,
            "cpu_temperature": None,
            "ram_usage": 33.0,
            "ping": None,
            "battery_level": 80,
            "is_autonomous": 1,
            "speed": None,
            "gps_lat": None,
            "gps_lng": None,
            "gps_alt": None,
            "lidar_x": None,
            "lidar_y": None,
            "lidar_z": None,
        }
    )
    assert status_id == 41
    sql, params = cursor.executions[0]
    assert "INSERT INTO system_status" in sql
    assert "%s" in sql
    assert params[1] is None
    assert params[3] is None
    assert params[6] is None
    assert "lidar_z" not in sql


def test_database_inserts_relative_image_paths_without_removed_columns():
    cursor = FakeCursor()
    database = DatabaseHarness(cursor)

    event_id = database.insert_event(
        event_source="VISION_AI",
        event_type="ASSAULT",
        image_path="received_frames/gallery/events/event-1.jpg",
        confidence=0.91,
        lidar_x=1.5,
        lidar_y=2.5,
    )
    action_id = database.insert_action(
        user_id=3,
        event_id=event_id,
        action_type="NOTE",
        description="현장 확인",
        image_path="received_frames/gallery/actions/action-1.jpg",
    )

    assert event_id == 41
    assert action_id == 41
    event_sql, event_params = cursor.executions[0]
    assert "INSERT INTO event_log" in event_sql
    assert "image_path" in event_sql
    assert "video_path" not in event_sql
    assert "lidar_z" not in event_sql
    assert event_params == (
        "VISION_AI",
        "ASSAULT",
        "received_frames/gallery/events/event-1.jpg",
        0.91,
        None,
        None,
        None,
        1.5,
        2.5,
    )
    action_sql, action_params = cursor.executions[1]
    assert "INSERT INTO action_log" in action_sql
    assert "image_path" in action_sql
    assert action_params == (
        3,
        41,
        "NOTE",
        "현장 확인",
        "received_frames/gallery/actions/action-1.jpg",
    )


def test_database_rejects_absolute_or_escaping_image_paths():
    cursor = FakeCursor()
    database = DatabaseHarness(cursor)

    invalid_paths = (
        "C:\\private\\event.jpg",
        "/private/event.jpg",
        "received_frames/gallery/../raw.jpg",
        "",
    )
    for image_path in invalid_paths:
        try:
            database.insert_event(
                event_source="VISION_AI",
                event_type="ASSAULT",
                image_path=image_path,
            )
        except ValueError as exc:
            assert "relative path" in str(exc)
        else:
            raise AssertionError(f"unsafe image path was accepted: {image_path}")
    assert cursor.executions == []


def test_database_reads_latest_first_with_time_and_limit_binding():
    expected = [{"event_id": 2}, {"event_id": 1}]
    cursor = FakeCursor(expected)
    database = DatabaseHarness(cursor)
    start = datetime(2026, 8, 1)
    end = datetime(2026, 8, 14)
    assert database.list_events(start_at=start, end_at=end, limit=25) == expected
    sql, params = cursor.executions[0]
    assert "is_deleted = 0" in sql
    assert "ORDER BY detected_at DESC LIMIT %s" in sql
    assert "image_path" in sql
    assert "video_path" not in sql
    assert "lidar_z" not in sql
    assert params == (start, end, 25)


def test_database_lists_system_status_and_actions_with_dashboard_fields():
    cursor = FakeCursor([])
    database = DatabaseHarness(cursor)

    database.list_system_status(limit=10)
    status_sql, status_params = cursor.executions[0]
    assert "lidar_x" in status_sql and "lidar_y" in status_sql
    assert "lidar_z" not in status_sql
    assert status_params == (10,)

    database.list_actions(limit=15)
    action_sql, action_params = cursor.executions[1]
    assert "u.name AS user_name" in action_sql
    assert "a.image_path" in action_sql
    assert "a.is_deleted = 0" in action_sql
    assert "ORDER BY a.created_at DESC LIMIT %s" in action_sql
    assert action_params == (15,)


def test_database_lists_gallery_images_from_events_and_actions():
    expected = [
        {
            "source": "event",
            "record_id": 9,
            "image_path": "received_frames/gallery/events/event-9.jpg",
        },
        {
            "source": "action",
            "record_id": 4,
            "image_path": "received_frames/gallery/actions/action-4.jpg",
        },
    ]
    cursor = FakeCursor(expected)
    database = DatabaseHarness(cursor)
    start = datetime(2026, 8, 1)
    end = datetime(2026, 8, 23)

    assert database.list_gallery(
        source="all", start_at=start, end_at=end, limit=12
    ) == expected
    sql, params = cursor.executions[0]
    assert "'event' AS source" in sql
    assert "'action' AS source" in sql
    assert "UNION ALL" in sql
    assert sql.count("image_path IS NOT NULL") == 2
    assert "ORDER BY recorded_at DESC LIMIT %s" in sql
    assert "video_path" not in sql
    assert "lidar_z" not in sql
    assert params == (start, end, start, end, 12)


def test_database_filters_gallery_source_and_rejects_unknown_source():
    cursor = FakeCursor([])
    database = DatabaseHarness(cursor)

    database.list_gallery(source="event", limit=5)
    event_sql, event_params = cursor.executions[0]
    assert "FROM event_log AS e" in event_sql
    assert "FROM action_log AS a" not in event_sql
    assert event_params == (5,)

    try:
        database.list_gallery(source="unknown")
    except ValueError as exc:
        assert "all, event, action" in str(exc)
    else:
        raise AssertionError("unknown gallery source was accepted")


def test_database_gets_event_and_action_image_paths_by_bound_id():
    event_cursor = FakeCursor(
        [{"image_path": "received_frames/gallery/events/event-7.jpg"}]
    )
    event_database = DatabaseHarness(event_cursor)
    assert event_database.get_event_image_path(7) == (
        "received_frames/gallery/events/event-7.jpg"
    )
    event_sql, event_params = event_cursor.executions[0]
    assert "FROM event_log" in event_sql
    assert "event_id = %s" in event_sql
    assert "is_deleted = 0" in event_sql
    assert event_params == (7,)

    action_cursor = FakeCursor(
        [{"image_path": "received_frames/gallery/actions/action-8.jpg"}]
    )
    action_database = DatabaseHarness(action_cursor)
    assert action_database.get_action_image_path(8) == (
        "received_frames/gallery/actions/action-8.jpg"
    )
    action_sql, action_params = action_cursor.executions[0]
    assert "FROM action_log" in action_sql
    assert "action_id = %s" in action_sql
    assert action_params == (8,)


def test_dashboard_records_schema_and_forward_migration_match_contract():
    repository_root = Path(__file__).resolve().parents[1]
    schema = (repository_root / "data/database/init_schema.sql").read_text(
        encoding="utf-8"
    )
    migration = (
        repository_root
        / "data/database/migrations/20260823_dashboard_records.sql"
    ).read_text(encoding="utf-8")

    assert schema.count("`image_path` varchar(255) DEFAULT NULL") == 2
    assert "`is_false_alarm`" in schema
    assert "`video_path`" not in schema
    assert "`lidar_z`" not in schema
    assert "CHANGE COLUMN `video_path` `image_path`" in migration
    assert "ALTER TABLE `action_log`" in migration
    assert migration.count("DROP COLUMN `lidar_z`") == 2
    assert "DROP TABLE" not in migration
    assert "TRUNCATE" not in migration


def test_database_checks_reportable_event_with_bound_id():
    cursor = FakeCursor([{"exists": 1}])
    database = DatabaseHarness(cursor)
    assert database.event_exists(7) is True
    sql, params = cursor.executions[0]
    assert "event_id = %s" in sql
    assert "is_deleted = 0" in sql
    assert params == (7,)


class RecordingDatabase:
    def __init__(self):
        self.events = []
        self.statuses = []

    def insert_event(self, **values):
        self.events.append(values)
        return len(self.events)

    def insert_system_status(self, values):
        self.statuses.append(values)
        return len(self.statuses)


class RecordingNotifier:
    def __init__(self):
        self.events = []

    def send_event_alert_async(self, message, *, robot_id, event_type):
        self.events.append((robot_id, event_type, message))
        return True


class RaisingNotifier:
    def send_event_alert_async(self, *_args, **_kwargs):
        raise RuntimeError("sender failed")


class BlockingDatabase(RecordingDatabase):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def insert_event(self, **values):
        if not self.events:
            self.entered.set()
            assert self.release.wait(2)
        return super().insert_event(**values)


def test_event_worker_cooldown_is_per_robot_and_event_type():
    database = RecordingDatabase()
    notifier = RecordingNotifier()
    worker = EventLogWorker(database, notifier, cooldown_sec=10)
    now = [100.0]
    worker.gate.clock = lambda: now[0]
    worker.start()
    try:
        assert worker.submit(
            robot_id="robot-1",
            event_source="VISION_AI",
            event_type="ASSAULT",
            confidence=0.9,
        )
        assert not worker.submit(
            robot_id="robot-1",
            event_source="VISION_AI",
            event_type="ASSAULT",
            confidence=0.8,
        )
        assert worker.submit(
            robot_id="robot-1",
            event_source="SYSTEM_MONITOR",
            event_type="NETWORK_LOSS",
        )
        assert worker.submit(
            robot_id="robot-2",
            event_source="VISION_AI",
            event_type="ASSAULT",
        )
        worker.queue.join()
        assert len(database.events) == 3
        now[0] += 10
        assert worker.submit(
            robot_id="robot-1",
            event_source="VISION_AI",
            event_type="ASSAULT",
        )
        worker.queue.join()
        assert len(database.events) == 4
    finally:
        worker.stop()


def test_event_worker_stops_after_a_full_queue_drains():
    database = BlockingDatabase()
    worker = EventLogWorker(
        database,
        RecordingNotifier(),
        cooldown_sec=0,
        queue_size=1,
    )
    worker.start()
    assert worker.submit(
        robot_id="robot-1",
        event_source="VISION_AI",
        event_type="ASSAULT",
    )
    assert database.entered.wait(1)
    assert worker.submit(
        robot_id="robot-1",
        event_source="SYSTEM_MONITOR",
        event_type="SYSTEM_ERROR",
    )
    stopped = threading.Event()

    def stop_worker():
        worker.stop(timeout_sec=2)
        stopped.set()

    stopper = threading.Thread(target=stop_worker)
    stopper.start()
    time.sleep(0.05)
    database.release.set()
    stopper.join(2)
    assert stopped.is_set()
    assert worker.thread is None
    assert len(database.events) == 2


def test_event_worker_survives_notifier_exception():
    database = RecordingDatabase()
    worker = EventLogWorker(database, RaisingNotifier(), cooldown_sec=0)
    worker.start()
    try:
        assert worker.submit(
            robot_id="robot-1",
            event_source="VISION_AI",
            event_type="ASSAULT",
        )
        assert worker.submit(
            robot_id="robot-1",
            event_source="SYSTEM_MONITOR",
            event_type="SYSTEM_ERROR",
        )
        worker.queue.join()
        assert len(database.events) == 2
        assert worker.thread is not None and worker.thread.is_alive()
    finally:
        worker.stop()


def test_status_writer_skips_unreceived_status_and_preserves_missing_values_as_null():
    database = RecordingDatabase()
    state = {"updated_at": None}
    writer = SystemStatusWriter(database, lambda: state)
    assert writer.write_once() is False
    state.update(
        {
            "updated_at": 1.0,
            "cpu_usage": "12.5",
            "cpu_temp": None,
            "ram_usage": "bad",
            "battery": "76",
            "mode": "manual",
        }
    )
    assert writer.write_once() is True
    saved = database.statuses[0]
    assert saved["cpu_usage"] == 12.5
    assert saved["cpu_temperature"] is None
    assert saved["ram_usage"] is None
    assert saved["ping"] is None
    assert saved["battery_level"] == 76
    assert saved["is_autonomous"] == 0


def test_status_writer_stops_its_background_thread_cleanly():
    database = RecordingDatabase()
    writer = SystemStatusWriter(
        database,
        lambda: {"updated_at": 1.0, "mode": "auto"},
        interval_sec=0.1,
    )
    writer.start()
    time.sleep(0.15)
    writer.stop(timeout_sec=1)
    assert writer.thread is None
    assert database.statuses
