# ROS process control panel plan

## Scope

- Repair the damaged dashboard without changing repository history.
- Keep the existing dashboard JavaScript and CSS isolated from ROS controls.
- Change only `frontend/` files and `server/app.py`.

## Design

1. Restore the existing dashboard assets as normal file content, then load an isolated ROS CSS/JS pair.
2. Add authenticated, CSRF-protected FastAPI routes through a dynamically loaded frontend route module. This avoids importing the obsolete Flask frontend package.
3. Control only allowlisted GPU components. Bridge lifecycle is in-process; independent ROS processes use exact command-line/PID matching and process groups, never broad process kills.
4. Show Pi service connection and control availability truthfully. The current Pi client does not support systemd service commands, so its control remains disabled.

## Verification

- Python syntax compilation and FastAPI route registration.
- Existing global dashboard functions remain present in `script.js`.
- No `shell=True` or broad process-kill command in the control module.
