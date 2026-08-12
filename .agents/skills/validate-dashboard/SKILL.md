---
name: validate-dashboard
description: Validate the actual dabom_capstone web dashboard with the Playwright Browser MCP. Use when frontend templates, static assets, browser-facing APIs, login flows, dashboard state, or server/app.py change. Do not use for backend changes with no browser-visible effect.
---

# Validate Dashboard

Use the Playwright Browser MCP to inspect the actual rendered dashboard and browser runtime.

## Required References

Read before validation:

- `references/dashboard_flows.md`
- `references/expected_states.md`

## Preparation

1. Confirm the dashboard server is running in a safe test configuration.
2. Determine the base URL from the current environment.
3. Use a test account and non-production data.
4. Confirm actual motor output, Telegram reporting, warning broadcast, and destructive controls are disabled.

## Validation Flow

1. Open the base URL.
2. Check redirect behavior for logged-in and logged-out sessions.
3. Validate the login page.
4. Log in using the test account when credentials are available.
5. Validate the main dashboard.
6. Inspect:
   - browser console errors
   - failed network requests
   - HTTP 4xx and 5xx responses
   - missing CSS, JavaScript, image, and stream assets
7. Exercise relevant safe UI flows:
   - login and logout
   - sidebar open and close
   - modal open and close
   - dark mode
   - camera online/offline state
   - robot connected/disconnected state
   - LiDAR online/offline state
   - saved-map list and selection display
   - navigation mode display
   - automatic/manual mode UI state
8. Compare actual states with `expected_states.md`.
9. Capture screenshots when they clarify a defect.
10. Report exact reproduction steps.

## Prohibited Browser Actions

Do not perform:

- D-Pad movement
- keyboard driving
- actual robot movement
- Telegram reporting
- warning broadcast
- ROS process start or stop
- map save or delete
- user deletion
- production data modification

## Result Format

Report:

- tested URL
- tested flow
- expected result
- actual result
- console messages
- failed requests
- screenshots captured
- likely related files
- unsafe flows intentionally skipped