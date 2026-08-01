# Battery status polling removal plan

## Scope

- Modify only the dashboard status polling code.
- Do not restart the server or change backend routes.

## Change

- Remove the `sys-battery` DOM update because the battery display is intentionally absent from the dashboard.
- Retain CPU, temperature, RAM, and network status polling.

## Verification

- Confirm no JavaScript reference to `sys-battery` remains in the polling script.
