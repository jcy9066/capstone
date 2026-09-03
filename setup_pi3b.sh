#!/usr/bin/env bash
# Configure Raspberry Pi 3 Model B (1GB) for the Dabom robot.
# Target: Ubuntu Server 22.04 arm64 + ROS 2 Humble.
#
# This script:
#   - verifies the board model
#   - enables GPIO14/15 UART
#   - assigns the stable PL011 UART to GPIO14/15 by disabling Bluetooth
#   - removes Linux serial-console ownership of the UART
#   - disables Wi-Fi power saving persistently
#   - applies the agreed Pi 3B camera/UART values to the local .env, if present
#
# It does NOT:
#   - reboot automatically
#   - flash Pico W
#   - send motor/GPIO/serial movement commands
#   - install ROS 2 or camera packages
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

log() {
    printf '[pi3b-setup] %s\n' "$*"
}

die() {
    printf '[pi3b-setup] ERROR: %s\n' "$*" >&2
    exit 1
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        die "Run with sudo: sudo bash raspberry/scripts/setup_pi3b.sh"
    fi
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

backup_once() {
    local path="$1"
    local backup="${path}.bak.dabom_pi3b"

    if [[ ! -e "${backup}" ]]; then
        cp -a -- "${path}" "${backup}"
        log "Backup created: ${backup}"
    fi
}

configure_uart() {
    local config_file cmdline_file temp_file

    config_file="$(find_boot_file config.txt)" \
        || die "config.txt was not found under /boot/firmware or /boot"

    cmdline_file="$(find_boot_file cmdline.txt)" \
        || die "cmdline.txt was not found under /boot/firmware or /boot"

    backup_once "${config_file}"
    backup_once "${cmdline_file}"

    # Remove previous Dabom block and conflicting primary-UART selections.
    temp_file="$(mktemp)"
    awk '
        BEGIN {skip=0}
        /^# DABOM_PI3B_BEGIN$/ {skip=1; next}
        /^# DABOM_PI3B_END$/   {skip=0; next}
        skip == 0 {print}
    ' "${config_file}" > "${temp_file}"

    sed -Ei \
        -e '/^[[:space:]]*enable_uart[[:space:]]*=/d' \
        -e '/^[[:space:]]*dtoverlay[[:space:]]*=[[:space:]]*disable-bt([[:space:]]|$)/d' \
        -e '/^[[:space:]]*dtoverlay[[:space:]]*=[[:space:]]*miniuart-bt([[:space:]]|$)/d' \
        "${temp_file}"

    cat >> "${temp_file}" <<'EOF'

# DABOM_PI3B_BEGIN
[all]
# Use the PL011 UART on GPIO14(TXD)/GPIO15(RXD) for Raspberry Pi <-> Pico W.
enable_uart=1
dtoverlay=disable-bt
# DABOM_PI3B_END
EOF

    cat "${temp_file}" > "${config_file}"
    rm -f -- "${temp_file}"

    # Keep tty1 console, but remove every serial console that can occupy GPIO UART.
    python3 - "${cmdline_file}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8").strip()
tokens = text.split()

blocked = ("console=serial0,", "console=ttyAMA0,", "console=ttyS0,")
tokens = [token for token in tokens if not token.startswith(blocked)]

path.write_text(" ".join(tokens) + "\n", encoding="utf-8")
PY

    # Prevent a serial getty from reopening the UART after boot.
    for unit in serial-getty@ttyAMA0.service serial-getty@ttyS0.service; do
        if systemctl list-unit-files "${unit}" --no-legend 2>/dev/null | grep -q .; then
            systemctl disable --now "${unit}" >/dev/null 2>&1 || true
            log "Disabled ${unit}"
        fi
    done

    # Bluetooth is intentionally unused in this project so PL011 can be dedicated
    # to the Pico W control/encoder link.
    for unit in hciuart.service bluetooth.service; do
        if systemctl list-unit-files "${unit}" --no-legend 2>/dev/null | grep -q .; then
            systemctl disable --now "${unit}" >/dev/null 2>&1 || true
            log "Disabled ${unit}"
        fi
    done

    log "UART configured: PL011 on GPIO14/15 after reboot"
}

ensure_iw() {
    if command -v iw >/dev/null 2>&1; then
        return 0
    fi

    log "'iw' is missing; installing the Ubuntu package required for Wi-Fi power control"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y iw
}

configure_device_groups() {
    local target_user="${SUDO_USER:-}"

    if [[ -z "${target_user}" || "${target_user}" == "root" ]]; then
        log "WARN: Could not determine the normal login user from SUDO_USER"
        log "      Ensure that the Pi login user belongs to the dialout and video groups."
        return 0
    fi

    local -a groups_to_add=()
    local group_name

    for group_name in dialout video render; do
        if getent group "${group_name}" >/dev/null 2>&1; then
            groups_to_add+=("${group_name}")
        fi
    done

    if (( ${#groups_to_add[@]} > 0 )); then
        local joined
        joined="$(IFS=,; printf '%s' "${groups_to_add[*]}")"
        usermod -aG "${joined}" "${target_user}"
        log "Added ${target_user} to device groups: ${joined}"
    fi
}

configure_wifi_power_save() {
    local iw_path service_file

    ensure_iw
    iw_path="$(command -v iw)"
    service_file="/etc/systemd/system/dabom-wifi-powersave.service"

    cat > "${service_file}" <<EOF
[Unit]
Description=Disable Wi-Fi power saving for Dabom Raspberry Pi 3B
After=network.target
Wants=network.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'if ip link show wlan0 >/dev/null 2>&1; then ${iw_path} dev wlan0 set power_save off; fi'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable --now dabom-wifi-powersave.service >/dev/null

    if ip link show wlan0 >/dev/null 2>&1; then
        "${iw_path}" dev wlan0 set power_save off || true
    fi

    log "Wi-Fi power saving configured OFF"
}

set_env_value() {
    local key="$1"
    local value="$2"

    python3 - "${ENV_FILE}" "${key}" "${value}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]

raw = path.read_text(encoding="utf-8")
lines = raw.splitlines()
prefix = key + "="
updated = False

for index, line in enumerate(lines):
    if line.startswith(prefix):
        lines[index] = prefix + value
        updated = True
        break

if not updated:
    lines.append(prefix + value)

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

configure_project_env() {
    if [[ ! -f "${ENV_FILE}" ]]; then
        log "WARN: ${ENV_FILE} does not exist; camera/UART values were not written"
        log "      Create it with: cp .env.example .env"
        log "      Then rerun this setup script."
        return 0
    fi

    # Agreed Raspberry Pi 3B operating profile.
    set_env_value "STREAM_WIDTH" "1280"
    set_env_value "STREAM_HEIGHT" "720"
    set_env_value "STREAM_FPS" "15"
    set_env_value "STREAM_BITRATE" "2500000"
    set_env_value "MOTOR_SERIAL_PORT" "/dev/serial0"
    set_env_value "MOTOR_SERIAL_BAUDRATE" "115200"

    chmod 600 "${ENV_FILE}" || true
    log "Applied Pi 3B camera/UART values to local .env"
}

main() {
    require_root

    local model
    model="$(read_model)"
    log "Detected model: ${model}"

    if [[ "${model}" != *"Raspberry Pi 3 Model B"* ]] || [[ "${model}" == *"Plus"* ]]; then
        die "This setup is only for Raspberry Pi 3 Model B (non-Plus)."
    fi

    if [[ "$(uname -m)" != "aarch64" ]]; then
        die "64-bit Ubuntu is required. Current architecture: $(uname -m)"
    fi

    configure_uart
    configure_device_groups
    configure_wifi_power_save
    configure_project_env

    log "Configuration complete."
    log "A reboot is REQUIRED before UART validation:"
    log "  sudo reboot"
    log "After reboot run:"
    log "  bash raspberry/scripts/validate_pi3b.sh"
}

main "$@"
