---
name: validate-raspberry
description: Validate Raspberry Pi, Pico W, UART, motor-control, encoder, timeout, and failsafe changes in dabom_capstone. Use when raspberry/ code or the Pi-Pico protocol changes. Delegate protocol and safety review to hardware_reviewer. Do not use for server-only, dashboard-only, or ROS-only changes.
---

# Validate Raspberry

Validate Raspberry Pi and Pico W code together using delegated read-only hardware/protocol review plus deterministic checks available to the Primary/Main Agent.

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

## Mandatory Sub-Agent Delegation

1. Read the root `AGENTS.md`.
2. When running in the Primary/Main Agent thread, delegate Pi/Pico protocol and safety review to `hardware_reviewer`.
3. Ask `hardware_reviewer` to inspect the current working-tree diff and verify:
   - Pi command generation and Pico parser compatibility
   - UART settings and message formats
   - encoder event fields and timestamps
   - timeout and failsafe behavior
   - speed bounds and malformed-command handling
   - GPIO pin conflicts and unsafe initial states
4. If a `hardware_reviewer` result already covers the same current working-tree diff and Raspberry/Pico scope, reuse it instead of spawning a duplicate.
5. If the current thread is already `hardware_reviewer`, do not spawn another `hardware_reviewer`; perform the assigned read-only review and return findings to the parent.
6. The Primary/Main Agent may run deterministic validators and toolchain checks while `hardware_reviewer` is working when those tasks are independent.
7. The Primary/Main Agent must wait for the reviewer result before concluding `validate-raspberry`.

## Reviewer Checks

The `hardware_reviewer` performs the following read-only checks:

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
10. Return file and symbol evidence for findings.

## Primary/Main Agent Validation

The Primary/Main Agent performs deterministic and environment-dependent checks:

1. Run the deterministic validator:

```bash
python3 .agents/skills/validate-raspberry/scripts/validate_uart_protocol.py
```

2. Run Python syntax checks.
3. Run Pico SDK build checks when the toolchain is available.
4. Run related tests when available.
5. Combine deterministic results with `hardware_reviewer` findings.
6. Report static, build, loopback, and real-hardware validation separately.

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
- `hardware_reviewer` must not modify application source or configuration.
- Do not spawn `test_reviewer` here; final regression delegation belongs to `review-change`.
- Project Sub-Agents must not recursively spawn another Project Sub-Agent unless the parent explicitly requests it.
