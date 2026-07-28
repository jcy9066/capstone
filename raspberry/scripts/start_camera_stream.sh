#!/usr/bin/env bash
# Push the Raspberry Pi camera's H.264 elementary stream to the existing
# FastAPI endpoint. This script intentionally does not start an RTSP server.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

SERVER_BASE_URL="${SERVER_BASE_URL:-http://100.100.248.122:21063}"
ROBOT_ID="${ROBOT_ID:-pi-01}"
STREAM_WIDTH="${STREAM_WIDTH:-640}"
STREAM_HEIGHT="${STREAM_HEIGHT:-480}"
STREAM_FPS="${STREAM_FPS:-15}"
STREAM_INFER="${STREAM_INFER:-false}"
STREAM_RETRY_SEC="${STREAM_RETRY_SEC:-3}"
CURL_CONNECT_TIMEOUT_SEC="${CURL_CONNECT_TIMEOUT_SEC:-5}"
STREAM_URL="${SERVER_BASE_URL%/}/stream/h264?robot_id=${ROBOT_ID}&infer=${STREAM_INFER}"

runtime_dir=""
camera_pid=""
curl_pid=""

cleanup() {
    trap - EXIT INT TERM
    for pid in "$camera_pid" "$curl_pid"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    for pid in "$camera_pid" "$curl_pid"; do
        if [[ -n "$pid" ]]; then
            wait "$pid" 2>/dev/null || true
        fi
    done
    if [[ -n "$runtime_dir" && -d "$runtime_dir" ]]; then
        rm -rf -- "$runtime_dir"
    fi
}

on_signal() {
    cleanup
    exit 130
}
trap cleanup EXIT
trap on_signal INT TERM

stream_once() {
    runtime_dir="$(mktemp -d "${TMPDIR:-/tmp}/dabom-h264.XXXXXX")"
    local fifo_path="$runtime_dir/camera.h264"
    mkfifo "$fifo_path"

    rpicam-vid \
        -t 0 \
        --nopreview \
        --codec h264 \
        --inline \
        --width "$STREAM_WIDTH" \
        --height "$STREAM_HEIGHT" \
        --framerate "$STREAM_FPS" \
        -o "$fifo_path" &
    camera_pid="$!"

    curl \
        --fail \
        --silent \
        --show-error \
        --http1.1 \
        --no-buffer \
        --connect-timeout "$CURL_CONNECT_TIMEOUT_SEC" \
        --request POST \
        --upload-file "$fifo_path" \
        --header "Content-Type: video/H264" \
        --header "Transfer-Encoding: chunked" \
        "$STREAM_URL" &
    curl_pid="$!"

    local curl_status=0
    if wait "$curl_pid"; then
        curl_status=0
    else
        curl_status=$?
    fi
    curl_pid=""

    if kill -0 "$camera_pid" 2>/dev/null; then
        kill "$camera_pid" 2>/dev/null || true
    fi
    wait "$camera_pid" 2>/dev/null || true
    camera_pid=""
    rm -rf -- "$runtime_dir"
    runtime_dir=""
    return "$curl_status"
}

echo "[camera-stream] endpoint=$STREAM_URL width=${STREAM_WIDTH} height=${STREAM_HEIGHT} fps=${STREAM_FPS} infer=${STREAM_INFER}"
while true; do
    if stream_once; then
        echo "[camera-stream] stream ended; reconnecting in ${STREAM_RETRY_SEC}s" >&2
    else
        echo "[camera-stream] upload failed; reconnecting in ${STREAM_RETRY_SEC}s" >&2
    fi
    sleep "$STREAM_RETRY_SEC"
done
