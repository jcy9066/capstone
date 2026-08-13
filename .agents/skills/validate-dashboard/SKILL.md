---
name: validate-dashboard
description: Validate the actual dabom_capstone web dashboard with the Playwright Browser MCP. Use when frontend templates, static assets, browser-facing APIs, login flows, dashboard state, or server/app.py change. Delegate browser validation to dashboard_reviewer. Do not use for backend changes with no browser-visible effect.
---

# Validate Dashboard

Validate the actual rendered dashboard and browser runtime through the `dashboard_reviewer` Sub-Agent.

## Required References

Read before validation:

- `references/dashboard_flows.md`
- `references/expected_states.md`

## Mandatory Sub-Agent Delegation

1. Read the root `AGENTS.md`.
2. When running in the Primary/Main Agent thread, delegate the actual browser validation to `dashboard_reviewer`.
3. Give `dashboard_reviewer` the current changed scope, relevant files, expected behavior, and the safe test URL or environment information available to the parent.
4. Require `dashboard_reviewer` to use the Playwright Browser MCP and return browser evidence, not an inferred result from source code alone.
5. If a `dashboard_reviewer` thread already covers the same current working-tree diff, URL, and validation scope, reuse that active or completed result instead of spawning a duplicate.
6. If the current thread is already `dashboard_reviewer`, do not spawn another `dashboard_reviewer`; perform the validation flow below directly and return the result to the parent.
7. The Primary/Main Agent must wait for the reviewer result before concluding `validate-dashboard`.

## Preparation

1. Confirm the dashboard server is running in a safe test configuration.
2. Determine the base URL from the current environment.
3. Use a test account and non-production data.
4. Confirm actual motor output, Telegram reporting, warning broadcast, and destructive controls are disabled.

## Validation Flow

The `dashboard_reviewer` performs the following flow:

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

## Parent Integration

After `dashboard_reviewer` returns:

1. Check that the result covers every browser-visible behavior affected by the current change.
2. Distinguish application defects from unavailable test data, missing credentials, unavailable server state, or intentionally prohibited actions.
3. Do not repeat the same browser flow in the Primary/Main Agent unless the reviewer result is incomplete, contradictory, or requires focused confirmation.
4. Carry blocking browser failures into `review-change` and the final report.

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

- Sub-Agent used
- tested URL
- tested flow
- expected result
- actual result
- console messages
- failed requests
- screenshots captured
- likely related files
- unsafe flows intentionally skipped
- conclusion: passed, failed, or incomplete

## Restrictions

- Application source and configuration must not be modified during dashboard review.
- `dashboard_reviewer` may only create screenshots, traces, or other temporary browser-validation artifacts when needed.
- Do not claim browser validation if the Playwright flow was not actually executed.
- Project Sub-Agents must not recursively spawn another Project Sub-Agent unless the parent explicitly requests it.
