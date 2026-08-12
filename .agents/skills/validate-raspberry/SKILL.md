---
name: validate-raspberry
description: Validate Raspberry Pi, Pico W, UART, motor-control, encoder, timeout, and failsafe changes in dabom_capstone. Use when raspberry/ code or the Pi-Pico protocol changes. Do not use for server-only, dashboard-only, or ROS-only changes.
---

# Validate Raspberry

Validate Raspberry Pi and Pico W code together whenever their communication or control behavior changes.

## Required Reference

Read:

- `references/uart_protocol.md`

## Scope

Inspect:

- `raspberry/robot_command_client.py`
- `raspberry/controllers/motor_controller.py`
- `raspberry/pico_w_sdk/main.c`
- `raspberry/pico_w_sdk/CMakeLists.txt`
- related tests and configuration

## Procedure

1. Identify changed Pi commands, Pico parser branches, responses, and events.
2. Compare both sides of every changed UART message.
3. Verify UART settings:
   - baud rate
   - line ending
   - encoding
   - timeout
   - receive buffer
4. Verify supported protocol messages:
   - `PING`
   - `STOP`
   - `MOVE`
   - `DRIVE`
   - `ENC_RESET`
   - `ENC_STREAM`
   - `EVENT,ENC`
5. Verify argument count, order, type, and valid range.
6. Verify encoder order and timestamp handling.
7. Verify communication failure leads to a safe stop.
8. Verify speed values are bounded before motor output.
9. Verify GPIO pin assignments do not conflict.
10. Run the deterministic validator:

```bash
python3 .agents/skills/validate-raspberry/scripts/validate_uart_protocol.py
```
11. Run Python syntax checks and Pico SDK build checks when toolchains are available.
12. Report static, build, loopback, and real-hardware validation separately.

## Safety Checks
- command timeout remains active
- malformed commands stop motors
- disconnected server cannot leave stale movement active
- zero-speed commands stop output
- encoder stream cannot block command processing
- speaker and MOSFET controls do not conflict with motor or encoder pins

## Restrictions
- Do not open a real serial device for movement commands.
- Do not change GPIO output.
- Do not flash the Pico W.
- Do not run OpenOCD.
- Do not power or drive motors.
- Do not claim real UART or motor success from static validation.
- Do not modify Git state.
