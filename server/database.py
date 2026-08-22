"""Environment-configured MySQL access used by server services."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator

from server.env_config import EnvConfigurationError, env_int, env_text

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ModuleNotFoundError:  # Keep non-auth server features bootable until dependencies are installed.
    pymysql = None
    DictCursor = None


class DatabaseConfigurationError(RuntimeError):
    """Raised when the server cannot safely connect to the configured database."""


class DatabaseOperationError(RuntimeError):
    """Raised when a configured database operation cannot be completed."""


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str
    connect_timeout_sec: int

    @classmethod
    def from_environment(cls) -> "DatabaseConfig":
        try:
            return cls(
                host=env_text("DB_HOST"),
                port=env_int("DB_PORT", minimum=1, maximum=65535),
                name=env_text("DB_NAME"),
                user=env_text("DB_USER"),
                password=env_text("DB_PASSWORD"),
                connect_timeout_sec=env_int(
                    "DB_CONNECT_TIMEOUT_SEC", minimum=1
                ),
            )
        except EnvConfigurationError as exc:
            raise DatabaseConfigurationError("Database configuration is invalid.") from exc

    def validate(self) -> None:
        if not all((self.host, self.name, self.user, self.password)):
            raise DatabaseConfigurationError(
                "Database configuration is incomplete. Set DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD."
            )


class Database:
    def __init__(self, config: DatabaseConfig | None = None) -> None:
        self.config = config or DatabaseConfig.from_environment()

    def _connect(self):
        self.config.validate()
        if pymysql is None or DictCursor is None:
            raise DatabaseConfigurationError(
                "PyMySQL is unavailable. Install the project requirements before using authentication."
            )
        try:
            return pymysql.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.name,
                charset="utf8mb4",
                cursorclass=DictCursor,
                connect_timeout=self.config.connect_timeout_sec,
                read_timeout=self.config.connect_timeout_sec,
                write_timeout=self.config.connect_timeout_sec,
                autocommit=False,
            )
        except Exception as exc:
            raise DatabaseConfigurationError("Unable to connect to the configured database.") from exc

    @contextmanager
    def transaction(self) -> Iterator[object]:
        connection = self._connect()
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    def insert_system_status(self, values: dict[str, Any]) -> int:
        columns = (
            "cpu_usage",
            "cpu_temperature",
            "ram_usage",
            "ping",
            "battery_level",
            "is_autonomous",
            "speed",
            "gps_lat",
            "gps_lng",
            "gps_alt",
            "lidar_x",
            "lidar_y",
            "lidar_z",
        )
        sql = f"""
            INSERT INTO system_status ({", ".join(columns)})
            VALUES ({", ".join(["%s"] * len(columns))})
        """
        return self._insert(sql, tuple(values.get(column) for column in columns))

    def insert_event(
        self,
        *,
        event_source: str,
        event_type: str,
        confidence: float | None = None,
        gps_lat: float | None = None,
        gps_lng: float | None = None,
        gps_alt: float | None = None,
        lidar_x: float | None = None,
        lidar_y: float | None = None,
        lidar_z: float | None = None,
    ) -> int:
        return self._insert(
            """
            INSERT INTO event_log
                (event_source, event_type, video_path, confidence,
                 gps_lat, gps_lng, gps_alt, lidar_x, lidar_y, lidar_z)
            VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_source,
                event_type,
                confidence,
                gps_lat,
                gps_lng,
                gps_alt,
                lidar_x,
                lidar_y,
                lidar_z,
            ),
        )

    def insert_action(
        self,
        *,
        user_id: int,
        action_type: str,
        event_id: int | None = None,
        description: str | None = None,
    ) -> int:
        return self._insert(
            """
            INSERT INTO action_log
                (user_id, event_id, action_type, description_content)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, event_id, action_type, description),
        )

    def mark_event_reported(self, event_id: int) -> bool:
        try:
            with self.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE event_log
                        SET is_reported = 1, reported_at = CURRENT_TIMESTAMP
                        WHERE event_id = %s AND is_deleted = 0
                        """,
                        (event_id,),
                    )
                    return cursor.rowcount == 1
        except DatabaseConfigurationError:
            raise
        except Exception as exc:
            raise DatabaseOperationError("Unable to update the event log.") from exc

    def event_exists(self, event_id: int) -> bool:
        try:
            with self.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT 1 FROM event_log
                        WHERE event_id = %s AND is_deleted = 0
                        LIMIT 1
                        """,
                        (event_id,),
                    )
                    return cursor.fetchone() is not None
        except DatabaseConfigurationError:
            raise
        except Exception as exc:
            raise DatabaseOperationError("Unable to read the event log.") from exc

    def list_system_status(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._select_logs(
            table="system_status",
            timestamp_column="recorded_at",
            columns=(
                "status_id",
                "cpu_usage",
                "cpu_temperature",
                "ram_usage",
                "ping",
                "battery_level",
                "is_autonomous",
                "speed",
                "gps_lat",
                "gps_lng",
                "gps_alt",
                "lidar_x",
                "lidar_y",
                "lidar_z",
                "recorded_at",
            ),
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )

    def list_events(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._select_logs(
            table="event_log",
            timestamp_column="detected_at",
            columns=(
                "event_id",
                "event_source",
                "event_type",
                "video_path",
                "confidence",
                "gps_lat",
                "gps_lng",
                "gps_alt",
                "lidar_x",
                "lidar_y",
                "lidar_z",
                "is_resolved",
                "is_reported",
                "reported_at",
                "is_alerted",
                "is_mic_used",
                "is_false_alarm",
                "detected_at",
            ),
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            soft_delete=True,
        )

    def list_actions(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._select_logs(
            table="action_log",
            timestamp_column="created_at",
            columns=(
                "action_id",
                "user_id",
                "event_id",
                "action_type",
                "description_content",
                "created_at",
            ),
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            soft_delete=True,
        )

    def _insert(self, sql: str, params: tuple[Any, ...]) -> int:
        try:
            with self.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    return int(cursor.lastrowid)
        except DatabaseConfigurationError:
            raise
        except Exception as exc:
            raise DatabaseOperationError("Unable to write to the configured database.") from exc

    def _select_logs(
        self,
        *,
        table: str,
        timestamp_column: str,
        columns: tuple[str, ...],
        start_at: datetime | None,
        end_at: datetime | None,
        limit: int,
        soft_delete: bool = False,
    ) -> list[dict[str, Any]]:
        # Identifiers are selected only by the private callers above. All user
        # values remain bound parameters.
        conditions = ["is_deleted = 0"] if soft_delete else []
        params: list[Any] = []
        if start_at is not None:
            conditions.append(f"{timestamp_column} >= %s")
            params.append(start_at)
        if end_at is not None:
            conditions.append(f"{timestamp_column} <= %s")
            params.append(end_at)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            f"SELECT {', '.join(columns)} FROM {table}{where} "
            f"ORDER BY {timestamp_column} DESC LIMIT %s"
        )
        params.append(limit)
        try:
            with self.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, tuple(params))
                    return list(cursor.fetchall())
        except DatabaseConfigurationError:
            raise
        except Exception as exc:
            raise DatabaseOperationError("Unable to read from the configured database.") from exc
