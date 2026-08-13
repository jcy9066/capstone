---
name: validate-navigation
description: Validate ROS 2 Humble, SLAM Toolbox, localization, AMCL, Nav2, TF, topics, launch files, and navigation configuration in dabom_capstone. Use when navigation/ or related ROS bridge code changes. Delegate ROS structure review to ros_reviewer. Do not use for unrelated server, frontend, or Pico-only changes.
---

# Validate Navigation

Validate ROS navigation changes using a delegated read-only ROS review plus deterministic static, build, and test checks available to the Primary/Main Agent.

## Required Reference

Read:

- `references/ros_interfaces.md`

## Scope

Inspect:

- `navigation/`
- `navigation/ros/patrol_navigation/`
- ROS bridge modules under `server/`
- launch files
- YAML configuration
- maps
- package metadata
- TF and topic interfaces

## Mandatory Sub-Agent Delegation

1. Read the root `AGENTS.md`.
2. When running in the Primary/Main Agent thread, delegate ROS structure and interface review to `ros_reviewer`.
3. Ask `ros_reviewer` to inspect the current working-tree diff and verify:
   - launch to executable registration
   - package installation coverage
   - topic, service, action, and frame consistency
   - TF chain and mode separation
   - QoS and timestamp handling
   - accidental real motor-output enablement
4. If a `ros_reviewer` result already covers the same current working-tree diff and ROS scope, reuse it instead of spawning a duplicate.
5. If the current thread is already `ros_reviewer`, do not spawn another `ros_reviewer`; perform the assigned read-only review and return findings to the parent.
6. The Primary/Main Agent may run deterministic validators, builds, and tests while `ros_reviewer` is working when those tasks are independent.
7. The Primary/Main Agent must wait for the reviewer result before concluding `validate-navigation`.

## Reviewer Checks

The `ros_reviewer` performs read-only semantic and interface review:

1. Identify changed ROS nodes, launch files, config files, and interfaces.
2. Trace each executable from:
   - launch file
   - `setup.py`
   - Python module
   - installed package path
3. Verify referenced config, RViz, map, and launch files exist.
4. Verify topic, service, action, and frame names against `ros_interfaces.md`.
5. Verify the expected TF chain:

```text
map → odom → base_link → laser
```

6. Distinguish:
   - scan-only
   - mapping
   - localization
   - localization + Nav2
7. Distinguish dry-run command output from real motor output.
8. Report file and symbol evidence for each finding.

## Primary/Main Agent Validation

The Primary/Main Agent performs deterministic and environment-dependent checks:

1. Validate Python and YAML syntax.
2. Run the deterministic validator:

```bash
python3 .agents/skills/validate-navigation/scripts/validate_navigation.py
```

3. When ROS 2 Humble and dependencies are available, build only the affected package:

```bash
cd navigation/ros
colcon build --packages-select patrol_navigation
```

4. Run navigation-related tests.
5. Combine deterministic results with `ros_reviewer` findings.
6. Report runtime checks separately from static and build checks.

## Checks

- setup.py console-script registration
- launch executable existence
- installed data-file coverage
- YAML parse success
- frame-name consistency
- topic-name consistency
- QoS suitability
- map path consistency
- localization parameter consistency
- Nav2 planner/controller configuration consistency
- duplicate bridge implementations
- accidental motor-output enablement

## Restrictions

- Do not publish `/cmd_vel`.
- Do not start real motor output.
- Do not alter ROS processes unless explicitly requested.
- Do not save or overwrite maps.
- Do not treat successful build as successful localization or navigation.
- Do not modify Git state.
- `ros_reviewer` must not modify application source or configuration.
- Do not spawn `test_reviewer` here; final regression delegation belongs to `review-change`.
- Project Sub-Agents must not recursively spawn another Project Sub-Agent unless the parent explicitly requests it.
