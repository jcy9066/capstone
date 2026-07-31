"""Environment-configured MySQL access used by the authentication service."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ModuleNotFoundError:  # Keep non-auth server features bootable until dependencies are installed.
    pymysql = None
    DictCursor = None


class DatabaseConfigurationError(RuntimeError):
    """Raised when the server cannot safely connect to the configured database."""


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
            port = int(os.getenv("DB_PORT", "3306"))
            timeout = int(os.getenv("DB_CONNECT_TIMEOUT_SEC", "5"))
        except ValueError as exc:
            raise DatabaseConfigurationError("Database port or timeout is invalid.") from exc
        return cls(
            host=os.getenv("DB_HOST", "").strip(),
            port=port,
            name=os.getenv("DB_NAME", "dabom").strip(),
            user=os.getenv("DB_USER", "").strip(),
            password=os.getenv("DB_PASSWORD", ""),
            connect_timeout_sec=max(1, timeout),
        )

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
