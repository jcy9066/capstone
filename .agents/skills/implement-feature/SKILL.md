---
name: implement-feature
description: Implement or modify features in dabom_capstone. Use for code changes, bug fixes, refactoring, API additions, UI changes, ROS changes, or Raspberry Pi changes. Orchestrate required read-only exploration and validation before and after edits. Do not use for explanation-only requests or read-only repository analysis.
---

# Implement Feature

Implement the requested change with the smallest safe modification while following the repository orchestration rules.

## Workflow

1. Read the root `AGENTS.md`.
2. Restate the requested scope internally.
3. Inspect the current branch and changes with read-only Git commands.
4. Before modifying application source or configuration, delegate repository exploration to `code_explorer` when running in the Primary/Main Agent thread.
5. Ask `code_explorer` to identify:
   - actual entry points and execution paths
   - imports, routes, launch files, scripts, and callers
   - affected files and areas
   - existing implementations that may already perform the requested function
   - duplicate or unused implementations
   - compatibility risks across public APIs, ROS interfaces, and UART protocols
6. Wait for the `code_explorer` result before deciding the final edit scope.
7. If the current thread is already `code_explorer`, do not spawn another `code_explorer`; perform only the assigned read-only exploration and return the findings to the parent.
8. Identify all affected areas:
   - `server/`
   - `frontend/`
   - `navigation/`
   - `raspberry/`
   - `tests/`
9. Modify only the files required by the request. Application source and configuration edits are owned by the Primary/Main Agent.
10. Preserve existing public APIs and protocols unless the request requires changing them.
11. Add or update tests when behavior changes.
12. Run every validation Skill relevant to the changed areas.
13. Follow each validation Skill's mandatory Sub-Agent delegation instructions. Independent reviewer delegations may run in parallel within the configured concurrency limit.
14. Wait for all required area-specific validation and reviewer results.
15. Run `review-change` after all area-specific validation.
16. Report:
    - changed files
    - implemented behavior
    - Skills used
    - Sub-Agents used and their assigned roles
    - validation performed
    - failed or skipped validation
    - Sub-Agent work that could not be performed
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
- any source or configuration file changed:
  - run `review-change`

## Sub-Agent Orchestration

- Pre-change exploration:
  - Primary/Main Agent must delegate to `code_explorer` before editing.
  - This result is a dependency for edit-scope selection, so wait for it before modification.
- Post-change validation:
  - `validate-dashboard` owns delegation to `dashboard_reviewer`.
  - `validate-navigation` owns delegation to `ros_reviewer`.
  - `validate-raspberry` owns delegation to `hardware_reviewer`.
  - `validate-server` may reuse the pre-change `code_explorer` result when it covers the same server execution path; when invoked standalone without a matching current-scope exploration result, it owns fallback delegation to `code_explorer`.
- Final review:
  - `review-change` owns delegation to `test_reviewer`.
- Do not spawn duplicate reviewers for the same current working-tree diff and scope.
- Project Sub-Agents must not recursively spawn another Project Sub-Agent unless the parent explicitly requests it.

## Restrictions

- Do not modify unrelated files.
- Do not create duplicate implementations.
- Do not remove files without checking references and execution paths.
- Do not create plan/result documents unless explicitly requested.
- Do not run Git commands that modify the working tree, index, branch, history, or remote.
- Do not run real motor, GPIO, serial movement, ROS motion, or firmware flashing commands.
- Do not claim hardware validation when only static validation was performed.
- Do not continue past a required pre-change delegation if that delegation failed; report the failure instead of claiming the orchestration completed.
