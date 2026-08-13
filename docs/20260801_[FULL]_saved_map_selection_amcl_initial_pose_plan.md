# Saved map selection and AMCL initial pose plan

## Scope and constraints

- Do not modify any file under `navigation/`.
- Preserve the active camera, LiDAR map, manual drive, alert, and existing map-save features.
- Add server modules, `server/app.py` integration, and dashboard assets only.

## Backend design

1. Add a strict saved-map registry that accepts only an exact `map_name` found in validated metadata.
2. Resolve metadata, YAML, and PGM paths beneath `navigation/maps`; reject traversal, external paths, symlinks outside the directory, and incomplete maps.
3. Add one long-lived ROS control node/executor. It owns a LoadMap client, initial-pose publisher, map subscriber, AMCL-pose subscriber, and lifecycle state clients.
4. Add authenticated routes for active-map status and map loading. Mutating requests require the existing CSRF token.
5. Serialize map loads with a nonblocking lock; verify the loaded OccupancyGrid and AMCL response before persisting active-map state.

## Frontend design

1. Add a MAP button beside SAVE and the minimap expand button.
2. Load the selection modal and active-map badge from isolated CSS/JavaScript assets, leaving the existing dashboard script unchanged.
3. Present map metadata, active state, initial pose fields in degrees, confirmation, progress, and useful error messages.

## Verification

- Python syntax and FastAPI route registration.
- Registry rejection for invalid names and paths.
- Mock-free static inspection of service, topic, lock, and authentication safeguards.
- Document the required GPU/ROS manual checks separately; no ROS process will be started here.
