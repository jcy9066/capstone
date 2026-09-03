---
name: validate-raspberry
description: Validate Raspberry Pi 3B/Pico/UART/motor/encoder/failsafe and Pi runtime configuration paths.
---

# Validate Raspberry

Read `references/uart_protocol.md`.

Current Raspberry Pi target:

```text
Raspberry Pi 3 Model B (1GB)
Ubuntu Server 22.04 arm64
Wi-Fi: 2.4GHz
UART: /dev/serial0 -> PL011 ttyAMA0
GPIO14 TX / GPIO15 RX
115200 8N1
```

Pi 3B provisioning and validation files:

```text
raspberry/scripts/setup_pi3b.sh
raspberry/scripts/validate_pi3b.sh
```

## Procedure

1. Delegate the current Pi/Pico/runtime-config and safety diff to `hardware_reviewer`; reuse a matching result.
2. If Pi/Pico UART code changed, compare both sides of each changed command/event, baudrate, framing, timeout and failsafe contract.
3. If `raspberry/scripts/setup_pi3b.sh` or `validate_pi3b.sh` exists or changed, verify the Pi 3B contract:
   - board target is Raspberry Pi 3 Model B, non-Plus
   - OS architecture target is `aarch64`
   - `enable_uart=1`
   - `dtoverlay=disable-bt`
   - Linux serial console does not own `serial0`, `ttyAMA0` or `ttyS0`
   - expected runtime target is `/dev/serial0 -> /dev/ttyAMA0`
   - Wi-Fi power saving is disabled persistently
   - camera profile is 1280x720, 15 FPS, 2.5 Mbps
   - UART env values remain `/dev/serial0`, 115200
4. Run static shell validation when Bash is available:
   `bash -n raspberry/scripts/setup_pi3b.sh raspberry/scripts/validate_pi3b.sh`
5. Run protocol validation:
   `python .agents/skills/validate-raspberry/scripts/validate_uart_protocol.py`
6. Run affected Python/tests in quiet/RTK mode when available.
7. Build Pico SDK only when the toolchain is available and the firmware changed.
8. Separate static/build/mock results from real Pi 3B/UART/hardware results.
9. Only when the current environment is the actual Pi 3B and the user explicitly requests device validation, run:
   `bash raspberry/scripts/validate_pi3b.sh`

## Context Budget

Use targeted search/partial reads. Do not return full firmware/source/build logs or successful
test output. Return protocol mismatches, Pi 3B configuration mismatches, safety issues,
evidence, and skipped hardware checks.

## Restrictions

- Do not execute `raspberry/scripts/setup_pi3b.sh` automatically. It changes boot/UART/Bluetooth/Wi-Fi system state.
- No real serial movement, GPIO output, motor/speaker drive, firmware flash, OpenOCD,
  Git remote/history mutation, or `test_reviewer` delegation here.
- Do not claim `/dev/serial0 -> ttyAMA0`, camera detection, Wi-Fi association, ROS runtime,
  or connected LiDAR as PASS unless verified on the actual Pi 3B.
