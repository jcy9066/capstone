from __future__ import annotations

import json
import re
import shlex
import sys
from typing import Any


# Local Git policy:
# - Approved read-only Git commands are allowed.
# - git switch --no-guess to an existing branch is allowed.
# - git add and a new validated git commit are allowed.
# - Branch creation/deletion, remote operations, merges, rebases, history rewriting,
#   checkout/restore/reset, amend, and other mutating operations remain blocked.
MUTATING_GIT_SUBCOMMANDS = frozenset(
    {
        "am",
        "apply",
        "bisect",
        "checkout",
        "cherry-pick",
        "clean",
        "clone",
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
        "tag",
        "worktree",
    }
)

READ_ONLY_GIT_SUBCOMMANDS = frozenset(
    {
        "blame",
        "cat-file",
        "cherry",
        "count-objects",
        "describe",
        "diff",
        "diff-files",
        "diff-index",
        "diff-tree",
        "for-each-ref",
        "grep",
        "log",
        "ls-files",
        "ls-tree",
        "merge-base",
        "name-rev",
        "rev-list",
        "rev-parse",
        "shortlog",
        "show",
        "show-ref",
        "status",
        "verify-commit",
        "verify-tag",
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

ALLOWED_COMMIT_TYPES = frozenset(
    {
        "feat",
        "fix",
        "docs",
        "style",
        "design",
        "test",
        "refactor",
        "build",
        "ci",
        "perf",
        "chore",
        "rename",
        "remove",
    }
)

# Accept raw/path-qualified Git and RTK-wrapped Git at shell-command boundaries.
# Common shell wrappers are consumed conservatively before the Git executable;
# each captured invocation is then parsed so global options cannot hide the
# subcommand.
_GIT_INVOCATION_RE = re.compile(
    r"(?ix)(?:^|[\r\n;&|`!]|\$\()\s*"
    r"(?:(?:env|command|cmd(?:\.exe)?|sudo|powershell(?:\.exe)?|pwsh(?:\.exe)?|"
    r"bash|sh)\b[^\r\n;&|()`]*?\s+[\"']?)*"
    r"((?:rtk(?:\.exe)?\s+)?(?:"
    r"\"[^\"\r\n]*[\\/]git(?:\.exe)?\""
    r"|'[^'\r\n]*[\\/]git(?:\.exe)?'"
    r"|(?:[^\s\r\n;&|()`]*[\\/])?git(?:\.exe)?"
    r")(?=\s|$)[^\r\n;&|)`]*)"
)

_GIT_GLOBAL_FLAGS = frozenset(
    {
        "--bare",
        "--glob-pathspecs",
        "--icase-pathspecs",
        "--literal-pathspecs",
        "--no-optional-locks",
        "--no-pager",
        "--no-replace-objects",
        "--noglob-pathspecs",
        "--paginate",
    }
)

_GIT_GLOBAL_OPTIONS_WITH_VALUE = frozenset(
    {
        "-C",
        "-c",
        "--config-env",
        "--git-dir",
        "--namespace",
        "--super-prefix",
        "--work-tree",
    }
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


def _commit_args_are_blocked(args: list[str]) -> tuple[bool, str]:
    message_count = 0
    index = 0

    while index < len(args):
        token = args[index]
        if token in {"-m", "--message"}:
            if index + 1 >= len(args):
                return True, "git commit message is missing"
            message_count += 1
            index += 2
            continue
        if token.startswith("--message="):
            message_count += 1
            index += 1
            continue
        if token.startswith("-m") and token != "-m":
            message_count += 1
            index += 1
            continue
        return True, f"git commit argument is not approved: {token}"

    if message_count != 1:
        return True, 'use one-line git commit -m "type: Summary"'

    return False, ""


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


def _parse_git_invocation(
    segment: str,
) -> tuple[str | None, list[str], str | None]:
    try:
        argv = shlex.split(segment, posix=True)
    except ValueError:
        return None, [], "git command quoting is invalid"

    index = 0
    if index < len(argv) and argv[index].lower() in {"rtk", "rtk.exe"}:
        index += 1
    executable = argv[index].replace("\\", "/").rsplit("/", 1)[-1].lower()
    if executable not in {"git", "git.exe"}:
        return None, [], "git command parsing failed"
    index += 1

    while index < len(argv) and argv[index].startswith("-"):
        token = argv[index]
        if token == "--":
            index += 1
            break
        if token in _GIT_GLOBAL_FLAGS:
            index += 1
            continue
        if token in _GIT_GLOBAL_OPTIONS_WITH_VALUE:
            if index + 1 >= len(argv):
                return None, [], f"git global option value is missing: {token}"
            index += 2
            continue
        if (
            token.startswith("-C")
            or token.startswith("-c")
            or any(
                token.startswith(option + "=")
                for option in _GIT_GLOBAL_OPTIONS_WITH_VALUE
                if option.startswith("--")
            )
        ):
            index += 1
            continue
        return None, [], f"unsupported git global option: {token}"

    if index >= len(argv):
        return None, [], "git subcommand is missing"

    return argv[index].lower(), argv[index + 1 :], None


def _switch_is_blocked(args: list[str]) -> tuple[bool, str]:
    # This is intentionally strict: no detach, force, merge, discard, tracking,
    # or branch-creation options. --no-guess prevents implicit creation from a
    # uniquely matching remote branch.
    if args.count("--no-guess") != 1:
        return True, "git switch requires --no-guess"

    branch_args = [token for token in args if token != "--no-guess"]
    if len(branch_args) != 1 or branch_args[0].startswith("-"):
        return True, "git switch only permits one existing branch"

    return False, ""


def _branch_is_blocked(args: list[str]) -> tuple[bool, str]:
    if not args:
        return False, ""

    read_only_flags = {
        "-a",
        "-l",
        "-r",
        "-v",
        "-vv",
        "--all",
        "--contains",
        "--list",
        "--merged",
        "--no-merged",
        "--remotes",
        "--show-current",
    }
    has_read_only_flag = False

    for token in args:
        if token in read_only_flags or token.startswith(
            ("--contains=", "--merged=", "--no-merged=")
        ):
            has_read_only_flag = True
            continue
        if token.startswith("-"):
            return True, f"git branch option is not read-only: {token}"

    if not has_read_only_flag:
        return True, "git branch mutation"

    return False, ""


def _git_command_is_blocked(command: str) -> tuple[bool, str]:
    if not command:
        return False, ""

    for match in _GIT_INVOCATION_RE.finditer(command):
        segment = match.group(1)
        subcommand, args, error = _parse_git_invocation(segment)
        if error:
            return True, error
        if subcommand in MUTATING_GIT_SUBCOMMANDS:
            return True, f"git {subcommand}"
        if subcommand == "switch":
            blocked, reason = _switch_is_blocked(args)
            if blocked:
                return True, reason
            continue
        if subcommand == "branch":
            blocked, reason = _branch_is_blocked(args)
            if blocked:
                return True, reason
            continue
        if subcommand == "commit":
            blocked, reason = _commit_args_are_blocked(args)
            if blocked:
                return True, reason
            message, error = _extract_commit_message(segment)
            if error:
                return True, error
            error = _validate_commit_message(message or "")
            if error:
                return True, error
            continue
        if subcommand == "add":
            continue
        if subcommand not in READ_ONLY_GIT_SUBCOMMANDS:
            return True, f"git subcommand is not approved: {subcommand}"

    return False, ""


def _deny_decision(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": reason,
        }
    }


def main() -> int:
    payload = _read_payload()
    tool_name = _tool_name(payload)

    github_blocked, github_action = _github_tool_is_mutating(tool_name)
    if github_blocked:
        reason = (
            "GitHub MCP repository writes are blocked: "
            f"{github_action}. Local git switch/add/new commit only."
        )
        print(json.dumps(_deny_decision(reason), ensure_ascii=False))
        return 0

    command = _extract_command(_tool_input(payload))
    git_blocked, reason = _git_command_is_blocked(command)
    if git_blocked:
        print(
            json.dumps(
                _deny_decision(
                    f"Git policy blocked this operation: {reason}. "
                    "Only local git switch/add/new commit are automated; "
                    "branch creation, remote operations, merge/rebase, "
                    "and history rewriting remain user-managed."
                ),
                ensure_ascii=False,
            )
        )
        return 0

    # No explicit "allow" decision: current Codex treats permissionDecision=allow
    # without updatedInput as an unsupported PreToolUse result.
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
