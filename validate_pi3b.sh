#!/usr/bin/env bash
# Read-only validation for the Dabom Raspberry Pi 3 Model B runtime.
#
# No motor command, GPIO mutation, Pico flash, or UART write is performed.
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

pass() {
    PASS_COUNT=$((PASS_COUNT + 1))
    printf '[PASS] %s\n' "$*"
}

warn() {
    WARN_COUNT=$((WARN_COUNT + 1))
    printf '[WARN] %s\n' "$*"
}

fail() {
    FAIL_COUNT=$((FAIL_COUNT + 1))
    printf '[FAIL] %s\n' "$*"
}

read_model() {
    if [[ -r /proc/device-tree/model ]]; then
        tr -d '\0' < /proc/device-tree/model
    else
        printf 'unknown'
    fi
}

find_boot_file() {
    local name="$1"
    local candidate

    for candidate in \
        "/boot/firmware/${name}" \
        "/boot/${name}"
    do
        if [[ -f "${candidate}" ]]; then
            printf '%s' "${candidate}"
            return 0
        fi
    done

    return 1
}

env_value() {
    local key="$1"

    if [[ ! -f "${ENV_FILE}" ]]; then
        return 1
    fi

    awk -F= -v key="${key}" '
        $1 == key {
            sub(/^[^=]*=/, "", $0)
            gsub(/\r$/, "", $0)
            print $0
            exit
        }
    ' "${ENV_FILE}"
}

check_platform() {
    local model arch mem_kib mem_mib os_id os_version

    model="$(read_model)"
    if [[ "${model}" == *"Raspberry Pi 3 Model B"* ]] && [[ "${model}" != *"Plus"* ]]; then
        pass "Board model: ${model}"
    else
        fail "Expected Raspberry Pi 3 Model B (non-Plus), got: ${model}"
    fi

    arch="$(uname -m)"
    if [[ "${arch}" == "aarch64" ]]; then
        pass "Architecture: aarch64"
    else
        fail "Expected aarch64, got: ${arch}"
    fi

    mem_kib="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null)"
    mem_kib="${mem_kib:-0}"
    mem_mib=$((mem_kib / 1024))
    if (( mem_mib >= 800 && mem_mib <= 1100 )); then
        pass "RAM class: approximately 1GB (${mem_mib} MiB visible)"
    else
        warn "Unexpected visible RAM for a 1GB Pi: ${mem_mib} MiB"
    fi

    os_id=""
    os_version=""
    if [[ -r /etc/os-release ]]; then
        # shellcheck disable=SC1091
        source /etc/os-release
        os_id="${ID:-}"
        os_version="${VERSION_ID:-}"
    fi

    if [[ "${os_id}" == "ubuntu" && "${os_version}" == "22.04" ]]; then
        pass "OS: Ubuntu 22.04"
    else
        fail "Expected Ubuntu 22.04, got: ${os_id:-unknown} ${os_version:-unknown}"
    fi
}

check_uart() {
    local config_file cmdline_file serial_target

    config_file="$(find_boot_file config.txt 2>/dev/null || true)"
    cmdline_file="$(find_boot_file cmdline.txt 2>/dev/null || true)"

    if [[ -n "${config_file}" ]]; then
        if grep -Eq '^[[:space:]]*enable_uart[[:space:]]*=[[:space:]]*1[[:space:]]*$' "${config_file}"; then
            pass "UART enabled in ${config_file}"
        else
            fail "enable_uart=1 is missing from ${config_file}"
        fi

        if grep -Eq '^[[:space:]]*dtoverlay[[:space:]]*=[[:space:]]*disable-bt[[:space:]]*$' "${config_file}"; then
            pass "Bluetooth overlay disabled; PL011 can be primary UART"
        else
            fail "dtoverlay=disable-bt is missing from ${config_file}"
        fi
    else
        fail "Raspberry Pi config.txt not found"
    fi

    if [[ -n "${cmdline_file}" ]]; then
        if grep -Eq '(^|[[:space:]])console=(serial0|ttyAMA0|ttyS0),' "${cmdline_file}"; then
            fail "Serial console still owns a UART in ${cmdline_file}"
        else
            pass "Serial console is not using GPIO UART"
        fi
    else
        fail "Raspberry Pi cmdline.txt not found"
    fi

    if [[ -e /dev/serial0 ]]; then
        serial_target="$(readlink -f /dev/serial0 2>/dev/null || true)"
        if [[ "${serial_target}" == "/dev/ttyAMA0" ]]; then
            pass "/dev/serial0 -> ttyAMA0 (PL011)"
        else
            fail "/dev/serial0 is not PL011 after reboot: ${serial_target:-unknown}"
        fi
    else
        fail "/dev/serial0 does not exist"
    fi

    for unit in hciuart.service bluetooth.service; do
        if systemctl is-active --quiet "${unit}" 2>/dev/null; then
            fail "${unit} is active"
        else
            pass "${unit} is not active"
        fi
    done
}

check_wifi() {
    local iw_path link_info power_info freq

    if ! ip link show wlan0 >/dev/null 2>&1; then
        fail "wlan0 interface not found"
        return
    fi
    pass "wlan0 interface exists"

    iw_path="$(command -v iw 2>/dev/null || true)"
    if [[ -z "${iw_path}" ]]; then
        fail "'iw' command not installed"
        return
    fi

    power_info="$("${iw_path}" dev wlan0 get power_save 2>/dev/null || true)"
    if grep -qi 'off' <<< "${power_info}"; then
        pass "Wi-Fi power saving: OFF"
    else
        warn "Wi-Fi power saving is not confirmed OFF: ${power_info:-unknown}"
    fi

    if systemctl is-enabled --quiet dabom-wifi-powersave.service 2>/dev/null; then
        pass "Persistent Wi-Fi power-save service is enabled"
    else
        warn "dabom-wifi-powersave.service is not enabled"
    fi

    link_info="$("${iw_path}" dev wlan0 link 2>/dev/null || true)"
    if grep -q 'Connected to' <<< "${link_info}"; then
        pass "Wi-Fi is connected"

        freq="$(awk '/freq:/ {print $2; exit}' <<< "${link_info}")"
        if [[ "${freq}" =~ ^[0-9]+$ ]] && (( freq >= 2400 && freq < 2500 )); then
            pass "Wi-Fi band: 2.4GHz (${freq} MHz)"
        else
            warn "Connected Wi-Fi frequency could not be confirmed as 2.4GHz: ${freq:-unknown}"
        fi
    else
        warn "Wi-Fi is not currently associated with an AP"
    fi
}

check_runtime() {
    local current_groups
    current_groups="$(id -nG 2>/dev/null || true)"

    if grep -qw dialout <<< "${current_groups}"; then
        pass "Current user belongs to dialout"
    else
        fail "Current user is not in dialout; UART/LiDAR serial access may fail"
    fi

    if grep -qw video <<< "${current_groups}"; then
        pass "Current user belongs to video"
    else
        warn "Current user is not in video; camera access should be verified"
    fi

    if [[ -f /opt/ros/humble/setup.bash ]]; then
        pass "ROS 2 Humble setup exists"
        if bash -lc 'source /opt/ros/humble/setup.bash && command -v ros2 >/dev/null 2>&1'; then
            pass "ROS 2 CLI is available"
        else
            fail "ROS 2 CLI is unavailable after sourcing Humble"
        fi
    else
        fail "/opt/ros/humble/setup.bash not found"
    fi

    if python3 - <<'PY' >/dev/null 2>&1
import dotenv
import requests
import serial
import websockets
PY
    then
        pass "Pi Python dependencies are importable"
    else
        fail "Missing Pi Python dependencies; install raspberry/requirements.txt"
    fi

    if command -v rpicam-vid >/dev/null 2>&1; then
        pass "rpicam-vid is available"
    else
        fail "rpicam-vid is not installed or not in PATH"
    fi

    if [[ -e /dev/ttyUSB0 ]]; then
        pass "RPLIDAR serial device exists: /dev/ttyUSB0"
    else
        warn "RPLIDAR /dev/ttyUSB0 not found; connect the LiDAR and rerun"
    fi

    if [[ -r /dev/serial0 && -w /dev/serial0 ]]; then
        pass "Current user can read/write /dev/serial0"
    else
        warn "Current user lacks read/write access to /dev/serial0 (or device is unavailable)"
    fi
}

check_camera() {
    local output

    if ! command -v rpicam-vid >/dev/null 2>&1; then
        return
    fi

    output="$(timeout 8 rpicam-vid --list-cameras 2>&1 || true)"
    if grep -qi 'ov5647' <<< "${output}"; then
        pass "OV5647 camera detected"
    else
        warn "OV5647 was not detected by rpicam-vid --list-cameras"
    fi
}

check_env() {
    local key expected actual
    local -a pairs=(
        "STREAM_WIDTH:1280"
        "STREAM_HEIGHT:720"
        "STREAM_FPS:15"
        "STREAM_BITRATE:2500000"
        "MOTOR_SERIAL_PORT:/dev/serial0"
        "MOTOR_SERIAL_BAUDRATE:115200"
    )

    if [[ ! -f "${ENV_FILE}" ]]; then
        fail "${ENV_FILE} does not exist"
        return
    fi

    pass ".env exists"

    for item in "${pairs[@]}"; do
        key="${item%%:*}"
        expected="${item#*:}"
        actual="$(env_value "${key}" 2>/dev/null || true)"

        if [[ "${actual}" == "${expected}" ]]; then
            pass ".env ${key}=${expected}"
        else
            fail ".env ${key}: expected '${expected}', got '${actual:-missing}'"
        fi
    done
}

print_resource_snapshot() {
    local mem_available_kib swap_total_kib

    mem_available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo 2>/dev/null)"
    swap_total_kib="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo 2>/dev/null)"
    mem_available_kib="${mem_available_kib:-0}"
    swap_total_kib="${swap_total_kib:-0}"

    printf '\n[INFO] Current available RAM: %d MiB\n' "$((mem_available_kib / 1024))"
    printf '[INFO] Current swap total: %d MiB (swap/zram is not required by this migration)\n' "$((swap_total_kib / 1024))"
}

main() {
    printf '=== Dabom Raspberry Pi 3B validation ===\n'

    check_platform
    check_uart
    check_wifi
    check_runtime
    check_camera
    check_env
    print_resource_snapshot

    printf '\n=== Result: PASS=%d WARN=%d FAIL=%d ===\n' \
        "${PASS_COUNT}" "${WARN_COUNT}" "${FAIL_COUNT}"

    if (( FAIL_COUNT > 0 )); then
        printf 'Static/runtime validation FAILED. Resolve FAIL items before robot integration testing.\n'
        exit 1
    fi

    if (( WARN_COUNT > 0 )); then
        printf 'Core validation passed with warnings. Connect/verify warned hardware before driving.\n'
    else
        printf 'Core validation passed. Proceed to staged hardware integration testing.\n'
    fi
}

main "$@"
