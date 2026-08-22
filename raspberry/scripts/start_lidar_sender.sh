#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source <(sed 's/\r$//' "$ENV_FILE")
    set +a
fi

source /opt/ros/humble/setup.bash

if [[ -f "$REPO_ROOT/navigation/ros/install/setup.bash" ]]; then
    source "$REPO_ROOT/navigation/ros/install/setup.bash"
fi

: "${ROBOT_ID:?ROBOT_ID is required}"
: "${ROBOT_CONTROL_TOKEN:?ROBOT_CONTROL_TOKEN is required}"
: "${SERVER_BASE_URL:?SERVER_BASE_URL is required}"
: "${LIDAR_SCAN_TOPIC:?LIDAR_SCAN_TOPIC is required}"
: "${LIDAR_WS_RECONNECT_SEC:?LIDAR_WS_RECONNECT_SEC is required}"
: "${LIDAR_SERIAL_PORT:?LIDAR_SERIAL_PORT is required}"
: "${LIDAR_SERIAL_BAUDRATE:?LIDAR_SERIAL_BAUDRATE is required}"
: "${LIDAR_DRIVER_PACKAGE:?LIDAR_DRIVER_PACKAGE is required}"
: "${LIDAR_DRIVER_EXECUTABLE:?LIDAR_DRIVER_EXECUTABLE is required}"
: "${LIDAR_FRAME:?LIDAR_FRAME is required}"
: "${LIDAR_BASE_FRAME:?LIDAR_BASE_FRAME is required}"
: "${LIDAR_X:?LIDAR_X is required}"
: "${LIDAR_Y:?LIDAR_Y is required}"
: "${LIDAR_Z:?LIDAR_Z is required}"
: "${LIDAR_ROLL:?LIDAR_ROLL is required}"
: "${LIDAR_PITCH:?LIDAR_PITCH is required}"
: "${LIDAR_YAW:?LIDAR_YAW is required}"
: "${ROS_LOCALHOST_ONLY:?ROS_LOCALHOST_ONLY is required}"

# ROS2 DDS는 Pi 내부에서만 사용한다.
# Pi → GPU 서버 전송은 WebSocket으로 수행한다.
export PYTHONUNBUFFERED=1

driver_pid=""
sender_pid=""

cleanup() {
    trap - EXIT INT TERM

    for pid in "$sender_pid" "$driver_pid"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done

    for pid in "$sender_pid" "$driver_pid"; do
        if [[ -n "$pid" ]]; then
            wait "$pid" 2>/dev/null || true
        fi
    done
}

on_signal() {
    cleanup
    exit 130
}

trap cleanup EXIT
trap on_signal INT TERM

while [[ ! -e "$LIDAR_SERIAL_PORT" ]]; do
    echo "[lidar] waiting for $LIDAR_SERIAL_PORT"
    sleep 2
done

echo "[lidar] starting driver"
echo "[lidar] port=$LIDAR_SERIAL_PORT"
echo "[lidar] baud=$LIDAR_SERIAL_BAUDRATE"
echo "[lidar] server configured"

ros2 launch patrol_navigation lidar.launch.py \
    serial_port:="$LIDAR_SERIAL_PORT" \
    serial_baudrate:="$LIDAR_SERIAL_BAUDRATE" \
    driver_package:="$LIDAR_DRIVER_PACKAGE" \
    driver_executable:="$LIDAR_DRIVER_EXECUTABLE" \
    frame_id:="$LIDAR_FRAME" \
    base_frame:="$LIDAR_BASE_FRAME" \
    laser_x:="$LIDAR_X" \
    laser_y:="$LIDAR_Y" \
    laser_z:="$LIDAR_Z" \
    laser_roll:="$LIDAR_ROLL" \
    laser_pitch:="$LIDAR_PITCH" \
    laser_yaw:="$LIDAR_YAW" &

driver_pid="$!"

sleep 3

python3 "$REPO_ROOT/raspberry/lidar_scan_sender.py" &
sender_pid="$!"

set +e
wait -n "$driver_pid" "$sender_pid"
exit_status=$?
set -e

echo "[lidar] driver or sender stopped status=$exit_status" >&2
exit "$exit_status"
