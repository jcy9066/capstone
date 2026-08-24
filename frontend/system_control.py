"""Authenticated ROS component control routes for the integrated dashboard."""

from __future__ import annotations

import asyncio
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

from server.env_config import env_bool, env_float, env_int, env_text


def attach_system_control_routes(app, navigation_process_control=None) -> None:
    root_dir = Path(__file__).resolve().parents[1]
    log_dir = root_dir / "logs" / "system_control"
    wheel_script = root_dir / "server" / "wheel_odometry.py"
    ros_install_setup = root_dir / "navigation" / "ros" / "install" / "setup.bash"
    component_ids = ("lidar_ros_bridge", "encoder_ros_bridge", "wheel_odometry", "slam_mapping", "map_bridge")
    locks = {component_id: threading.Lock() for component_id in component_ids}

    def server_module():
        module = sys.modules.get("server.app") or sys.modules.get("__main__")
        if module is None:
            raise RuntimeError("Integrated server module is unavailable.")
        return module

    def error(message: str, status_code: int = 400):
        return JSONResponse({"ok": False, "detail": message}, status_code=status_code)

    def access(request, csrf: bool = False):
        if not request.session.get("user"):
            return error("Login required.", 401)
        return server_module().csrf_failure(request) if csrf else None

    def cmdline(pid: int) -> list[str]:
        try:
            raw = (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0")
            return [part.decode("utf-8", errors="replace") for part in raw if part]
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            return []

    def matching_processes(component_id: str) -> list[dict]:
        if not Path("/proc").is_dir():
            return []
        found = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            args = cmdline(pid)
            if component_id == "wheel_odometry":
                match = str(wheel_script) in args or "server/wheel_odometry.py" in args
            elif component_id == "slam_mapping":
                match = any(
                    Path(args[index]).name == "ros2"
                    and args[index + 1:index + 4]
                    == ["launch", "patrol_navigation", "mapping.launch.py"]
                    for index in range(len(args))
                )
            elif component_id == "map_bridge":
                match = any(
                    Path(argument).name == "map_bridge"
                    and "patrol_navigation" in argument
                    for argument in args
                )
            else:
                match = False
            if match:
                found.append({"pid": pid, "args": args})
        return found

    def gpu_status(component_id: str) -> dict:
        labels = {
            "lidar_ros_bridge": ("LiDAR ROS Bridge", "Pi의 LiDAR 데이터를 ROS 2 /scan으로 전달"),
            "encoder_ros_bridge": ("Encoder ROS Bridge", "Pi의 엔코더 데이터를 ROS 2 /wheel_ticks로 전달"),
            "wheel_odometry": ("Wheel Odometry", "엔코더 기반 로봇 위치 변화와 odom TF 계산"),
            "slam_mapping": ("SLAM Mapping", "LiDAR 기반 지도 작성과 Map Bridge 함께 실행"),
            "map_bridge": ("Map Bridge", "단독 실행 시 지도·위치·LiDAR 데이터를 대시보드로 전달"),
        }
        module = server_module()
        label, description = labels[component_id]
        if component_id == "lidar_ros_bridge":
            count, pids = (1 if module.lidar_ros_bridge is not None else 0), []
        elif component_id == "encoder_ros_bridge":
            count, pids = (1 if module.encoder_ros_bridge is not None else 0), []
        elif component_id == "slam_mapping" and navigation_process_control is not None:
            process_status = navigation_process_control.status()
            pids = process_status.get("mapping_pids", [])
            count = len(pids)
        else:
            matches = matching_processes(component_id)
            count, pids = len(matches), [item["pid"] for item in matches]
        return {
            "id": component_id, "label": label, "description": description,
            "state": "off" if count == 0 else "duplicate" if count > 1 else "on",
            "instance_count": count, "duplicate": count > 1, "pids": pids,
            "message": "중복 실행 감지" if count > 1 else None,
        }

    def ros_command(command: list[str]) -> list[str]:
        source_parts = ["source /opt/ros/humble/setup.bash"]
        if ros_install_setup.exists():
            source_parts.append(f"source {shlex.quote(str(ros_install_setup))}")
        source_parts.extend([
            f"export ROS_DOMAIN_ID={shlex.quote(env_text('ROS_DOMAIN_ID'))}",
            f"export ROS_LOCALHOST_ONLY={shlex.quote(env_text('ROS_LOCALHOST_ONLY'))}",
            f"exec {shlex.join(command)}",
        ])
        return ["bash", "-lc", " && ".join(source_parts)]

    def start_bridge(component_id: str) -> None:
        module = server_module()
        if component_id == "lidar_ros_bridge" and module.lidar_ros_bridge is None:
            if module.LidarRosBridge is None:
                raise RuntimeError("LiDAR ROS bridge dependency is unavailable.")
            module.lidar_ros_bridge = module.LidarRosBridge(
                ros_topic=env_text("LIDAR_ROS_TOPIC"),
                base_frame=env_text("LIDAR_BASE_FRAME"),
                lidar_frame=env_text("LIDAR_FRAME"),
                lidar_x=env_float("LIDAR_X"),
                lidar_y=env_float("LIDAR_Y"),
                lidar_z=env_float("LIDAR_Z"),
                lidar_yaw=env_float("LIDAR_YAW"),
                dashboard_max_points=env_int(
                    "LIDAR_DASHBOARD_MAX_POINTS", minimum=1
                ),
                use_source_timestamp=env_bool("LIDAR_USE_SOURCE_TIMESTAMP"),
            )
            module.lidar_ros_bridge.start()
        elif component_id == "encoder_ros_bridge" and module.encoder_ros_bridge is None:
            if module.EncoderRosBridge is None:
                raise RuntimeError("Encoder ROS bridge dependency is unavailable.")
            module.encoder_ros_bridge = module.EncoderRosBridge(
                ros_topic=env_text("ENCODER_ROS_TOPIC")
            )
            module.encoder_ros_bridge.start()

    def stop_bridge(component_id: str) -> None:
        module = server_module()
        if component_id == "lidar_ros_bridge" and module.lidar_ros_bridge is not None:
            module.lidar_ros_bridge.close()
            module.lidar_ros_bridge = None
        elif component_id == "encoder_ros_bridge" and module.encoder_ros_bridge is not None:
            module.encoder_ros_bridge.close()
            module.encoder_ros_bridge = None

    def start_process(component_id: str) -> None:
        if component_id == "wheel_odometry":
            command = [sys.executable, str(wheel_script)]
        elif component_id == "slam_mapping":
            if navigation_process_control is not None:
                navigation_process_control.transition("MAPPING")
                return
            command = [
                "ros2", "launch", "patrol_navigation", "mapping.launch.py",
                "server_base_url:=http://127.0.0.1:21063", "robot_id:=pi-01",
                "start_lidar:=false", "start_fake_odom:=false", "start_rviz:=false",
            ]
        elif component_id == "map_bridge":
            command = [
                "ros2", "run", "patrol_navigation", "map_bridge", "--ros-args",
                "-p", "robot_id:=pi-01",
                "-p", "server_base_url:=http://127.0.0.1:21063",
                "-p", "map_topic:=/map",
                "-p", "scan_topic:=/scan",
                "-p", "pose_parent_frame:=map",
                "-p", "pose_child_frame:=base_link",
            ]
        else:
            raise KeyError(component_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / f"{component_id}.log").open("ab") as log_file:
            subprocess.Popen(
                ros_command(command), cwd=root_dir, stdout=log_file,
                stderr=subprocess.STDOUT, start_new_session=True,
            )
        time.sleep(0.5)
        if gpu_status(component_id)["instance_count"] == 0:
            raise RuntimeError(f"{component_id} failed to start; check logs/system_control/{component_id}.log")

    def stop_processes(component_id: str, keep_one: bool = False) -> None:
        if component_id == "slam_mapping" and navigation_process_control is not None:
            if keep_one:
                navigation_process_control.transition("MAPPING")
            else:
                navigation_process_control.stop("MAPPING")
            return
        matches = matching_processes(component_id)
        targets = matches[1:] if keep_one else matches
        for item in targets:
            try:
                if os.getpgid(item["pid"]) == item["pid"]:
                    os.killpg(item["pid"], signal.SIGTERM)
                else:
                    os.kill(item["pid"], signal.SIGTERM)
            except ProcessLookupError:
                continue
        time.sleep(0.3)
        target_pids = {item["pid"] for item in targets}
        for item in matching_processes(component_id):
            if item["pid"] not in target_pids:
                continue
            try:
                if os.getpgid(item["pid"]) == item["pid"]:
                    os.killpg(item["pid"], signal.SIGKILL)
                else:
                    os.kill(item["pid"], signal.SIGKILL)
            except ProcessLookupError:
                continue

    def control_gpu(component_id: str, action: str) -> dict:
        with locks[component_id]:
            status = gpu_status(component_id)
            if action == "start" and status["instance_count"] == 0:
                start_bridge(component_id) if component_id.endswith("bridge") else start_process(component_id)
            elif action == "stop":
                stop_bridge(component_id) if component_id.endswith("bridge") else stop_processes(component_id)
            elif action == "normalize" and not component_id.endswith("bridge"):
                stop_processes(component_id, keep_one=True)
            return gpu_status(component_id)

    async def payload() -> dict:
        module = server_module()
        pi_connected = await module.connections.is_connected(module.SERVER_ROBOT_ID)
        return {
            "ok": True, "updated_at": datetime.now(timezone.utc).isoformat(),
            "gpu": [gpu_status(component_id) for component_id in component_ids],
            "pi": [{
                "id": "lidar_ros", "label": "LiDAR ROS Service", "description": "Pi에서 LiDAR 스캔 데이터를 수집",
                "state": "unreachable", "instance_count": None, "duplicate": False,
                "reachable": pi_connected, "control_available": False,
                "message": "현재 Pi 원격 서비스 제어를 지원하지 않음" if pi_connected else "Pi 연결 끊김: 상태 확인 불가",
            }],
        }

    @app.get("/api/system-control/status")
    async def get_system_control_status(request: Request):
        denied = access(request)
        return denied if denied else await payload()

    @app.post("/api/system-control/gpu/{component_id}/{action}")
    async def control_gpu_system_component(component_id: str, action: str, request: Request):
        denied = access(request, csrf=True)
        if denied:
            return denied
        if component_id not in component_ids or action not in {"start", "stop", "normalize"}:
            return error("Invalid system control request.", 404)
        try:
            component = await asyncio.to_thread(control_gpu, component_id, action)
            return {"ok": True, "component": component, "updated_at": datetime.now(timezone.utc).isoformat()}
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            return error(str(exc), 500)

    @app.post("/api/system-control/pi/{component_id}/{action}")
    async def control_pi_system_component(component_id: str, action: str, request: Request):
        denied = access(request, csrf=True)
        if denied:
            return denied
        return error("Pi system service control is unavailable until its control agent supports it.", 409)
