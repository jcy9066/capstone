---
name: validate-navigation
description: Validate ROS 2 Humble, SLAM Toolbox, localization, AMCL, Nav2, TF, topics, launch files, and navigation configuration in dabom_capstone. Use when navigation/ or related ROS bridge code changes. Do not use for unrelated server, frontend, or Pico-only changes.
---

# Validate Navigation

Validate ROS navigation changes using static checks and available ROS build tools.

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

## Procedure

1. Identify changed ROS nodes, launch files, config files, and interfaces.
2. Trace each executable from:
   - launch file
   - `setup.py`
   - Python module
   - installed package path
3. Verify referenced config, RViz, map, and launch files exist.
4. Validate Python and YAML syntax.
5. Verify topic, service, action, and frame names against `ros_interfaces.md`.
6. Verify the expected TF chain:

```text
map → odom → base_link → laser
```
7. Distinguish:
    - scan-only
    - mapping
    - localization
    - localization + Nav2
8. Distinguish dry-run command output from real motor output.
9. Run the deterministic validator:

```
python3 .agents/skills/validate-navigation/scripts/validate_navigation.py
```
10. When ROS 2 Humble and dependencies are available, build only the affected package:

```
cd navigation/ros
colcon build --packages-select patrol_navigation
```
11. Run navigation-related tests.
12. Report runtime checks separately from static and build checks.

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

- Do not publish /cmd_vel.
- Do not start real motor output.
- Do not alter ROS processes unless explicitly requested.
- Do not save or overwrite maps.
- Do not treat successful build as successful localization or navigation.
- Do not modify Git state.
