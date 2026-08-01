import math
import time
from datetime import datetime, timezone

import requests
import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformException, TransformListener


def stamp_to_iso(stamp):
    seconds = stamp.sec + stamp.nanosec / 1_000_000_000
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace("+00:00", "Z")


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def yaw_from_quaternion(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def rle_encode(values):
    if not values:
        return []
    runs = []
    last = int(values[0])
    count = 1
    for value in values[1:]:
        value = int(value)
        if value == last:
            count += 1
        else:
            runs.append([last, count])
            last = value
            count = 1
    runs.append([last, count])
    return runs


class MapBridge(Node):
    def __init__(self):
        super().__init__("map_bridge")
        self.declare_parameter("robot_id", "pi-01")
        self.declare_parameter("server_base_url", "http://127.0.0.1:21063")
        self.declare_parameter("map_topic", "/map")
        self.declare_parameter("scan_topic", "/scan")
        self.declare_parameter("pose_parent_frame", "map")
        self.declare_parameter("pose_child_frame", "base_link")
        self.declare_parameter("map_publish_period_sec", 1.0)
        self.declare_parameter("pose_publish_period_sec", 0.2)
        self.declare_parameter("scan_publish_period_sec", 0.0)
        self.declare_parameter("request_timeout_sec", 1.0)
        self.declare_parameter("send_map", True)
        self.declare_parameter("send_pose", True)
        self.declare_parameter("send_scan", False)
        self.declare_parameter("max_scan_points", 180)

        self.robot_id = self.get_parameter("robot_id").value
        self.server_base_url = self.get_parameter("server_base_url").value.rstrip("/")
        self.map_topic = self.get_parameter("map_topic").value
        self.scan_topic = self.get_parameter("scan_topic").value
        self.pose_parent_frame = self.get_parameter("pose_parent_frame").value
        self.pose_child_frame = self.get_parameter("pose_child_frame").value
        self.request_timeout_sec = float(self.get_parameter("request_timeout_sec").value)
        self.send_map = bool(self.get_parameter("send_map").value)
        self.send_pose = bool(self.get_parameter("send_pose").value)
        self.send_scan = bool(self.get_parameter("send_scan").value)
        self.max_scan_points = int(self.get_parameter("max_scan_points").value)
        self.latest_map = None
        self.latest_scan = None
        self.last_warning_at = 0.0

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.map_subscription = self.create_subscription(OccupancyGrid, self.map_topic, self.on_map, 1)
        if self.send_scan:
            self.scan_subscription = self.create_subscription(
                LaserScan,
                self.scan_topic,
                self.on_scan,
                qos_profile_sensor_data,
            )
        else:
            self.scan_subscription = None

        map_period = float(self.get_parameter("map_publish_period_sec").value)
        pose_period = float(self.get_parameter("pose_publish_period_sec").value)
        scan_period = float(self.get_parameter("scan_publish_period_sec").value)
        if self.send_map and map_period > 0:
            self.create_timer(map_period, self.publish_map)
        if self.send_pose and pose_period > 0:
            self.create_timer(pose_period, self.publish_pose)
        if self.send_scan and scan_period > 0:
            self.create_timer(scan_period, self.publish_scan)

        self.get_logger().info(
            f"map_bridge ready robot_id={self.robot_id} server={self.server_base_url} "
            f"map_topic={self.map_topic} pose={self.pose_parent_frame}->{self.pose_child_frame}"
        )

    def on_map(self, msg):
        self.latest_map = msg

    def on_scan(self, msg):
        self.latest_scan = msg

    def post_json(self, path, payload):
        url = f"{self.server_base_url}{path}"
        try:
            response = requests.post(url, json=payload, timeout=self.request_timeout_sec)
            if response.status_code >= 400:
                self.warn_throttled(f"POST {path} failed status={response.status_code} body={response.text[:160]}")
                return False
            return True
        except requests.RequestException as exc:
            self.warn_throttled(f"POST {path} failed: {exc}")
            return False

    def warn_throttled(self, message):
        now = time.monotonic()
        if now - self.last_warning_at >= 5.0:
            self.get_logger().warning(message)
            self.last_warning_at = now

    def publish_map(self):
        msg = self.latest_map
        if msg is None:
            return
        payload = {
            "robot_id": self.robot_id,
            "frame_id": msg.header.frame_id or "map",
            "timestamp": stamp_to_iso(msg.header.stamp),
            "bridge_timestamp": now_iso(),
            "resolution": msg.info.resolution,
            "width": msg.info.width,
            "height": msg.info.height,
            "origin": {
                "x": msg.info.origin.position.x,
                "y": msg.info.origin.position.y,
                "z": msg.info.origin.position.z,
                "yaw": yaw_from_quaternion(msg.info.origin.orientation),
            },
            "data_encoding": "rle",
            "data": rle_encode(list(msg.data)),
        }
        self.post_json("/navigation/map", payload)

    def publish_pose(self):
        try:
            transform = self.tf_buffer.lookup_transform(
                self.pose_parent_frame,
                self.pose_child_frame,
                Time(),
            )
        except TransformException as exc:
            self.warn_throttled(
                f"TF lookup failed {self.pose_parent_frame}->{self.pose_child_frame}: {exc}"
            )
            return

        t = transform.transform.translation
        r = transform.transform.rotation
        payload = {
            "robot_id": self.robot_id,
            "frame_id": self.pose_parent_frame,
            "child_frame_id": self.pose_child_frame,
            "timestamp": stamp_to_iso(transform.header.stamp),
            "bridge_timestamp": now_iso(),
            "x": t.x,
            "y": t.y,
            "z": t.z,
            "yaw": yaw_from_quaternion(r),
            "orientation": {"x": r.x, "y": r.y, "z": r.z, "w": r.w},
        }
        self.post_json("/navigation/pose", payload)

    def publish_scan(self):
        msg = self.latest_scan
        if msg is None:
            return
        ranges = list(msg.ranges)
        if self.max_scan_points > 0 and len(ranges) > self.max_scan_points:
            step = max(1, len(ranges) // self.max_scan_points)
            ranges = ranges[::step]
            angle_increment = msg.angle_increment * step
        else:
            angle_increment = msg.angle_increment
        payload = {
            "robot_id": self.robot_id,
            "frame_id": msg.header.frame_id,
            "timestamp": stamp_to_iso(msg.header.stamp),
            "bridge_timestamp": now_iso(),
            "angle_min": msg.angle_min,
            "angle_max": msg.angle_max,
            "angle_increment": angle_increment,
            "range_min": msg.range_min,
            "range_max": msg.range_max,
            "ranges": [None if math.isinf(v) or math.isnan(v) else v for v in ranges],
        }
        self.post_json("/navigation/scan", payload)


def main(args=None):
    rclpy.init(args=args)
    node = MapBridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
