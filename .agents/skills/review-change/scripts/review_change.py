#!/usr/bin/env python3
"""Review repository changes without modifying Git state.

This script never runs git add, commit, push, pull, merge, checkout,
switch, reset, restore, rebase or tag.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

VALIDATORS = {
    "server": Path(
        ".agents/skills/"
        "validate-server/"
        "scripts/"
        "validate_server.py"
    ),
    "navigation": Path(
        ".agents/skills/"
        "validate-navigation/"
        "scripts/"
        "validate_navigation.py"
    ),
    "raspberry": Path(
        ".agents/skills/"
        "validate-raspberry/"
        "scripts/"
        "validate_uart_protocol.py"
    ),
}

GENERATED_PREFIXES = (
    "build/",
    "install/",
    "log/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
)

BACKUP_PATTERNS = (
    re.compile(
        r"(?:^|/)[^/]+\.bak(?:$|[._-])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|/)[^/]+\.backup(?:$|[._-])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|/)[^/]+~$"
    ),
    re.compile(
        r"(?:^|/)[^/]+\.tmp$",
        re.IGNORECASE,
    ),
)

CONFLICT_PATTERN = re.compile(
    (
        r"^(?:"
        r"<<<<<<<"
        r"|======="
        r"|>>>>>>>"
        r")(?: .*)?$"
    ),
    re.MULTILINE,
)

SECRET_PATTERNS = {
    "GitHub token": re.compile(
        (
            r"\b(?:ghp|github_pat)_"
            r"[A-Za-z0-9_]{20,}\b"
        )
    ),
    "private key": re.compile(
        (
            r"-----BEGIN "
            r"(?:RSA |EC |OPENSSH )?"
            r"PRIVATE KEY-----"
        )
    ),
    "AWS access key": re.compile(
        r"\bAKIA[0-9A-Z]{16}\b"
    ),
    "generic secret": re.compile(
        (
            r"(?i)\b(?:"
            r"password"
            r"|passwd"
            r"|secret"
            r"|api[_-]?key"
            r"|access[_-]?token"
            r")"
            r"\s*[:=]\s*"
            r"[\"']?"
            r"([A-Za-z0-9_./+=-]{12,})"
        )
    ),
}

SECRET_SCAN_EXCEPTIONS = {
    ".env.example",
    "README.md",
    "PROJECT.md",
}

TEXT_SUFFIXES = {
    ".py",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".js",
    ".mjs",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".json",
    ".toml",
    ".xml",
    ".yaml",
    ".yml",
    ".md",
    ".sh",
    ".service",
    ".sql",
    ".txt",
}

DASHBOARD_PREFIXES = (
    "frontend/",
    "dashboard/",
    "server/static/",
    "server/templates/",
)

SERVER_PREFIXES = (
    "server/",
    "tests/",
)

NAVIGATION_PREFIXES = (
    "navigation/",
)

RASPBERRY_PREFIXES = (
    "raspberry/",
)

TEST_PREFIXES = (
    "tests/",
    "test/",
)


class Report:
    def __init__(
        self,
        root: Path,
    ) -> None:
        self.root = root
        self.items: list[
            dict[str, Any]
        ] = []
        self.commands: list[
            dict[str, Any]
        ] = []
        self.changed_files: list[str] = []
        self.validators: list[str] = []

    def add(
        self,
        severity: str,
        code: str,
        message: str,
        path: str | Path | None = None,
        line: int | None = None,
    ) -> None:
        if isinstance(
            path,
            Path,
        ):
            try:
                path = (
                    path.resolve()
                    .relative_to(
                        self.root
                    )
                    .as_posix()
                )

            except ValueError:
                path = path.as_posix()

        self.items.append(
            {
                "severity": severity,
                "code": code,
                "message": message,
                "path": path,
                "line": line,
            }
        )

    def error(
        self,
        code: str,
        message: str,
        path=None,
        line=None,
    ) -> None:
        self.add(
            "ERROR",
            code,
            message,
            path,
            line,
        )

    def warn(
        self,
        code: str,
        message: str,
        path=None,
        line=None,
    ) -> None:
        self.add(
            "WARN",
            code,
            message,
            path,
            line,
        )

    def passed(
        self,
        code: str,
        message: str,
    ) -> None:
        self.add(
            "PASS",
            code,
            message,
        )

    def skipped(
        self,
        code: str,
        message: str,
    ) -> None:
        self.add(
            "SKIP",
            code,
            message,
        )

    @property
    def errors(self) -> int:
        return sum(
            item["severity"]
            == "ERROR"
            for item in self.items
        )

    @property
    def warnings(self) -> int:
        return sum(
            item["severity"]
            == "WARN"
            for item in self.items
        )


def find_root(
    explicit: Path | None,
) -> Path:
    starts = (
        [explicit.resolve()]
        if explicit
        else [
            Path.cwd(),
            Path(__file__).resolve().parent,
        ]
    )

    for start in starts:
        for candidate in (
            start,
            *start.parents,
        ):
            if (
                (
                    candidate
                    / ".git"
                ).exists()
                and (
                    candidate
                    / "AGENTS.md"
                ).is_file()
            ):
                return candidate.resolve()

    raise RuntimeError(
        "dabom_capstone Git 저장소 "
        "루트를 찾지 못했습니다."
    )


def run(
    report: Report,
    name: str,
    command: list[str],
    cwd: Path,
    timeout: int,
    show_output: bool,
) -> int:
    started = time.monotonic()

    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=os.environ.copy(),
        )

        returncode = (
            process.returncode
        )

        stdout = process.stdout
        stderr = process.stderr

    except FileNotFoundError as exc:
        returncode = 127
        stdout = ""
        stderr = str(exc)

    except subprocess.TimeoutExpired as exc:
        returncode = 124

        stdout = (
            exc.stdout
            if isinstance(
                exc.stdout,
                str,
            )
            else ""
        )

        stderr = (
            (
                exc.stderr
                if isinstance(
                    exc.stderr,
                    str,
                )
                else ""
            )
            + (
                "\ncommand timed out "
                f"after {timeout}s"
            )
        ).strip()

    report.commands.append(
        {
            "name": name,
            "returncode": returncode,
            "duration_sec": (
                time.monotonic()
                - started
            ),
            "stdout": stdout,
            "stderr": stderr,
        }
    )

    if show_output:
        print(
            f"\n[COMMAND] {name}"
        )

        print(
            " ".join(command)
        )

        if stdout.strip():
            print(
                stdout.rstrip()
            )

        if stderr.strip():
            print(
                stderr.rstrip(),
                file=sys.stderr,
            )

    return returncode


def git_read(
    report: Report,
    name: str,
    arguments: list[str],
    root: Path,
    timeout: int = 30,
) -> str | None:
    started = time.monotonic()

    try:
        process = subprocess.run(
            [
                "git",
                *arguments,
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=os.environ.copy(),
        )

    except (
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ) as exc:
        report.error(
            "git-read",
            f"{name} 실패: {exc}",
        )

        return None

    report.commands.append(
        {
            "name": name,
            "returncode": (
                process.returncode
            ),
            "duration_sec": (
                time.monotonic()
                - started
            ),
            "stdout": (
                process.stdout
            ),
            "stderr": (
                process.stderr
            ),
        }
    )

    if process.returncode != 0:
        report.error(
            "git-read",
            (
                f"{name} 실패: "
                f"{process.stderr.strip()[:1000]}"
            ),
        )

        return None

    return process.stdout


def parse_name_status(
    payload: str,
) -> set[str]:
    tokens = payload.split(
        "\0"
    )

    paths: set[str] = set()
    index = 0

    while index < len(tokens):
        status = tokens[index]
        index += 1

        if not status:
            continue

        if status[0] in {
            "R",
            "C",
        }:
            if (
                index + 1
                >= len(tokens)
            ):
                break

            old_path = tokens[index]
            new_path = tokens[
                index + 1
            ]

            index += 2

            if old_path:
                paths.add(
                    old_path
                )

            if new_path:
                paths.add(
                    new_path
                )

        else:
            if index >= len(tokens):
                break

            path = tokens[index]
            index += 1

            if path:
                paths.add(path)

    return paths


def discover_changes(
    root: Path,
    args: argparse.Namespace,
    report: Report,
) -> list[str]:
    files: set[str] = set()

    if args.base:
        revision = (
            (
                f"{args.base}..."
                f"{args.head}"
            )
            if args.head
            else (
                f"{args.base}..."
                "HEAD"
            )
        )

        output = git_read(
            report,
            "git-diff-range",
            [
                "diff",
                "--name-status",
                "-z",
                (
                    "--diff-filter="
                    "ACDMRTUXB"
                ),
                revision,
            ],
            root,
        )

        if output is not None:
            files.update(
                parse_name_status(
                    output
                )
            )

    else:
        commands = (
            (
                "git-diff-working",
                [
                    "diff",
                    "--name-status",
                    "-z",
                    (
                        "--diff-filter="
                        "ACDMRTUXB"
                    ),
                ],
            ),
            (
                "git-diff-staged",
                [
                    "diff",
                    "--cached",
                    "--name-status",
                    "-z",
                    (
                        "--diff-filter="
                        "ACDMRTUXB"
                    ),
                ],
            ),
        )

        for (
            name,
            command,
        ) in commands:
            output = git_read(
                report,
                name,
                command,
                root,
            )

            if output is not None:
                files.update(
                    parse_name_status(
                        output
                    )
                )

        untracked = git_read(
            report,
            "git-untracked",
            [
                "ls-files",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            root,
        )

        if untracked is not None:
            files.update(
                item
                for item in untracked.split(
                    "\0"
                )
                if item
            )

    normalized = sorted(
        Path(path)
        .as_posix()
        .lstrip("./")
        for path in files
        if path.strip()
    )

    report.changed_files = (
        normalized
    )

    if normalized:
        report.passed(
            "changed-files",
            (
                f"변경 파일 "
                f"{len(normalized)}개를 "
                "확인했습니다."
            ),
        )

    else:
        report.skipped(
            "changed-files",
            (
                "검토할 Git 변경 사항이 "
                "없습니다."
            ),
        )

    return normalized


def read_diff(
    root: Path,
    args: argparse.Namespace,
    report: Report,
) -> str:
    if args.base:
        revision = (
            (
                f"{args.base}..."
                f"{args.head}"
            )
            if args.head
            else (
                f"{args.base}..."
                "HEAD"
            )
        )

        return (
            git_read(
                report,
                "git-diff-content",
                [
                    "diff",
                    "--no-ext-diff",
                    "--unified=0",
                    revision,
                ],
                root,
            )
            or ""
        )

    working = (
        git_read(
            report,
            "git-diff-content",
            [
                "diff",
                "--no-ext-diff",
                "--unified=0",
            ],
            root,
        )
        or ""
    )

    staged = (
        git_read(
            report,
            "git-diff-content-staged",
            [
                "diff",
                "--cached",
                "--no-ext-diff",
                "--unified=0",
            ],
            root,
        )
        or ""
    )

    return (
        working
        + "\n"
        + staged
    )


def is_text_file(
    path: Path,
) -> bool:
    return (
        path.suffix.lower()
        in TEXT_SUFFIXES
        or path.name
        in {
            ".env",
            ".env.example",
            ".gitignore",
            "Dockerfile",
            "CMakeLists.txt",
        }
    )


def read_text(
    path: Path,
) -> str | None:
    try:
        return path.read_text(
            encoding="utf-8"
        )

    except (
        OSError,
        UnicodeError,
    ):
        return None


def hygiene_checks(
    root: Path,
    changed: list[str],
    report: Report,
) -> None:
    for relative in changed:
        lower = relative.lower()

        if lower.startswith(
            GENERATED_PREFIXES
        ):
            report.error(
                "generated-artifact",
                (
                    "build/install/log/cache "
                    "산출물을 Git 변경에 "
                    "포함하면 안 됩니다."
                ),
                relative,
            )

        if (
            "/__pycache__/"
            in f"/{lower}/"
            or lower.endswith(".pyc")
        ):
            report.error(
                "cache-file",
                (
                    "Python cache 파일을 "
                    "Git 변경에 포함하면 "
                    "안 됩니다."
                ),
                relative,
            )

        if any(
            pattern.search(relative)
            for pattern in BACKUP_PATTERNS
        ):
            report.error(
                "backup-file",
                (
                    "backup 또는 임시 파일을 "
                    "Git 변경에 포함하면 "
                    "안 됩니다."
                ),
                relative,
            )

        if (
            Path(relative).name.startswith(
                ".env"
            )
            and relative
            != ".env.example"
        ):
            report.error(
                "environment-secret-file",
                (
                    "실제 환경 변수 파일을 "
                    "Git 변경에 포함하면 "
                    "안 됩니다."
                ),
                relative,
            )

        path = (
            root
            / relative
        )

        if (
            path.is_file()
            and path.stat().st_size
            > 5 * 1024 * 1024
        ):
            report.warn(
                "large-file",
                (
                    "변경 파일 크기가 "
                    "5MiB를 초과합니다: "
                    f"{path.stat().st_size} bytes"
                ),
                relative,
            )


def content_checks(
    root: Path,
    changed: list[str],
    diff_text: str,
    report: Report,
) -> None:
    conflict_found = False
    secret_found = False

    for relative in changed:
        path = (
            root
            / relative
        )

        if (
            not path.is_file()
            or not is_text_file(path)
        ):
            continue

        source = read_text(path)

        if source is None:
            report.warn(
                "text-read",
                (
                    "UTF-8 텍스트로 "
                    "읽을 수 없습니다."
                ),
                relative,
            )

            continue

        for match in (
            CONFLICT_PATTERN.finditer(
                source
            )
        ):
            conflict_found = True

            line = (
                source.count(
                    "\n",
                    0,
                    match.start(),
                )
                + 1
            )

            report.error(
                "merge-conflict",
                (
                    "해결되지 않은 Git "
                    "conflict marker가 "
                    "있습니다."
                ),
                relative,
                line,
            )

        if (
            relative
            in SECRET_SCAN_EXCEPTIONS
        ):
            continue

        for (
            label,
            pattern,
        ) in SECRET_PATTERNS.items():
            match = pattern.search(
                source
            )

            if match is None:
                continue

            secret_found = True

            line = (
                source.count(
                    "\n",
                    0,
                    match.start(),
                )
                + 1
            )

            report.error(
                "secret-exposure",
                (
                    f"{label}로 보이는 "
                    "값이 포함되어 있습니다."
                ),
                relative,
                line,
            )

    added_lines = "\n".join(
        line[1:]
        for line in diff_text.splitlines()
        if (
            line.startswith("+")
            and not line.startswith(
                "+++"
            )
        )
    )

    for (
        label,
        pattern,
    ) in SECRET_PATTERNS.items():
        if pattern.search(
            added_lines
        ):
            secret_found = True

            report.error(
                "secret-added",
                (
                    "추가된 diff에 "
                    f"{label}로 보이는 "
                    "값이 있습니다."
                ),
            )

    if not conflict_found:
        report.passed(
            "merge-conflict",
            (
                "Git conflict marker가 "
                "없습니다."
            ),
        )

    if not secret_found:
        report.passed(
            "secret-exposure",
            (
                "변경 파일에서 명확한 "
                "secret 노출을 찾지 "
                "못했습니다."
            ),
        )


def syntax_checks(
    root: Path,
    changed: list[str],
    report: Report,
) -> None:
    try:
        import yaml  # type: ignore

    except ImportError:
        yaml = None

    checked = 0

    for relative in changed:
        path = (
            root
            / relative
        )

        if not path.is_file():
            continue

        suffix = (
            path.suffix.lower()
        )

        try:
            if suffix == ".py":
                ast.parse(
                    path.read_text(
                        encoding="utf-8"
                    ),
                    filename=str(path),
                )

                checked += 1

            elif suffix == ".json":
                json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )

                checked += 1

            elif suffix == ".toml":
                tomllib.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )

                checked += 1

            elif (
                suffix == ".xml"
                or path.name
                == "package.xml"
            ):
                ET.parse(path)
                checked += 1

            elif suffix in {
                ".yaml",
                ".yml",
            }:
                if yaml is None:
                    report.warn(
                        "yaml-parser",
                        (
                            "PyYAML이 없어 "
                            "YAML 구문 검사를 "
                            "생략합니다."
                        ),
                        relative,
                    )

                else:
                    yaml.safe_load(
                        path.read_text(
                            encoding="utf-8"
                        )
                    )

                    checked += 1

        except (
            SyntaxError,
            UnicodeError,
            OSError,
            ValueError,
            json.JSONDecodeError,
            tomllib.TOMLDecodeError,
            ET.ParseError,
        ) as exc:
            report.error(
                "syntax",
                str(exc),
                relative,
                getattr(
                    exc,
                    "lineno",
                    None,
                ),
            )

        except Exception as exc:
            if (
                yaml is not None
                and isinstance(
                    exc,
                    yaml.YAMLError,
                )
            ):
                report.error(
                    "syntax",
                    str(exc),
                    relative,
                )

            else:
                raise

    if checked:
        report.passed(
            "syntax",
            (
                "변경된 구조화 파일 "
                f"{checked}개의 "
                "구문이 유효합니다."
            ),
        )


def safety_checks(
    diff_text: str,
    report: Report,
) -> None:
    added_lines = [
        line[1:]
        for line in diff_text.splitlines()
        if (
            line.startswith("+")
            and not line.startswith(
                "+++"
            )
        )
    ]

    patterns = {
        "motor-output-enabled": re.compile(
            (
                r"\b(?:self\.)?"
                r"motor_output_enabled"
                r"\s*=\s*True\b"
            )
        ),
        "server-motor-enabled": re.compile(
            (
                r"\bMOTOR_OUTPUT_ENABLED"
                r"\s*=\s*"
                r"(?:1|true|True)\b"
            )
        ),
        "secret-log": re.compile(
            (
                r"(?i)\bprint\s*\("
                r"[^)]*"
                r"(?:"
                r"token"
                r"|password"
                r"|secret"
                r"|api[_-]?key"
                r")"
            )
        ),
    }

    unsafe_found = False

    for (
        code,
        pattern,
    ) in patterns.items():
        matches = [
            line.strip()
            for line in added_lines
            if pattern.search(line)
        ]

        if matches:
            unsafe_found = True

            report.error(
                code,
                (
                    "안전 설정을 활성화하는 "
                    "변경이 추가되었습니다: "
                    + " | ".join(
                        matches[:5]
                    )
                ),
            )

    live_cmd_vel = any(
        (
            re.search(
                (
                    r"(?:cmd_vel|"
                    r"cmd_vel_smoothed)"
                    r".{0,80}"
                    r"[\"']/cmd_vel[\"']"
                ),
                line,
            )
            is not None
        )
        and (
            "cmd_vel_nav_dry_run"
            not in line
        )
        for line in added_lines
    )

    if live_cmd_vel:
        unsafe_found = True

        report.error(
            "live-cmd-vel",
            (
                "Nav2 출력을 실제 /cmd_vel로 "
                "연결하는 변경 가능성이 "
                "있습니다."
            ),
        )

    if not unsafe_found:
        report.passed(
            "safety-diff",
            (
                "명확한 모터 출력 활성화, "
                "실제 /cmd_vel 연결 또는 "
                "secret logging 변경을 "
                "찾지 못했습니다."
            ),
        )


def test_change_check(
    changed: list[str],
    report: Report,
) -> None:
    source_changed = [
        path
        for path in changed
        if path.endswith(
            (
                ".py",
                ".js",
                ".ts",
                ".tsx",
                ".c",
                ".cpp",
            )
        )
        and not path.startswith(
            TEST_PREFIXES
        )
        and "/test"
        not in path.lower()
    ]

    test_changed = [
        path
        for path in changed
        if (
            path.startswith(
                TEST_PREFIXES
            )
            or "/tests/"
            in path
            or Path(path).name.startswith(
                "test_"
            )
        )
    ]

    if (
        source_changed
        and not test_changed
    ):
        report.warn(
            "tests-unchanged",
            (
                f"소스 파일 "
                f"{len(source_changed)}개가 "
                "변경됐지만 테스트 파일 "
                "변경은 없습니다. 기존 테스트 "
                "실행 결과를 확인해야 합니다."
            ),
        )

    elif (
        source_changed
        and test_changed
    ):
        report.passed(
            "tests-changed",
            (
                "소스 변경과 함께 테스트 파일 "
                f"{len(test_changed)}개가 "
                "변경되었습니다."
            ),
        )


def select_validators(
    changed: list[str],
) -> tuple[
    list[str],
    bool,
]:
    selected: list[str] = []

    server_changed = any(
        path.startswith(
            SERVER_PREFIXES
        )
        for path in changed
    )

    navigation_changed = any(
        path.startswith(
            NAVIGATION_PREFIXES
        )
        for path in changed
    )

    raspberry_changed = any(
        path.startswith(
            RASPBERRY_PREFIXES
        )
        for path in changed
    )

    dashboard_changed = any(
        path.startswith(
            DASHBOARD_PREFIXES
        )
        for path in changed
    )

    if server_changed:
        selected.append(
            "server"
        )

    if navigation_changed:
        selected.append(
            "navigation"
        )

    if raspberry_changed:
        selected.append(
            "raspberry"
        )

    return (
        selected,
        dashboard_changed,
    )


def run_validators(
    root: Path,
    selected: list[str],
    args: argparse.Namespace,
    report: Report,
) -> None:
    report.validators = selected

    if args.skip_validators:
        report.skipped(
            "validators",
            (
                "--skip-validators로 "
                "관련 Skill 검사를 "
                "생략했습니다."
            ),
        )

        return

    if not selected:
        report.skipped(
            "validators",
            (
                "변경 경로에 대응하는 "
                "Python validator가 "
                "없습니다."
            ),
        )

        return

    for name in selected:
        script = (
            root
            / VALIDATORS[name]
        )

        if not script.is_file():
            report.error(
                "validator-missing",
                (
                    f"{name} validator "
                    "파일이 없습니다."
                ),
                script,
            )

            continue

        command = [
            sys.executable,
            str(script),
        ]

        if args.show_command_output:
            if name == "server":
                command.append(
                    "--show-test-output"
                )

            else:
                command.append(
                    "--show-command-output"
                )

        result = run(
            report,
            f"validator:{name}",
            command,
            root,
            args.validator_timeout,
            args.show_command_output,
        )

        command_record = (
            report.commands[-1]
        )

        if result != 0:
            combined = (
                command_record["stdout"]
                + "\n"
                + command_record["stderr"]
            ).strip()

            report.error(
                "validator-failed",
                (
                    f"{name} validator 실패"
                    f"(returncode={result}).\n"
                    f"{combined[-6000:]}"
                ),
                script,
            )

        else:
            report.passed(
                "validator",
                (
                    f"{name} validator가 "
                    "통과했습니다."
                ),
            )


def dashboard_check(
    dashboard_changed: bool,
    args: argparse.Namespace,
    report: Report,
) -> None:
    if not dashboard_changed:
        return

    message = (
        "대시보드 관련 변경이 있습니다. "
        "Codex는 Playwright MCP로 로그인, "
        "주요 화면, browser console error, "
        "failed network request, 수동 주행 및 "
        "자율주행 제어 흐름을 별도로 "
        "검증해야 합니다."
    )

    if args.require_dashboard_validation:
        report.error(
            "dashboard-playwright-required",
            message,
        )

    else:
        report.warn(
            "dashboard-playwright-required",
            message,
        )


def print_report(
    report: Report,
    args: argparse.Namespace,
) -> None:
    if args.json:
        print(
            json.dumps(
                {
                    "ok": (
                        report.errors
                        == 0
                    ),
                    "root": str(
                        report.root
                    ),
                    "changed_files": (
                        report.changed_files
                    ),
                    "validators": (
                        report.validators
                    ),
                    "errors": (
                        report.errors
                    ),
                    "warnings": (
                        report.warnings
                    ),
                    "findings": (
                        report.items
                    ),
                    "commands": [
                        {
                            **item,
                            "stdout": (
                                item["stdout"][
                                    -8000:
                                ]
                            ),
                            "stderr": (
                                item["stderr"][
                                    -8000:
                                ]
                            ),
                        }
                        for item
                        in report.commands
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        return

    print(
        (
            "dabom change review: "
            f"{report.root}"
        )
    )

    print(
        "-" * 78
    )

    if report.changed_files:
        print(
            "changed files:"
        )

        for path in (
            report.changed_files
        ):
            print(
                f"  - {path}"
            )

        print(
            "-" * 78
        )

    order = {
        "ERROR": 0,
        "WARN": 1,
        "SKIP": 2,
        "PASS": 3,
    }

    for item in sorted(
        report.items,
        key=lambda value: (
            order.get(
                value["severity"],
                9,
            ),
            value["path"] or "",
            value["line"] or 0,
            value["code"],
        ),
    ):
        location = (
            f" {item['path']}"
            if item["path"]
            else ""
        )

        if item["line"]:
            location += (
                f":{item['line']}"
            )

        print(
            (
                f"[{item['severity']}] "
                f"{item['code']}:"
                f"{location} "
                f"{item['message']}"
            )
        )

    if (
        report.commands
        and not args.show_command_output
    ):
        print(
            "-" * 78
        )

        for item in report.commands:
            print(
                (
                    f"[COMMAND] "
                    f"{item['name']}: "
                    "returncode="
                    f"{item['returncode']}, "
                    "duration="
                    f"{item['duration_sec']:.2f}s"
                )
            )

    print(
        "-" * 78
    )

    print(
        (
            "summary: "
            f"files={len(report.changed_files)}, "
            f"errors={report.errors}, "
            f"warnings={report.warnings}, "
            "validators="
            f"{','.join(report.validators) or 'none'}"
        )
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=__doc__,
    )

    result.add_argument(
        "--root",
        type=Path,
    )

    result.add_argument(
        "--base",
    )

    result.add_argument(
        "--head",
    )

    result.add_argument(
        "--json",
        action="store_true",
    )

    result.add_argument(
        "--strict-warnings",
        action="store_true",
    )

    result.add_argument(
        "--show-command-output",
        action="store_true",
    )

    result.add_argument(
        "--skip-validators",
        action="store_true",
    )

    result.add_argument(
        "--validator-timeout",
        type=int,
        default=600,
    )

    result.add_argument(
        "--require-dashboard-validation",
        action="store_true",
    )

    return result


def main() -> int:
    args = parser().parse_args()

    if (
        args.head
        and not args.base
    ):
        print(
            (
                "ERROR: --head를 사용하려면 "
                "--base가 필요합니다."
            ),
            file=sys.stderr,
        )

        return 2

    try:
        root = find_root(
            args.root
        )

    except RuntimeError as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        return 2

    report = Report(root)

    changed = discover_changes(
        root,
        args,
        report,
    )

    if changed:
        diff_text = read_diff(
            root,
            args,
            report,
        )

        hygiene_checks(
            root,
            changed,
            report,
        )

        content_checks(
            root,
            changed,
            diff_text,
            report,
        )

        syntax_checks(
            root,
            changed,
            report,
        )

        safety_checks(
            diff_text,
            report,
        )

        test_change_check(
            changed,
            report,
        )

        (
            selected,
            dashboard_changed,
        ) = select_validators(
            changed
        )

        run_validators(
            root,
            selected,
            args,
            report,
        )

        dashboard_check(
            dashboard_changed,
            args,
            report,
        )

    print_report(
        report,
        args,
    )

    return (
        1
        if (
            report.errors
            or (
                args.strict_warnings
                and report.warnings
            )
        )
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())