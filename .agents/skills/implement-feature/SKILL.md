---
name: implement-feature
description: Implement or modify features in dabom_capstone. Use for code changes, bug fixes, refactoring, API additions, UI changes, ROS changes, or Raspberry Pi changes. Do not use for explanation-only requests or read-only repository analysis.
---

# Implement Feature

Implement the requested change with the smallest safe modification.

## Workflow

1. Read the root `AGENTS.md`.
2. Restate the requested scope internally.
3. Inspect the current branch and changes with read-only Git commands.
4. Locate the actual entry point, imports, routes, launch files, scripts, and callers.
5. Identify all affected areas:
   - `server/`
   - `frontend/`
   - `navigation/`
   - `raspberry/`
   - `tests/`
6. Check whether an existing implementation already performs the requested function.
7. Modify only the files required by the request.
8. Preserve existing public APIs and protocols unless the request requires changing them.
9. Add or update tests when behavior changes.
10. Run every validation Skill relevant to the changed areas.
11. Run `review-change` after all area-specific validation.
12. Report:
    - changed files
    - implemented behavior
    - validation performed
    - failed or skipped validation
    - hardware checks still required

## Required Validation Routing

- `server/` changed:
  - run `validate-server`
- `frontend/` changed:
  - run `validate-dashboard`
- `server/app.py` changed:
  - run `validate-server`
  - run `validate-dashboard`
- `navigation/` changed:
  - run `validate-navigation`
- `raspberry/` changed:
  - run `validate-raspberry`
- any source file changed:
  - run `review-change`

## Restrictions

- Do not modify unrelated files.
- Do not create duplicate implementations.
- Do not remove files without checking references and execution paths.
- Do not create plan/result documents unless explicitly requested.
- Do not run Git commands that modify the working tree, index, branch, history, or remote.
- Do not run real motor, GPIO, serial movement, ROS motion, or firmware flashing commands.
- Do not claim hardware validation when only static validation was performed.