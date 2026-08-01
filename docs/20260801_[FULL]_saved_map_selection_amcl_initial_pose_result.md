# Saved map selection and AMCL initial pose result

## Modified and added files

- `server/app.py`
- `server/navigation_map_service.py`
- `server/navigation_ros_control.py`
- `server/navigation_map_api.py`
- `frontend/templates/index.html`
- `frontend/services/static/navigation_map_control.js`
- `frontend/services/static/navigation_map_control.css`

## Added APIs

- `GET /api/navigation/maps/active`
- `POST /api/navigation/maps/load`
- Updated `GET /api/navigation/maps` to return only validated saved maps for authenticated users.

## ROS connection

- One server-lifetime ROS node/executor creates the `/map_server/load_map` client, `/initialpose` publisher, `/map` subscriber, `/amcl_pose` subscriber, and lifecycle state clients.
- The load flow checks for an active mapping publisher, waits for localization services, verifies the LoadMap result, verifies OccupancyGrid metadata, publishes an initial pose, and verifies AMCL pose proximity.
- The initial pose uses x/y covariance `0.25` and yaw covariance `radians(15)^2`.

## Active map state and security

- Active state is persisted atomically in `data/runtime/navigation_active_map.json`, outside `navigation/`.
- Saved map resolution is allowlist-only and validates metadata, YAML, PGM, and raw JSON beneath `navigation/maps`.
- The map-load API requires a logged-in session and the existing CSRF token. Concurrent loads return `409`.
- No shell command, `shell=True`, `os.system`, or user-controlled ROS service/topic path is used.

## Local verification

- Python compilation passed for all modified server modules.
- All three saved maps passed registry validation.
- Required routes registered successfully.
- Unauthenticated list requests return `401`; map loads without CSRF return `403`; traversal-style map names return `400`.
- MAP button order and existing SAVE function were confirmed.

- Load responses include both `yaw_degrees` (dashboard input) and `yaw` in radians (ROS value).

## Required GPU/ROS manual verification

```bash
source /opt/ros/humble/setup.bash
source navigation/ros/install/setup.bash
ros2 launch patrol_navigation localization.launch.py \
  map:="$(pwd)/navigation/maps/test_map_20260801.yaml" \
  server_base_url:=http://127.0.0.1:21063 \
  start_lidar:=false start_fake_odom:=false
```

After restarting the FastAPI server by the normal project procedure, log in, open MAP, select `slam_test_01`, and load it with x=0, y=0, yaw=0. Verify:

```bash
ros2 topic echo /map --once
ros2 topic echo /amcl_pose --once
ros2 run tf2_ros tf2_echo map base_link
```

Expected map metadata for `slam_test_01` is width 75, height 60, resolution 0.05. Do not run mapping mode and localization mode together; the API rejects active `slam_toolbox` mapping with `MAPPING_MODE_ACTIVE`.

## Follow-up

- Nav2 goal cancellation and costmap clearing are intentionally not included because no complete Nav2 goal-control integration exists in this repository.
