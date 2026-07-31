#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

if [[ -f "$ENV_FILE" ]]; then
    sed -i 's/\r$//' "$ENV_FILE"

    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

source /opt/ros/humble/setup.bash

if [[ -f "$REPO_ROOT/navigation/ros/install/setup.bash" ]]; then
    source "$REPO_ROOT/navigation/ros/install/setup.bash"
fi

export ROBOT_ID="${ROBOT_ID:-pi-01}"
export SERVER_BASE_URL="${SERVER_BASE_URL:-http://100.100.248.122:21063}"

if [[ -z "${LIDAR_WS_URL:-}" ]]; then
    case "$SERVER_BASE_URL" in
        https://*)
            WS_BASE_URL="wss://${SERVER_BASE_URL#https://}"
            ;;
        http://*)
            WS_BASE_URL="ws://${SERVER_BASE_URL#http://}"
            ;;
        *)
            echo "[lidar] invalid SERVER_BASE_URL: $SERVER_BASE_URL" >&2
            exit 1
            ;;
    esac

    export LIDAR_WS_URL="${WS_BASE_URL%/}/ws/sensors/${ROBOT_ID}/lidar"
fi

export LIDAR_SCAN_TOPIC="${LIDAR_SCAN_TOPIC:-/scan}"
export LIDAR_WS_RECONNECT_SEC="${LIDAR_WS_RECONNECT_SEC:-1.0}"

export LIDAR_SERIAL_PORT="${LIDAR_SERIAL_PORT:-/dev/ttyUSB0}"
export LIDAR_SERIAL_BAUDRATE="${LIDAR_SERIAL_BAUDRATE:-115200}"

export LIDAR_DRIVER_PACKAGE="${LIDAR_DRIVER_PACKAGE:-sllidar_ros2}"
export LIDAR_DRIVER_EXECUTABLE="${LIDAR_DRIVER_EXECUTABLE:-sllidar_node}"

# ROS2 DDS는 Pi 내부에서만 사용한다.
# Pi → GPU 서버 전송은 WebSocket으로 수행한다.
export ROS_LOCALHOST_ONLY=1
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
echo "[lidar] websocket=$LIDAR_WS_URL"

ros2 launch patrol_navigation lidar.launch.py \
    serial_port:="$LIDAR_SERIAL_PORT" \
    serial_baudrate:="$LIDAR_SERIAL_BAUDRATE" \
    driver_package:="$LIDAR_DRIVER_PACKAGE" \
    driver_executable:="$LIDAR_DRIVER_EXECUTABLE" \
    frame_id:=laser \
    base_frame:=base_link \
    laser_x:=0.0 \
    laser_y:=0.0 \
    laser_z:=0.12 \
    laser_roll:=0.0 \
    laser_pitch:=0.0 \
    laser_yaw:=0.0 &

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
