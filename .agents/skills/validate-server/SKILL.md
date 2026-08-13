---
name: validate-server
description: Validate FastAPI server, authentication, WebSocket, database, and server-side API changes in dabom_capstone. Use when files under server/ or server-related tests change. Coordinate server execution-path review with code_explorer when needed. Do not use for frontend-only, ROS-only, or Raspberry Pi-only changes.
---

# Validate Server

Validate server-side changes without modifying Git state or external production data.

## Scope

Inspect changes related to:

- `server/app.py`
- `server/auth_service.py`
- server API modules
- WebSocket handling
- session and CSRF handling
- database access
- navigation APIs
- server-side tests

## Sub-Agent Delegation

1. Read the root `AGENTS.md`.
2. When running in the Primary/Main Agent thread, check whether a `code_explorer` result already covers the same current working-tree diff and affected server execution path.
3. If no matching current-scope exploration result exists, delegate a read-only server path review to `code_explorer` before concluding validation.
4. Ask `code_explorer` to trace:
   - changed FastAPI routes and their callers
   - frontend consumers of changed browser-facing APIs
   - imports and referenced modules
   - WebSocket producers and consumers when affected
   - duplicated or stale server execution paths
5. If the current thread is already `code_explorer`, do not spawn another `code_explorer`; perform the assigned read-only path review and return findings to the parent.
6. A pre-change `code_explorer` result from `implement-feature` may be reused only when it still covers the current changed scope. The Primary/Main Agent remains responsible for validating the actual post-change diff.
7. If `server/app.py` or frontend-visible server behavior changed, `validate-dashboard` must be run and owns delegation to `dashboard_reviewer`.

## Procedure

1. Read the changed server files and their callers.
2. Confirm imported modules and referenced files exist.
3. Check that route paths, methods, request fields, and response fields remain consistent with frontend callers.
4. Check session, authentication, authorization, CSRF, and cookie handling for affected routes.
5. Check WebSocket connection, disconnect, timeout, and stale-state handling when affected.
6. Check database queries for:
   - parameter binding
   - transaction handling
   - connection cleanup
   - deleted-user filtering
   - error handling
7. Run the deterministic validator:

```bash
python3 .agents/skills/validate-server/scripts/validate_server.py
```

8. Run affected tests under `tests/`.
9. If `server/app.py` or frontend-facing API behavior changed, invoke `validate-dashboard`.
10. Wait for any required `code_explorer` result before producing the server-validation conclusion.
11. Record commands, exit codes, Sub-Agent findings, and skipped checks.

## Minimum Checks

- Python syntax and import validation
- affected pytest tests
- duplicate FastAPI route detection
- static/template path existence
- frontend API path consistency
- required environment-variable name consistency
- secrets not hardcoded
- no production DB mutation during validation

## Restrictions

- Do not send Telegram notifications.
- Do not delete or modify production database data.
- Do not start actual robot motion.
- Do not change Git state.
- Do not report success if required tests failed.
- Do not spawn `test_reviewer` here; final regression delegation belongs to `review-change`.
- Project Sub-Agents must not recursively spawn another Project Sub-Agent unless the parent explicitly requests it.
