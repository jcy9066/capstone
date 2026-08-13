from __future__ import annotations

import json
import re
import sys
from typing import Any


MUTATING_GIT_SUBCOMMANDS = frozenset(
    {
        "add",
        "am",
        "apply",
        "bisect",
        "checkout",
        "cherry-pick",
        "clean",
        "clone",
        "commit",
        "fetch",
        "init",
        "merge",
        "mv",
        "pull",
        "push",
        "rebase",
        "reset",
        "restore",
        "revert",
        "rm",
        "stash",
        "switch",
        "tag",
        "worktree",
    }
)

MUTATING_GITHUB_TOOL_SUFFIXES = frozenset(
    {
        "create_blob",
        "create_branch",
        "create_commit",
        "create_file",
        "create_tree",
        "delete_file",
        "merge_pull_request",
        "update_file",
        "update_ref",
    }
)

_GIT_COMMAND_RE = re.compile(
    r"(?ix)"
    r"(?:^|[\r\n;&|]\s*)"
    r"git"
    r"(?:\s+-C\s+(?:\"[^\"]*\"|'[^']*'|\S+))*"
    r"(?:\s+--(?:git-dir|work-tree)(?:=|\s+)(?:\"[^\"]*\"|'[^']*'|\S+))*"
    r"\s+([a-z][a-z0-9-]*)\b"
)


def _read_payload() -> dict[str, Any]:
    """Codex hook payload를 읽는다. 단독 실행/빈 stdin도 정상 허용한다."""
    try:
        if sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
    except Exception:
        return {}

    if not raw.strip():
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}


def _first_value(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _tool_name(payload: dict[str, Any]) -> str:
    value = _first_value(
        payload,
        "tool_name",
        "toolName",
        "tool",
        "name",
    )
    return str(value or "").strip()


def _tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = _first_value(
        payload,
        "tool_input",
        "toolInput",
        "input",
        "arguments",
        "args",
    )

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        return {"command": value}

    return {}


def _extract_command(tool_input: dict[str, Any]) -> str:
    for key in ("command", "cmd", "script", "code", "input"):
        value = tool_input.get(key)

        if isinstance(value, str) and value.strip():
            return value

        if isinstance(value, list):
            parts = [str(part) for part in value if part is not None]
            if parts:
                return " ".join(parts)

    argv = tool_input.get("argv")
    if isinstance(argv, list):
        return " ".join(str(part) for part in argv)

    return ""


def _github_tool_is_mutating(tool_name: str) -> tuple[bool, str]:
    normalized = tool_name.strip().lower()

    for suffix in MUTATING_GITHUB_TOOL_SUFFIXES:
        if (
            normalized.endswith("." + suffix)
            or normalized.endswith("__" + suffix)
            or normalized == suffix
        ):
            return True, suffix

    return False, ""


def _git_command_is_mutating(command: str) -> tuple[bool, str]:
    if not command:
        return False, ""

    for match in _GIT_COMMAND_RE.finditer(command):
        subcommand = match.group(1).lower()

        if subcommand in MUTATING_GIT_SUBCOMMANDS:
            return True, subcommand

    branch_re = re.compile(
        r"(?ix)"
        r"(?:^|[\r\n;&|]\s*)"
        r"git"
        r"(?:\s+-C\s+(?:\"[^\"]*\"|'[^']*'|\S+))*"
        r"\s+branch\b([^\r\n;&|]*)"
    )

    for match in branch_re.finditer(command):
        tail = match.group(1).strip()

        if not tail:
            continue

        read_only_patterns = (
            r"^(?:--list|-l)(?:\s|$)",
            r"^--show-current(?:\s|$)",
            r"^(?:-a|--all)(?:\s|$)",
            r"^(?:-r|--remotes)(?:\s|$)",
            r"^(?:-v|-vv)(?:\s|$)",
            r"^--contains(?:\s|$)",
            r"^--merged(?:\s|$)",
            r"^--no-merged(?:\s|$)",
        )

        if any(
            re.search(pattern, tail, flags=re.IGNORECASE)
            for pattern in read_only_patterns
        ):
            continue

        return True, "branch"

    return False, ""


def _decision(
    permission: str,
    reason: str | None = None,
) -> dict[str, Any]:
    specific: dict[str, Any] = {
        "hookEventName": "PreToolUse",
        "permissionDecision": permission,
    }

    if reason:
        specific["permissionDecisionReason"] = reason
        specific["additionalContext"] = reason

    return {"hookSpecificOutput": specific}


def main() -> int:
    payload = _read_payload()
    tool_name = _tool_name(payload)
    tool_input = _tool_input(payload)

    github_blocked, github_action = _github_tool_is_mutating(tool_name)

    if github_blocked:
        reason = (
            "이 프로젝트에서는 Codex가 Git/GitHub repository 상태를 "
            f"변경하지 않습니다. 차단된 GitHub 작업: {github_action}. "
            "branch/add/commit/push/pull/merge 및 repository file/ref 변경은 "
            "사용자가 직접 수행합니다."
        )
        print(json.dumps(_decision("deny", reason), ensure_ascii=False))
        return 0

    command = _extract_command(tool_input)
    git_blocked, git_action = _git_command_is_mutating(command)

    if git_blocked:
        reason = (
            "이 프로젝트에서는 Codex가 Git 상태를 변경하지 않습니다. "
            f"차단된 Git 작업: git {git_action}. "
            "Git 상태 변경은 사용자가 직접 수행합니다."
        )
        print(json.dumps(_decision("deny", reason), ensure_ascii=False))
        return 0

    print(json.dumps(_decision("allow"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
