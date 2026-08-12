---
name: validate-server
description: Validate FastAPI server, authentication, WebSocket, database, and server-side API changes in dabom_capstone. Use when files under server/ or server-related tests change. Do not use for frontend-only, ROS-only, or Raspberry Pi-only changes.
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
8. Run affected tests under tests/.
9. If server/app.py or frontend-facing API behavior changed, invoke validate-dashboard.
10. Record commands, exit codes, and skipped checks.

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