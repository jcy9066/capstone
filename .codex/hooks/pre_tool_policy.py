from __future__ import annotations

import json
import re
import shlex
import sys
from typing import Any


MUTATING_GIT_SUBCOMMANDS = frozenset(
    {
        "am", "apply", "bisect", "checkout", "cherry-pick", "clean", "clone",
        "fetch", "init", "merge", "mv", "pull", "push", "rebase", "reset",
        "restore", "revert", "rm", "stash", "switch", "tag", "worktree",
    }
)

MUTATING_GITHUB_TOOL_SUFFIXES = frozenset(
    {
        "create_blob", "create_branch", "create_commit", "create_file",
        "create_tree", "delete_file", "merge_pull_request", "update_file",
        "update_ref",
    }
)

ALLOWED_COMMIT_TYPES = frozenset(
    {
        "feat", "fix", "docs", "style", "design", "test", "refactor",
        "build", "ci", "perf", "chore", "rename", "remove",
    }
)

# Accept both raw Git and RTK-wrapped Git so RTK cannot bypass Git policy.
_GIT_PREFIX = (
    r"(?:rtk(?:\.exe)?\s+)?git"
    r"(?:\s+-C\s+(?:\"[^\"]*\"|'[^']*'|\S+))*"
    r"(?:\s+--(?:git-dir|work-tree)(?:=|\s+)"
    r"(?:\"[^\"]*\"|'[^']*'|\S+))*"
)

_GIT_COMMAND_RE = re.compile(
    rf"(?ix)(?:^|[\r\n;&|]\s*){_GIT_PREFIX}\s+([a-z][a-z0-9-]*)\b"
)

_GIT_COMMIT_SEGMENT_RE = re.compile(
    rf"(?ix)(?:^|[\r\n;&|]\s*)({_GIT_PREFIX}\s+commit\b[^\r\n;&|]*)"
)

_SUBJECT_RE = re.compile(r"^(?P<type>[a-z]+): (?P<summary>.+)$")


def _read_payload() -> dict[str, Any]:
    try:
        if sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
    except Exception:
        return {}

    if not raw.strip():
        return {}

    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    return value if isinstance(value, dict) else {}


def _first_value(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _tool_name(payload: dict[str, Any]) -> str:
    return str(
        _first_value(payload, "tool_name", "toolName", "tool", "name") or ""
    ).strip()


def _tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = _first_value(
        payload, "tool_input", "toolInput", "input", "arguments", "args"
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


def _extract_commit_message(segment: str) -> tuple[str | None, str | None]:
    try:
        argv = shlex.split(segment, posix=True)
    except ValueError:
        return None, "commit command quoting is invalid"

    messages: list[str] = []
    index = 0

    while index < len(argv):
        token = argv[index]
        if token in ("-m", "--message"):
            if index + 1 >= len(argv):
                return None, "git commit message is missing"
            messages.append(argv[index + 1])
            index += 2
            continue
        if token.startswith("--message="):
            messages.append(token.split("=", 1)[1])
        elif token.startswith("-m") and token != "-m":
            messages.append(token[2:])
        index += 1

    if len(messages) != 1:
        return None, 'use one-line git commit -m "type: Summary"'

    return messages[0], None


def _validate_commit_message(message: str) -> str | None:
    if "\n" in message or "\r" in message:
        return "commit message must be one line"

    subject = message.strip()
    if not subject:
        return "commit message is empty"
    if len(subject) > 50:
        return f"commit message exceeds 50 chars: {len(subject)}"
    if subject.endswith("."):
        return "commit message must not end with a period"

    match = _SUBJECT_RE.fullmatch(subject)
    if match is None:
        return "commit message must match 'type: Summary'"

    commit_type = match.group("type")
    if commit_type not in ALLOWED_COMMIT_TYPES:
        return f"unsupported commit type: {commit_type}"

    if not match.group("summary").strip():
        return "commit summary is empty"

    return None


def _git_command_is_blocked(command: str) -> tuple[bool, str]:
    if not command:
        return False, ""

    for match in _GIT_COMMAND_RE.finditer(command):
        subcommand = match.group(1).lower()
        if subcommand in MUTATING_GIT_SUBCOMMANDS:
            return True, f"git {subcommand}"

    for match in _GIT_COMMIT_SEGMENT_RE.finditer(command):
        segment = match.group(1)

        if re.search(r"(?i)(?:^|\s)--amend(?:\s|$)", segment):
            return True, "git commit --amend"

        message, error = _extract_commit_message(segment)
        if error:
            return True, error

        error = _validate_commit_message(message or "")
        if error:
            return True, error

    branch_re = re.compile(
        rf"(?ix)(?:^|[\r\n;&|]\s*){_GIT_PREFIX}\s+branch\b([^\r\n;&|]*)"
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
        return True, "git branch mutation"

    return False, ""


def _decision(permission: str, reason: str | None = None) -> dict[str, Any]:
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

    github_blocked, github_action = _github_tool_is_mutating(tool_name)
    if github_blocked:
        reason = (
            "GitHub MCP repository writes are blocked: "
            f"{github_action}. Local validated git add/new commit only."
        )
        print(json.dumps(_decision("deny", reason), ensure_ascii=False))
        return 0

    command = _extract_command(_tool_input(payload))
    git_blocked, reason = _git_command_is_blocked(command)
    if git_blocked:
        print(
            json.dumps(
                _decision(
                    "deny",
                    f"Git policy blocked this operation: {reason}. "
                    "push/merge/history changes remain user-managed.",
                ),
                ensure_ascii=False,
            )
        )
        return 0

    print(json.dumps(_decision("allow"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
