# Battery status polling removal result

## Changed

- Removed the dashboard JavaScript update for `sys-battery`.
- CPU, temperature, RAM, and network status polling remain unchanged.

## Not changed

- No backend route was changed.
- No server or Uvicorn process was restarted.

## Verification

- Confirmed no `sys-battery` reference remains in `frontend/services/static/script.js`.
