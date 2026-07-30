from machine import Pin, PWM, UART
import time


# Pi GPIO14 TXD -> Pico W GP1 RX
# Pi GPIO15 RXD <- Pico W GP0 TX
UART_ID = 0
UART_BAUDRATE = 115200
UART_TX_PIN = 0
UART_RX_PIN = 1

# Pico W -> MDD10A
LEFT_PWM_PIN = 2
LEFT_DIR_PIN = 3
RIGHT_PWM_PIN = 4
RIGHT_DIR_PIN = 5

PWM_FREQUENCY_HZ = 20000
COMMAND_TIMEOUT_MS = 350
CURVE_INNER_RATIO = 0.35

# 바퀴를 띄운 상태에서 전진 방향을 확인합니다.
# 반대로 회전하는 채널만 0과 1을 바꿉니다.
LEFT_FORWARD_DIR_LEVEL = 0
RIGHT_FORWARD_DIR_LEVEL = 0

ALLOWED_DIRECTIONS = {
    "forward",
    "backward",
    "left",
    "right",
    "forward_left",
    "forward_right",
    "backward_left",
    "backward_right",
    "rotate_left",
    "rotate_right",
}


class MotorChannel:
    def __init__(
        self,
        pwm_pin,
        dir_pin,
        forward_dir_level,
    ):
        self.pwm = PWM(
            Pin(pwm_pin, Pin.OUT)
        )

        self.pwm.freq(
            PWM_FREQUENCY_HZ
        )

        self.direction = Pin(
            dir_pin,
            Pin.OUT,
            value=forward_dir_level,
        )

        self.forward_dir_level = (
            1 if forward_dir_level else 0
        )

        self.stop()

    def set_signed_speed(
        self,
        signed_speed,
    ):
        signed_speed = max(
            -1.0,
            min(float(signed_speed), 1.0),
        )

        if signed_speed >= 0.0:
            self.direction.value(
                self.forward_dir_level
            )
        else:
            self.direction.value(
                1 - self.forward_dir_level
            )

        self.pwm.duty_u16(
            int(abs(signed_speed) * 65535)
        )

    def stop(self):
        self.pwm.duty_u16(0)


uart = UART(
    UART_ID,
    baudrate=UART_BAUDRATE,
    tx=Pin(UART_TX_PIN),
    rx=Pin(UART_RX_PIN),
    bits=8,
    parity=None,
    stop=1,
)

left_motor = MotorChannel(
    LEFT_PWM_PIN,
    LEFT_DIR_PIN,
    LEFT_FORWARD_DIR_LEVEL,
)

right_motor = MotorChannel(
    RIGHT_PWM_PIN,
    RIGHT_DIR_PIN,
    RIGHT_FORWARD_DIR_LEVEL,
)

last_move_ms = time.ticks_ms()
is_moving = False
rx_buffer = bytearray()


def reply(message):
    uart.write(
        (message + "\n").encode("ascii")
    )


def stop_motors():
    global is_moving

    left_motor.stop()
    right_motor.stop()

    is_moving = False


def direction_to_wheel_speeds(
    direction,
    speed,
):
    inner = speed * CURVE_INNER_RATIO

    mapping = {
        "forward": (
            speed,
            speed,
        ),
        "backward": (
            -speed,
            -speed,
        ),
        "left": (
            0.0,
            speed,
        ),
        "right": (
            speed,
            0.0,
        ),
        "forward_left": (
            inner,
            speed,
        ),
        "forward_right": (
            speed,
            inner,
        ),
        "backward_left": (
            -speed,
            -inner,
        ),
        "backward_right": (
            -inner,
            -speed,
        ),
        "rotate_left": (
            -speed,
            speed,
        ),
        "rotate_right": (
            speed,
            -speed,
        ),
    }

    return mapping[direction]


def move(
    direction,
    speed,
):
    global last_move_ms
    global is_moving

    left_speed, right_speed = (
        direction_to_wheel_speeds(
            direction,
            speed,
        )
    )

    left_motor.set_signed_speed(
        left_speed
    )

    right_motor.set_signed_speed(
        right_speed
    )

    last_move_ms = time.ticks_ms()
    is_moving = True


def handle_command(line):
    try:
        parts = [
            part.strip()
            for part in line.split(",")
        ]

        command = (
            parts[0].upper()
            if parts
            else ""
        )

        if command == "PING":
            reply("OK,PONG")
            return

        if command == "STOP":
            stop_motors()

            reason = (
                parts[1]
                if len(parts) > 1
                else "stop"
            )

            reply(
                "OK,STOP," + reason
            )
            return

        if command == "MOVE":
            if len(parts) != 3:
                raise ValueError(
                    "MOVE requires "
                    "direction and speed"
                )

            direction = parts[1].lower()

            if direction not in ALLOWED_DIRECTIONS:
                raise ValueError(
                    "invalid direction"
                )

            speed = max(
                0.0,
                min(float(parts[2]), 1.0),
            )

            if speed <= 0.0:
                stop_motors()
                reply("OK,STOP,zero_speed")
                return

            move(
                direction,
                speed,
            )

            reply(
                "OK,MOVE,{},{:.3f}".format(
                    direction,
                    speed,
                )
            )
            return

        raise ValueError(
            "unknown command"
        )

    except Exception as exc:
        stop_motors()

        reply(
            "ERR,"
            + str(exc).replace(",", ";")
        )


def process_uart_bytes(data):
    global rx_buffer

    if not data:
        return

    rx_buffer.extend(data)

    if len(rx_buffer) > 512:
        rx_buffer = bytearray()
        stop_motors()

        reply(
            "ERR,receive buffer overflow"
        )
        return

    while True:
        try:
            newline_index = (
                rx_buffer.index(10)
            )
        except ValueError:
            return

        raw_line = bytes(
            rx_buffer[:newline_index]
        )

        del rx_buffer[
            :newline_index + 1
        ]

        line = (
            raw_line
            .decode("ascii", "ignore")
            .strip()
        )

        if line:
            handle_command(line)


stop_motors()
reply("READY,PICO_W_MOTOR")


while True:
    if uart.any():
        process_uart_bytes(
            uart.read()
        )

    if (
        is_moving
        and time.ticks_diff(
            time.ticks_ms(),
            last_move_ms,
        ) > COMMAND_TIMEOUT_MS
    ):
        stop_motors()
        reply("EVENT,FAILSAFE_STOP")

    time.sleep_ms(5)