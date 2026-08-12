---
name: review-change
description: Perform the final read-only review of dabom_capstone changes for secrets, generated files, duplicate code, unintended scope, missing tests, and unsafe behavior. Use after any code or configuration change. Do not use as a replacement for area-specific validation.
---

# Review Change

Perform a final read-only review after all relevant validation Skills have run.

## Procedure

1. Inspect repository status using read-only Git commands.
2. Review unstaged and staged diffs without changing Git state.
3. List every changed, added, deleted, and untracked file.
4. Confirm each change belongs to the user-requested scope.
5. Run the deterministic reviewer:

```bash
python3 .agents/skills/review-change/scripts/review_change.py
```
6. Check for:
    - secrets
    - generated files
    - backups
    - build outputs
    - duplicated implementations
    - dead or unreferenced code
    - unintended API changes
    - missing tests
    - documentation drift
7. Use the GitHub MCP in read-only mode when comparison with the remote dev branch, commit history, PR, Issue, or CI result is needed.
8. Do not use GitHub MCP tools that modify files, commits, branches, tags, releases, workflows, or repository settings.
9. Report blocking issues separately from non-blocking observations.

## Repository Hygiene Checks

Reject or flag:
- .env
- credentials, passwords, tokens, and secrets
- *.bak
- *.bak_*
- __pycache__/
- ROS build/, install/, and log/
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

## Final Report

Return:

- changed files
- area-specific validation completed
- blocking issues
- non-blocking issues
- skipped checks
- required real-hardware checks
- conclusion: ready or not ready for user-managed commit
- Restrictions
- Do not run git add, commit, push, pull, merge, rebase, or other Git-changing commands.
- Do not modify files during this review unless the user explicitly requests fixes.
- Do not create or update GitHub objects without user approval.
- Do not report the change as ready when blocking validation failed.
