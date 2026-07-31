#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
    pwd
)"

cd "$ROOT_DIR"

source /opt/ros/humble/setup.bash

if [[ -f "$ROOT_DIR/navigation/ros/install/setup.bash" ]]; then
    source "$ROOT_DIR/navigation/ros/install/setup.bash"
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
    sed -i 's/\r$//' "$ROOT_DIR/.env"

    set -a
    source "$ROOT_DIR/.env"
    set +a
fi

export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-1}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-27}"

export INFERENCE_ENABLED=false
export VISUALIZATION_ENABLED=false
export MODEL_REQUIRED=false

exec python3 -m uvicorn \
    server.app:app \
    --host 0.0.0.0 \
    --port 21063 \
    --no-access-log
