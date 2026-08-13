---
name: review-change
description: Perform the final read-only review of dabom_capstone changes for secrets, generated files, duplicate code, unintended scope, missing tests, and unsafe behavior. Use after any code or configuration change. Delegate final regression and test-gap review to test_reviewer after area-specific validation. Do not use as a replacement for area-specific validation.
---

# Review Change

Perform the final read-only review after all relevant validation Skills and area-specific reviewer work have completed.

## Prerequisites

Before this Skill concludes:

- every validation Skill required by the changed areas must have run
- required `dashboard_reviewer`, `ros_reviewer`, and `hardware_reviewer` results must be available when their areas were affected
- failed and skipped checks must already be identified

Do not use `review-change` to replace missing area-specific validation.

## Procedure

1. Read the root `AGENTS.md`.
2. Inspect repository status using read-only Git commands.
3. Review unstaged and staged diffs without changing Git state.
4. List every changed, added, deleted, and untracked file.
5. Confirm each change belongs to the user-requested scope.
6. Run the deterministic reviewer:

```bash
python3 .agents/skills/review-change/scripts/review_change.py
```

7. Check for:
   - secrets
   - generated files
   - backups
   - build outputs
   - duplicated implementations
   - dead or unreferenced code
   - unintended API changes
   - missing tests
   - documentation drift
8. Use the GitHub MCP in read-only mode when comparison with the remote dev branch, commit history, PR, Issue, or CI result is needed.
9. Do not use GitHub MCP tools that modify files, commits, branches, tags, releases, workflows, or repository settings.
10. After the deterministic review and all area-specific validation results are available, delegate final regression and test-gap review to `test_reviewer` when running in the Primary/Main Agent thread.
11. Pass `test_reviewer` the current changed scope plus known validation successes, failures, and skipped checks so it can compare the claims with the actual current diff.
12. Wait for `test_reviewer` before issuing the final readiness conclusion.
13. Report blocking issues separately from non-blocking observations.

## Mandatory Sub-Agent Delegation

- Primary/Main Agent:
  - must spawn `test_reviewer` after all area-specific validation is complete
  - must wait for its result before declaring the change ready
- Existing result reuse:
  - if a `test_reviewer` result already covers the same final current working-tree diff and all current validation results, reuse it rather than spawning a duplicate
- Delegation guard:
  - if the current thread is already `test_reviewer`, do not spawn another `test_reviewer`; perform the final regression and test-gap review directly and return the result to the parent
- `test_reviewer` may run tests and static checks, but must not modify application source or configuration
- Project Sub-Agents must not recursively spawn another Project Sub-Agent unless the parent explicitly requests it

## Repository Hygiene Checks

Reject or flag:

- `.env`
- credentials, passwords, tokens, and secrets
- `*.bak`
- `*.bak_*`
- `__pycache__/`
- ROS `build/`, `install/`, and `log/`
- Pico SDK build output
- runtime logs
- received frames
- generated test maps
- model weights
- large unintended binaries
- editor and OS temporary files

## Code Review Checks

- changed execution paths are valid
- imports and references resolve
- no duplicate active implementation was added
- removed files have no active references
- public API and UART changes are coordinated
- failure and timeout behavior remains safe
- related tests were added or updated
- validation results match the claims
- area-specific Sub-Agent findings were addressed or explicitly reported

## Final Report

Return:

- changed files
- area-specific validation completed
- Sub-Agents used
- deterministic reviewer result
- `test_reviewer` result
- blocking issues
- non-blocking issues
- skipped checks
- required real-hardware checks
- conclusion: ready or not ready for user-managed commit

## Restrictions

- Do not run `git add`, `commit`, `push`, `pull`, `merge`, `rebase`, or other Git-changing commands.
- Do not modify files during this review unless the user explicitly requests fixes outside the read-only review step.
- Do not create or update GitHub objects without user approval.
- Do not report the change as ready when blocking validation failed.
- Do not report the change as ready when mandatory `test_reviewer` delegation could not be completed.
