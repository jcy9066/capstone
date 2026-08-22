#!/usr/bin/env bash

set -Eeo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ -f "${PROJECT_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source <(sed 's/\r$//' "${PROJECT_DIR}/.env")
    set +a
fi

: "${SERVER_HOST:?SERVER_HOST is required}"
: "${SERVER_PORT:?SERVER_PORT is required}"
: "${ROS_DOMAIN_ID:?ROS_DOMAIN_ID is required}"
: "${ENCODER_ROS_ENABLE:?ENCODER_ROS_ENABLE is required}"
: "${WHEEL_DIAMETER_M:?WHEEL_DIAMETER_M is required}"
: "${WHEEL_TRACK_M:?WHEEL_TRACK_M is required}"
: "${ENCODER_TICKS_PER_REV:?ENCODER_TICKS_PER_REV is required}"
: "${WHEEL_TICKS_TOPIC:?WHEEL_TICKS_TOPIC is required}"
: "${ODOM_TOPIC:?ODOM_TOPIC is required}"
: "${ODOM_FRAME:?ODOM_FRAME is required}"
: "${BASE_FRAME:?BASE_FRAME is required}"

SERVER_PID=""
ODOM_PID=""

cleanup() {
    local exit_code=$?

    trap - EXIT INT TERM

    echo
    echo "[gpu-stack] 종료 중..."

    if [[ -n "${ODOM_PID}" ]] && kill -0 "${ODOM_PID}" 2>/dev/null; then
        kill "${ODOM_PID}" 2>/dev/null || true
    fi

    if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
        kill "${SERVER_PID}" 2>/dev/null || true
    fi

    if [[ -n "${ODOM_PID}" ]]; then
        wait "${ODOM_PID}" 2>/dev/null || true
    fi

    if [[ -n "${SERVER_PID}" ]]; then
        wait "${SERVER_PID}" 2>/dev/null || true
    fi

    echo "[gpu-stack] FastAPI 및 wheel odometry 종료 완료"
    exit "${exit_code}"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
    echo "[gpu-stack] ROS2 Humble을 찾을 수 없습니다."
    exit 1
fi

set +u
source /opt/ros/humble/setup.bash
set -u

export ROS_DOMAIN_ID

# FastAPI encoder → ROS2 /wheel_ticks bridge
export ENCODER_ROS_ENABLE

# 실제 바닥 주행으로 보정한 odometry 값
export WHEEL_DIAMETER_M
export WHEEL_TRACK_M
export ENCODER_TICKS_PER_REV

export WHEEL_TICKS_TOPIC
export ODOM_TOPIC
export ODOM_FRAME
export BASE_FRAME

cd "${PROJECT_DIR}"

# Starlette StaticFiles는 디렉터리가 없으면 서버 시작에 실패한다.
mkdir -p "${PROJECT_DIR}/frontend/services/static"

if [[ ! -d "${PROJECT_DIR}/frontend/templates" ]]; then
    echo "[gpu-stack] frontend/templates 디렉터리가 없습니다."
    exit 1
fi

echo "[gpu-stack] PROJECT_DIR=${PROJECT_DIR}"
echo "[gpu-stack] ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"
echo "[gpu-stack] SERVER=http://${SERVER_HOST}:${SERVER_PORT}"
echo "[gpu-stack] ENCODER_TICKS_PER_REV=${ENCODER_TICKS_PER_REV}"

echo "[gpu-stack] FastAPI 서버 시작"

python3 -m uvicorn \
    server.app:app \
    --host "${SERVER_HOST}" \
    --port "${SERVER_PORT}" &

SERVER_PID=$!

sleep 1

if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
    echo "[gpu-stack] FastAPI 서버 시작 실패"
    wait "${SERVER_PID}" || true
    exit 1
fi

echo "[gpu-stack] wheel odometry 시작"

python3 server/wheel_odometry.py &

ODOM_PID=$!

sleep 1

if ! kill -0 "${ODOM_PID}" 2>/dev/null; then
    echo "[gpu-stack] wheel odometry 시작 실패"
    wait "${ODOM_PID}" || true
    exit 1
fi

echo
echo "[gpu-stack] 실행 완료"
echo "[gpu-stack] FastAPI PID=${SERVER_PID}"
echo "[gpu-stack] Odometry PID=${ODOM_PID}"
echo "[gpu-stack] 종료: Ctrl+C"
echo

set +e
wait -n "${SERVER_PID}" "${ODOM_PID}"
STATUS=$?
set -e

echo "[gpu-stack] 구성 요소 하나가 종료되었습니다."
exit "${STATUS}"
