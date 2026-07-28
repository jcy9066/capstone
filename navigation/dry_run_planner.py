"""LiDAR-only, non-actuating navigation decisions for the GPU server.

This module deliberately has no ROS, network, GPIO, serial, or motor imports.
It only converts the most recently received LaserScan payload into a dry-run
decision that another layer may display or log.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Mapping


FRONT_MIN_DEG = -20.0
FRONT_MAX_DEG = 20.0
LEFT_MIN_DEG = 20.0
LEFT_MAX_DEG = 90.0
RIGHT_MIN_DEG = -90.0
RIGHT_MAX_DEG = -20.0


@dataclass(frozen=True)
class DryRunPlannerConfig:
    """Configuration for the display-only obstacle avoidance heuristic."""

    enabled: bool = True
    stop_distance_m: float = 0.45
    slow_distance_m: float = 0.90
    normal_linear_mps: float = 0.25
    slow_linear_mps: float = 0.10
    turn_angular_rps: float = 0.65
    scan_timeout_sec: float = 1.0

    def __post_init__(self):
        if self.stop_distance_m <= 0:
            raise ValueError("stop_distance_m must be positive")
        if self.slow_distance_m < self.stop_distance_m:
            raise ValueError("slow_distance_m must be at least stop_distance_m")
        if self.normal_linear_mps < 0 or self.slow_linear_mps < 0:
            raise ValueError("linear speeds must be non-negative")
        if self.turn_angular_rps <= 0 or self.scan_timeout_sec <= 0:
            raise ValueError("turn_angular_rps and scan_timeout_sec must be positive")


def validate_scan_payload(payload: Any) -> dict[str, Any]:
    """Return a copy of a valid HTTP LaserScan payload or raise ValueError.

    Individual range entries may be ``None`` because the Pi bridge converts
    ROS NaN/Infinity values to JSON null.  The planner filters those entries
    later, while scan metadata must be finite and structurally sound.
    """

    if not isinstance(payload, Mapping):
        raise ValueError("scan payload must be a JSON object")

    required = (
        "robot_id",
        "frame_id",
        "timestamp",
        "angle_min",
        "angle_max",
        "angle_increment",
        "range_min",
        "range_max",
        "ranges",
    )
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(f"missing scan fields: {', '.join(missing)}")

    if not str(payload["robot_id"]).strip():
        raise ValueError("robot_id must not be empty")
    if not str(payload["frame_id"]).strip():
        raise ValueError("frame_id must not be empty")
    if not isinstance(payload["ranges"], list) or not payload["ranges"]:
        raise ValueError("ranges must be a non-empty list")

    numeric_fields = ("angle_min", "angle_max", "angle_increment", "range_min", "range_max")
    for name in numeric_fields:
        value = _finite_number(payload[name])
        if value is None:
            raise ValueError(f"{name} must be a finite number")

    if float(payload["angle_increment"]) == 0.0:
        raise ValueError("angle_increment must not be zero")
    if float(payload["range_min"]) < 0.0 or float(payload["range_max"]) <= float(payload["range_min"]):
        raise ValueError("range_min and range_max are invalid")

    normalized = dict(payload)
    normalized["ranges"] = [
        None if _finite_number(value) is None else float(value) for value in payload["ranges"]
    ]
    return normalized


def plan_scan(
    scan: Mapping[str, Any] | None,
    received_at: float | None,
    config: DryRunPlannerConfig,
    now: float | None = None,
) -> dict[str, Any]:
    """Create a safe, non-actuating decision for one latest scan.

    The per-sector value is the 10th percentile of valid ranges rather than a
    raw minimum.  A real nearby obstacle normally occupies adjacent LiDAR
    beams; using this low percentile still responds to it while one isolated
    bad beam cannot force an unnecessary turn or stop.
    """

    now = time.time() if now is None else float(now)
    if scan is None or received_at is None:
        return _decision(
            action="WAITING_FOR_SCAN",
            reason="NO_SCAN",
            received_at=None,
            scan_age_sec=None,
            front_distance_m=None,
            left_distance_m=None,
            right_distance_m=None,
        )

    scan_age_sec = max(0.0, now - float(received_at))
    front, left, right = sector_distances(scan)
    common = {
        "received_at": float(received_at),
        "scan_age_sec": scan_age_sec,
        "front_distance_m": front,
        "left_distance_m": left,
        "right_distance_m": right,
    }

    if not config.enabled:
        return _decision(action="STOP", reason="DRY_RUN_DISABLED", **common)
    if scan_age_sec > config.scan_timeout_sec:
        return _decision(action="STOP", reason="SCAN_TIMEOUT", **common)
    if front is None:
        return _decision(action="STOP", reason="FRONT_SECTOR_UNAVAILABLE", **common)

    left_clear = left is not None and left >= config.slow_distance_m
    right_clear = right is not None and right >= config.slow_distance_m

    if front <= config.stop_distance_m:
        if left_clear and (not right_clear or left >= right):
            return _decision(
                action="TURN_LEFT",
                reason="FRONT_OBSTACLE_LEFT_CLEAR",
                linear_x=0.0,
                angular_z=config.turn_angular_rps,
                **common,
            )
        if right_clear:
            return _decision(
                action="TURN_RIGHT",
                reason="FRONT_OBSTACLE_RIGHT_CLEAR",
                linear_x=0.0,
                angular_z=-config.turn_angular_rps,
                **common,
            )
        return _decision(action="STOP", reason="NO_SAFE_TURN", **common)

    if front <= config.slow_distance_m:
        turn_left = _prefer_left(left, right)
        if turn_left is None:
            return _decision(action="STOP", reason="SIDE_SECTORS_UNAVAILABLE", **common)
        if max(left or 0.0, right or 0.0) < config.stop_distance_m:
            return _decision(action="STOP", reason="NO_SAFE_TURN", **common)
        return _decision(
            action="SLOW_AVOID",
            reason="FRONT_CAUTION",
            linear_x=config.slow_linear_mps,
            angular_z=config.turn_angular_rps if turn_left else -config.turn_angular_rps,
            **common,
        )

    return _decision(
        action="FORWARD",
        reason="FRONT_CLEAR",
        linear_x=config.normal_linear_mps,
        angular_z=0.0,
        **common,
    )


def sector_distances(scan: Mapping[str, Any]) -> tuple[float | None, float | None, float | None]:
    """Return robust front, left, and right distances from a LaserScan payload."""

    angle_min = _finite_number(scan.get("angle_min"))
    angle_increment = _finite_number(scan.get("angle_increment"))
    range_min = _finite_number(scan.get("range_min"))
    range_max = _finite_number(scan.get("range_max"))
    ranges = scan.get("ranges")
    if (
        angle_min is None
        or angle_increment is None
        or angle_increment == 0.0
        or range_min is None
        or range_max is None
        or range_max <= range_min
        or not isinstance(ranges, list)
    ):
        return None, None, None

    front_values: list[float] = []
    left_values: list[float] = []
    right_values: list[float] = []
    for index, raw_range in enumerate(ranges):
        distance = _finite_number(raw_range)
        if distance is None or distance <= 0.0 or distance < range_min or distance > range_max:
            continue
        angle_deg = math.degrees(angle_min + index * angle_increment)
        if FRONT_MIN_DEG <= angle_deg <= FRONT_MAX_DEG:
            front_values.append(distance)
        elif LEFT_MIN_DEG < angle_deg <= LEFT_MAX_DEG:
            left_values.append(distance)
        elif RIGHT_MIN_DEG <= angle_deg < RIGHT_MAX_DEG:
            right_values.append(distance)

    return (
        _lower_percentile(front_values),
        _lower_percentile(left_values),
        _lower_percentile(right_values),
    )


def _decision(
    *,
    action: str,
    reason: str,
    received_at: float | None,
    scan_age_sec: float | None,
    front_distance_m: float | None,
    left_distance_m: float | None,
    right_distance_m: float | None,
    linear_x: float = 0.0,
    angular_z: float = 0.0,
) -> dict[str, Any]:
    return {
        "dry_run": True,
        "motor_output_enabled": False,
        "action": action,
        "reason": reason,
        "linear_x": round(float(linear_x), 4),
        "angular_z": round(float(angular_z), 4),
        "front_distance_m": _round_or_none(front_distance_m),
        "left_distance_m": _round_or_none(left_distance_m),
        "right_distance_m": _round_or_none(right_distance_m),
        "scan_age_sec": _round_or_none(scan_age_sec),
        "updated_at": received_at,
    }


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _lower_percentile(values: list[float], percentile: float = 0.10) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _prefer_left(left: float | None, right: float | None) -> bool | None:
    if left is None and right is None:
        return None
    if right is None:
        return True
    if left is None:
        return False
    return left >= right


def _round_or_none(value: float | None) -> float | None:
    return None if value is None else round(float(value), 4)
