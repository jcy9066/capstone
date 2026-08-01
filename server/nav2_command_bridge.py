from __future__ import annotations

import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class Nav2CommandBridge(Node):
    def __init__(self) -> None:
        super().__init__("nav2_command_bridge")

        self.declare_parameter(
            "cmd_vel_topic",
            "/cmd_vel_nav_dry_run",
        )
        self.declare_parameter("wheel_track_m", 0.201)
        self.declare_parameter("max_wheel_mps", 0.50)
        self.declare_parameter("twist_timeout_sec", 0.50)

        self.cmd_vel_topic = str(
            self.get_parameter("cmd_vel_topic").value
        )
        self.wheel_track_m = float(
            self.get_parameter("wheel_track_m").value
        )
        self.max_wheel_mps = float(
            self.get_parameter("max_wheel_mps").value
        )
        self.twist_timeout_sec = float(
            self.get_parameter("twist_timeout_sec").value
        )

        # 현재 단계에서는 절대로 실제 명령을 전송하지 않는다.
        self.motor_output_enabled = False

        self.last_twist_at = None
        self.last_log_at = 0.0
        self.timed_out = True
        self.received_count = 0
        self.rejected_count = 0

        self.create_subscription(
            Twist,
            self.cmd_vel_topic,
            self.on_twist,
            10,
        )
        self.create_timer(0.05, self.check_timeout)

        self.get_logger().info(
            "nav2_command_bridge ready "
            f"topic={self.cmd_vel_topic} "
            f"wheel_track_m={self.wheel_track_m:.3f} "
            f"max_wheel_mps={self.max_wheel_mps:.3f} "
            "motor_output_enabled=false"
        )

    def on_twist(self, msg: Twist) -> None:
        linear_x = float(msg.linear.x)
        angular_z = float(msg.angular.z)

        if (
            not math.isfinite(linear_x)
            or not math.isfinite(angular_z)
        ):
            self.rejected_count += 1
            self.get_logger().warning(
                "Twist rejected: NaN or Infinity"
            )
            return

        half_track = self.wheel_track_m / 2.0

        left_raw = (
            linear_x
            - angular_z * half_track
        )
        right_raw = (
            linear_x
            + angular_z * half_track
        )

        # 회전 비율을 유지하면서 좌우 속도를 비례 제한한다.
        peak = max(abs(left_raw), abs(right_raw))

        if peak > self.max_wheel_mps:
            scale = self.max_wheel_mps / peak
        else:
            scale = 1.0

        left_mps = left_raw * scale
        right_mps = right_raw * scale

        now = time.monotonic()
        self.last_twist_at = now
        self.timed_out = False
        self.received_count += 1

        # 로그 과다 출력을 막기 위해 0.2초마다 출력한다.
        if now - self.last_log_at >= 0.2:
            self.last_log_at = now

            self.get_logger().info(
                "DRY_RUN "
                f"linear_x={linear_x:.4f} "
                f"angular_z={angular_z:.4f} "
                f"left_mps={left_mps:.4f} "
                f"right_mps={right_mps:.4f} "
                f"limited={scale < 1.0} "
                "would_send=false "
                "motor_output_enabled=false"
            )

    def check_timeout(self) -> None:
        if self.last_twist_at is None or self.timed_out:
            return

        age_sec = (
            time.monotonic()
            - self.last_twist_at
        )

        if age_sec <= self.twist_timeout_sec:
            return

        self.timed_out = True

        self.get_logger().warning(
            "DRY_RUN STOP "
            f"reason=twist_timeout "
            f"age_sec={age_sec:.3f} "
            "left_mps=0.0000 "
            "right_mps=0.0000 "
            "would_send=false"
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Nav2CommandBridge()

    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
