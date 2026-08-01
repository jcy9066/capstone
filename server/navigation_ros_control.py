"""Long-lived ROS 2 control for saved-map loading and AMCL initialization."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

try:
    import rclpy
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from lifecycle_msgs.srv import GetState
    from nav2_msgs.srv import LoadMap
    from nav_msgs.msg import OccupancyGrid
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

    ROS_IMPORT_ERROR: Exception | None = None
except ModuleNotFoundError as exc:  # Allows the web server to run without ROS locally.
    rclpy = None
    PoseWithCovarianceStamped = None
    GetState = None
    LoadMap = None
    OccupancyGrid = None
    SingleThreadedExecutor = None
    Node = None
    DurabilityPolicy = None
    QoSProfile = None
    ReliabilityPolicy = None
    ROS_IMPORT_ERROR = exc


class NavigationRosError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


@dataclass
class _MapObservation:
    sequence: int = 0
    width: int | None = None
    height: int | None = None
    resolution: float | None = None
    origin_x: float | None = None
    origin_y: float | None = None
    received_at: float | None = None


@dataclass
class _AmclObservation:
    sequence: int = 0
    x: float | None = None
    y: float | None = None
    yaw: float | None = None
    received_at: float | None = None


class NavigationRosControl:
    """Owns one ROS node/executor for the lifetime of the FastAPI server."""

    LOAD_MAP_SERVICE = "/map_server/load_map"
    INITIAL_POSE_TOPIC = "/initialpose"
    MAP_TOPIC = "/map"
    AMCL_POSE_TOPIC = "/amcl_pose"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._node = None
        self._executor = None
        self._thread = None
        self._owns_rclpy = False
        self._started = False
        self._load_map_client = None
        self._map_server_state_client = None
        self._amcl_state_client = None
        self._initial_pose_publisher = None
        self._map = _MapObservation()
        self._amcl = _AmclObservation()
        self._last_lifecycle = {"map_server": "unavailable", "amcl": "unavailable"}

    def start(self) -> bool:
        with self._lock:
            if self._started:
                return True
            if ROS_IMPORT_ERROR is not None:
                return False
            if not rclpy.ok():
                rclpy.init(args=None)
                self._owns_rclpy = True

            self._node = Node("navigation_map_control")
            self._executor = SingleThreadedExecutor()
            self._executor.add_node(self._node)
            self._load_map_client = self._node.create_client(LoadMap, self.LOAD_MAP_SERVICE)
            self._map_server_state_client = self._node.create_client(GetState, "/map_server/get_state")
            self._amcl_state_client = self._node.create_client(GetState, "/amcl/get_state")
            self._initial_pose_publisher = self._node.create_publisher(
                PoseWithCovarianceStamped,
                self.INITIAL_POSE_TOPIC,
                10,
            )
            map_qos = QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            )
            self._node.create_subscription(OccupancyGrid, self.MAP_TOPIC, self._on_map, map_qos)
            self._node.create_subscription(PoseWithCovarianceStamped, self.AMCL_POSE_TOPIC, self._on_amcl_pose, 10)
            self._thread = threading.Thread(
                target=self._executor.spin,
                name="navigation-map-ros-executor",
                daemon=True,
            )
            self._thread.start()
            self._started = True
            return True

    def close(self) -> None:
        with self._lock:
            if not self._started:
                return
            executor, thread, node = self._executor, self._thread, self._node
            owns_rclpy = self._owns_rclpy
            self._started = False
            self._executor = None
            self._thread = None
            self._node = None
        if executor is not None:
            try:
                executor.shutdown(timeout_sec=2.0)
            except Exception:
                pass
        if thread is not None:
            thread.join(timeout=2.0)
        if node is not None:
            try:
                node.destroy_node()
            except Exception:
                pass
        if owns_rclpy and rclpy is not None and rclpy.ok():
            try:
                rclpy.shutdown()
            except Exception:
                pass

    def load_map_and_reset_pose(
        self,
        selected_map: Any,
        initial_pose: dict[str, float],
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        self._require_started()
        if progress is not None:
            progress("loading")
        self._raise_if_mapping_mode()
        if not self._load_map_client.wait_for_service(timeout_sec=2.5):
            raise NavigationRosError(
                "MAP_SERVER_UNAVAILABLE",
                "The map server LoadMap service is unavailable.",
            )

        lifecycle = self._refresh_lifecycle_states(timeout_sec=1.0)
        if lifecycle["map_server"] != "active" or lifecycle["amcl"] != "active":
            raise NavigationRosError(
                "LOCALIZATION_NOT_ACTIVE",
                "map_server and AMCL must both be active before loading a map.",
            )

        with self._condition:
            map_sequence = self._map.sequence
            amcl_sequence = self._amcl.sequence

        request = LoadMap.Request()
        request.map_url = str(selected_map.yaml_path)
        response = self._wait_future(
            self._load_map_client.call_async(request),
            timeout_sec=5.0,
            error_code="LOAD_MAP_TIMEOUT",
            message="Timed out while loading the selected map.",
        )
        success_code = getattr(LoadMap.Response, "RESULT_SUCCESS", 0)
        if int(response.result) != int(success_code):
            result_names = {
                getattr(LoadMap.Response, "RESULT_MAP_DOES_NOT_EXIST", 1): "MAP_DOES_NOT_EXIST",
                getattr(LoadMap.Response, "RESULT_INVALID_MAP_DATA", 2): "INVALID_MAP_DATA",
                getattr(LoadMap.Response, "RESULT_INVALID_MAP_METADATA", 3): "INVALID_MAP_METADATA",
                getattr(LoadMap.Response, "RESULT_UNDEFINED_FAILURE", 255): "UNDEFINED_FAILURE",
            }
            error_code = result_names.get(int(response.result), "LOAD_MAP_FAILED")
            raise NavigationRosError(error_code, "map_server rejected the selected map.")

        if progress is not None:
            progress("verifying")
        observed_map = self._wait_for_map(selected_map, map_sequence, timeout_sec=5.0)
        if progress is not None:
            progress("resetting_pose")
        self._publish_initial_pose(initial_pose)
        if progress is not None:
            progress("verifying")
        observed_amcl = self._wait_for_amcl(initial_pose, amcl_sequence, timeout_sec=5.0)

        lifecycle = self._refresh_lifecycle_states(timeout_sec=0.5)
        return {
            "localization": {
                "map_server": lifecycle["map_server"],
                "amcl": lifecycle["amcl"],
                "map_received": True,
                "amcl_pose_received": True,
            },
            "verification": {
                "map": observed_map,
                "amcl_pose": observed_amcl,
            },
        }

    def active_status(self, selected_map: Any | None) -> dict[str, Any]:
        if ROS_IMPORT_ERROR is not None:
            return {
                "available": False,
                "map_server": "unavailable",
                "amcl": "unavailable",
                "load_map_service": False,
                "map_verified": False,
                "amcl_pose_received": False,
            }
        if not self._started:
            return {
                "available": False,
                "map_server": "checking",
                "amcl": "checking",
                "load_map_service": False,
                "map_verified": False,
                "amcl_pose_received": False,
            }
        lifecycle = self._refresh_lifecycle_states(timeout_sec=0.25)
        with self._lock:
            map_matches = selected_map is not None and self._map_matches(selected_map)
            amcl_received = self._amcl.received_at is not None
        return {
            "available": True,
            "map_server": lifecycle["map_server"],
            "amcl": lifecycle["amcl"],
            "load_map_service": self._load_map_client.wait_for_service(timeout_sec=0.05),
            "map_verified": map_matches,
            "amcl_pose_received": amcl_received,
        }

    def _require_started(self) -> None:
        if ROS_IMPORT_ERROR is not None:
            raise NavigationRosError("ROS_UNAVAILABLE", "ROS 2 dependencies are unavailable on this server.", 503)
        if not self._started:
            raise NavigationRosError("ROS_UNAVAILABLE", "The navigation ROS control node is not running.", 503)

    def _raise_if_mapping_mode(self) -> None:
        endpoints = self._node.get_publishers_info_by_topic(self.MAP_TOPIC)
        for endpoint in endpoints:
            source = f"{endpoint.node_namespace}/{endpoint.node_name}".lower()
            if "slam_toolbox" in source:
                raise NavigationRosError(
                    "MAPPING_MODE_ACTIVE",
                    "Map loading is unavailable while SLAM mapping is publishing /map.",
                )

    def _refresh_lifecycle_states(self, timeout_sec: float) -> dict[str, str]:
        map_server = self._get_lifecycle_state(self._map_server_state_client, timeout_sec)
        amcl = self._get_lifecycle_state(self._amcl_state_client, timeout_sec)
        with self._lock:
            self._last_lifecycle = {"map_server": map_server, "amcl": amcl}
            return dict(self._last_lifecycle)

    def _get_lifecycle_state(self, client: Any, timeout_sec: float) -> str:
        if client is None or not client.wait_for_service(timeout_sec=timeout_sec):
            return "unavailable"
        try:
            response = self._wait_future(
                client.call_async(GetState.Request()),
                timeout_sec=max(0.25, timeout_sec),
                error_code="LIFECYCLE_TIMEOUT",
                message="Timed out while reading lifecycle state.",
            )
        except NavigationRosError:
            return "unavailable"
        state = response.current_state
        label = str(getattr(state, "label", "")).lower()
        if label:
            return label
        return "active" if int(getattr(state, "id", 0)) == 3 else "inactive"

    def _wait_future(self, future: Any, timeout_sec: float, error_code: str, message: str) -> Any:
        deadline = time.monotonic() + timeout_sec
        while not future.done() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not future.done():
            raise NavigationRosError(error_code, message, 504)
        try:
            return future.result()
        except Exception as exc:
            raise NavigationRosError("ROS_SERVICE_FAILED", "ROS service request failed.", 502) from exc

    def _wait_for_map(self, selected_map: Any, before_sequence: int, timeout_sec: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_sec
        with self._condition:
            while True:
                if self._map.sequence > before_sequence and self._map_matches(selected_map):
                    return {
                        "width": self._map.width,
                        "height": self._map.height,
                        "resolution": self._map.resolution,
                    }
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise NavigationRosError(
                        "MAP_VERIFICATION_FAILED",
                        "map_server did not publish the requested map metadata.",
                        504,
                    )
                self._condition.wait(timeout=min(remaining, 0.2))

    def _wait_for_amcl(self, initial_pose: dict[str, float], before_sequence: int, timeout_sec: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_sec
        with self._condition:
            while True:
                if self._amcl.sequence > before_sequence and self._amcl_matches(initial_pose):
                    return {
                        "x": self._amcl.x,
                        "y": self._amcl.y,
                        "yaw": self._amcl.yaw,
                    }
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise NavigationRosError(
                        "AMCL_VERIFICATION_FAILED",
                        "AMCL did not confirm an initial pose near the requested location.",
                        504,
                    )
                self._condition.wait(timeout=min(remaining, 0.2))

    def _publish_initial_pose(self, initial_pose: dict[str, float]) -> None:
        message = PoseWithCovarianceStamped()
        message.header.frame_id = "map"
        message.header.stamp = self._node.get_clock().now().to_msg()
        message.pose.pose.position.x = initial_pose["x"]
        message.pose.pose.position.y = initial_pose["y"]
        half_yaw = initial_pose["yaw"] / 2.0
        message.pose.pose.orientation.z = math.sin(half_yaw)
        message.pose.pose.orientation.w = math.cos(half_yaw)
        # 0.25 m^2 for x/y and about 15 degrees squared for yaw.
        message.pose.covariance[0] = 0.25
        message.pose.covariance[7] = 0.25
        message.pose.covariance[35] = math.radians(15.0) ** 2
        self._initial_pose_publisher.publish(message)

    def _on_map(self, message: Any) -> None:
        with self._condition:
            self._map.sequence += 1
            self._map.width = int(message.info.width)
            self._map.height = int(message.info.height)
            self._map.resolution = float(message.info.resolution)
            self._map.origin_x = float(message.info.origin.position.x)
            self._map.origin_y = float(message.info.origin.position.y)
            self._map.received_at = time.monotonic()
            self._condition.notify_all()

    def _on_amcl_pose(self, message: Any) -> None:
        orientation = message.pose.pose.orientation
        yaw = math.atan2(
            2.0 * (orientation.w * orientation.z + orientation.x * orientation.y),
            1.0 - 2.0 * (orientation.y * orientation.y + orientation.z * orientation.z),
        )
        with self._condition:
            self._amcl.sequence += 1
            self._amcl.x = float(message.pose.pose.position.x)
            self._amcl.y = float(message.pose.pose.position.y)
            self._amcl.yaw = yaw
            self._amcl.received_at = time.monotonic()
            self._condition.notify_all()

    def _map_matches(self, selected_map: Any) -> bool:
        if self._map.width != selected_map.width or self._map.height != selected_map.height:
            return False
        if self._map.resolution is None or not math.isclose(self._map.resolution, selected_map.resolution, rel_tol=0.0, abs_tol=1e-6):
            return False
        return (
            self._map.origin_x is not None
            and self._map.origin_y is not None
            and math.isclose(self._map.origin_x, selected_map.origin_x, rel_tol=0.0, abs_tol=1e-5)
            and math.isclose(self._map.origin_y, selected_map.origin_y, rel_tol=0.0, abs_tol=1e-5)
        )

    def _amcl_matches(self, initial_pose: dict[str, float]) -> bool:
        if self._amcl.x is None or self._amcl.y is None or self._amcl.yaw is None:
            return False
        yaw_delta = math.atan2(
            math.sin(self._amcl.yaw - initial_pose["yaw"]),
            math.cos(self._amcl.yaw - initial_pose["yaw"]),
        )
        return (
            abs(self._amcl.x - initial_pose["x"]) <= 0.5
            and abs(self._amcl.y - initial_pose["y"]) <= 0.5
            and abs(yaw_delta) <= math.radians(30.0)
        )
