---
name: validate-raspberry
description: Validate changed Pi/Pico/UART/motor/encoder/failsafe paths.
---

# Validate Raspberry

Read `references/uart_protocol.md`.

## Procedure

1. Delegate current Pi/Pico protocol and safety diff to `hardware_reviewer`; reuse matching result.
2. Compare both sides of each changed UART command/event and safety timeout.
3. Run:
   `python .agents/skills/validate-raspberry/scripts/validate_uart_protocol.py`
4. Run affected Python/tests in quiet/RTK mode when available.
5. Build Pico SDK only when the toolchain is available and the firmware changed.
6. Separate static/build/mock results from real UART/hardware results.

## Context Budget

Use targeted search/partial reads. Do not return full firmware/source/build logs or successful
test output. Return protocol mismatches, safety issues, evidence, and skipped hardware checks.

## Restrictions

No real serial movement, GPIO output, motor/speaker drive, firmware flash, OpenOCD,
Git remote/history mutation, or `test_reviewer` delegation here.
