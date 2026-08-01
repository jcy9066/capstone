#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "hardware/clocks.h"
#include "hardware/pwm.h"
#include "hardware/uart.h"
#include "pico/stdlib.h"


#define CONTROL_UART uart0
#define UART_BAUDRATE 115200
#define UART_TX_PIN 0
#define UART_RX_PIN 1

#define LEFT_PWM_PIN 2
#define LEFT_DIR_PIN 3
#define RIGHT_PWM_PIN 4
#define RIGHT_DIR_PIN 5

#define PWM_FREQUENCY_HZ 20000.0f
#define PWM_WRAP 999U

#define COMMAND_TIMEOUT_MS 350U
#define CURVE_INNER_RATIO 0.35f
#define RX_BUFFER_SIZE 128U

/*
 * 바퀴를 띄운 상태에서 전진 방향을 확인한다.
 * 해당 측이 반대로 회전하면 0과 1을 바꾼다.
 */
#define LEFT_FORWARD_DIR_LEVEL 0
#define RIGHT_FORWARD_DIR_LEVEL 0


typedef struct {
    uint pwm_pin;
    uint dir_pin;
    uint slice;
    uint channel;
    bool forward_dir_level;
} motor_channel_t;


static motor_channel_t left_motor;
static motor_channel_t right_motor;

static bool is_moving = false;
static uint64_t last_move_ms = 0;


static float clamp_float(float value, float min_value, float max_value) {
    if (value < min_value) {
        return min_value;
    }

    if (value > max_value) {
        return max_value;
    }

    return value;
}


static void uart_reply(const char *message) {
    uart_puts(CONTROL_UART, message);
    uart_putc_raw(CONTROL_UART, '\n');
}


static void motor_channel_init(
    motor_channel_t *motor,
    uint pwm_pin,
    uint dir_pin,
    bool forward_dir_level
) {
    motor->pwm_pin = pwm_pin;
    motor->dir_pin = dir_pin;
    motor->forward_dir_level = forward_dir_level;

    gpio_init(dir_pin);
    gpio_set_dir(dir_pin, GPIO_OUT);
    gpio_put(dir_pin, forward_dir_level);

    gpio_set_function(pwm_pin, GPIO_FUNC_PWM);

    motor->slice = pwm_gpio_to_slice_num(pwm_pin);
    motor->channel = pwm_gpio_to_channel(pwm_pin);

    pwm_config config = pwm_get_default_config();

    pwm_config_set_wrap(&config, PWM_WRAP);

    const float clock_divider =
        (float)clock_get_hz(clk_sys) /
        (PWM_FREQUENCY_HZ * (float)(PWM_WRAP + 1U));

    pwm_config_set_clkdiv(&config, clock_divider);

    pwm_init(motor->slice, &config, true);

    pwm_set_chan_level(
        motor->slice,
        motor->channel,
        0
    );
}


static void motor_set_signed_speed(
    motor_channel_t *motor,
    float signed_speed
) {
    signed_speed = clamp_float(
        signed_speed,
        -1.0f,
        1.0f
    );

    const bool forward = signed_speed >= 0.0f;

    gpio_put(
        motor->dir_pin,
        forward
            ? motor->forward_dir_level
            : !motor->forward_dir_level
    );

    float magnitude = signed_speed;

    if (magnitude < 0.0f) {
        magnitude = -magnitude;
    }

    const uint16_t level = (uint16_t)(
        magnitude * (float)PWM_WRAP
    );

    pwm_set_chan_level(
        motor->slice,
        motor->channel,
        level
    );
}


static void stop_motors(void) {
    pwm_set_chan_level(
        left_motor.slice,
        left_motor.channel,
        0
    );

    pwm_set_chan_level(
        right_motor.slice,
        right_motor.channel,
        0
    );

    is_moving = false;
}


static bool direction_to_wheel_speeds(
    const char *direction,
    float speed,
    float *left_speed,
    float *right_speed
) {
    const float inner = speed * CURVE_INNER_RATIO;

    if (strcmp(direction, "forward") == 0) {
        *left_speed = speed;
        *right_speed = speed;

    } else if (strcmp(direction, "backward") == 0) {
        *left_speed = -speed;
        *right_speed = -speed;

    } else if (strcmp(direction, "left") == 0) {
        *left_speed = 0.0f;
        *right_speed = speed;

    } else if (strcmp(direction, "right") == 0) {
        *left_speed = speed;
        *right_speed = 0.0f;

    } else if (strcmp(direction, "forward_left") == 0) {
        *left_speed = inner;
        *right_speed = speed;

    } else if (strcmp(direction, "forward_right") == 0) {
        *left_speed = speed;
        *right_speed = inner;

    } else if (strcmp(direction, "backward_left") == 0) {
        *left_speed = -speed;
        *right_speed = -inner;

    } else if (strcmp(direction, "backward_right") == 0) {
        *left_speed = -inner;
        *right_speed = -speed;

    } else if (strcmp(direction, "rotate_left") == 0) {
        *left_speed = -speed;
        *right_speed = speed;

    } else if (strcmp(direction, "rotate_right") == 0) {
        *left_speed = speed;
        *right_speed = -speed;

    } else {
        return false;
    }

    return true;
}


static void move_motors(
    const char *direction,
    float speed
) {
    float left_speed = 0.0f;
    float right_speed = 0.0f;

    if (!direction_to_wheel_speeds(
            direction,
            speed,
            &left_speed,
            &right_speed
        )) {
        stop_motors();
        uart_reply("ERR,invalid direction");
        return;
    }

    motor_set_signed_speed(
        &left_motor,
        left_speed
    );

    motor_set_signed_speed(
        &right_motor,
        right_speed
    );

    last_move_ms = to_ms_since_boot(
        get_absolute_time()
    );

    is_moving = true;

    uart_puts(CONTROL_UART, "OK,MOVE,");
    uart_puts(CONTROL_UART, direction);
    uart_putc_raw(CONTROL_UART, '\n');
}


static void handle_command(char *line) {
    char *save_pointer = NULL;

    char *command = strtok_r(
        line,
        ",",
        &save_pointer
    );

    if (command == NULL) {
        return;
    }

    if (strcmp(command, "PING") == 0) {
        uart_reply("OK,PONG");
        return;
    }

    if (strcmp(command, "STOP") == 0) {
        stop_motors();
        uart_reply("OK,STOP");
        return;
    }

    if (strcmp(command, "MOVE") == 0) {
        char *direction = strtok_r(
            NULL,
            ",",
            &save_pointer
        );

        char *speed_text = strtok_r(
            NULL,
            ",",
            &save_pointer
        );

        if (
            direction == NULL ||
            speed_text == NULL
        ) {
            stop_motors();
            uart_reply(
                "ERR,MOVE requires direction and speed"
            );
            return;
        }

        char *end_pointer = NULL;

        float speed = strtof(
            speed_text,
            &end_pointer
        );

        if (
            end_pointer == speed_text ||
            *end_pointer != '\0'
        ) {
            stop_motors();
            uart_reply("ERR,invalid speed");
            return;
        }

        speed = clamp_float(
            speed,
            0.0f,
            1.0f
        );

        if (speed <= 0.0f) {
            stop_motors();
            uart_reply("OK,STOP");
            return;
        }

        move_motors(
            direction,
            speed
        );

        return;
    }

    stop_motors();
    uart_reply("ERR,unknown command");
}


int main(void) {
    uart_init(
        CONTROL_UART,
        UART_BAUDRATE
    );

    gpio_set_function(
        UART_TX_PIN,
        GPIO_FUNC_UART
    );

    gpio_set_function(
        UART_RX_PIN,
        GPIO_FUNC_UART
    );

    uart_set_format(
        CONTROL_UART,
        8,
        1,
        UART_PARITY_NONE
    );

    uart_set_fifo_enabled(
        CONTROL_UART,
        true
    );

    motor_channel_init(
        &left_motor,
        LEFT_PWM_PIN,
        LEFT_DIR_PIN,
        LEFT_FORWARD_DIR_LEVEL
    );

    motor_channel_init(
        &right_motor,
        RIGHT_PWM_PIN,
        RIGHT_DIR_PIN,
        RIGHT_FORWARD_DIR_LEVEL
    );

    stop_motors();

    sleep_ms(100);

    uart_reply("READY,PICO_W_MOTOR");

    char receive_buffer[RX_BUFFER_SIZE];
    size_t receive_length = 0;

    while (true) {
        while (uart_is_readable(CONTROL_UART)) {
            const char character =
                uart_getc(CONTROL_UART);

            if (
                character == '\n' ||
                character == '\r'
            ) {
                if (receive_length > 0) {
                    receive_buffer[
                        receive_length
                    ] = '\0';

                    handle_command(
                        receive_buffer
                    );

                    receive_length = 0;
                }

            } else if (
                receive_length <
                RX_BUFFER_SIZE - 1U
            ) {
                receive_buffer[
                    receive_length++
                ] = character;

            } else {
                receive_length = 0;
                stop_motors();

                uart_reply(
                    "ERR,receive buffer overflow"
                );
            }
        }

        if (is_moving) {
            const uint64_t now_ms =
                to_ms_since_boot(
                    get_absolute_time()
                );

            if (
                now_ms - last_move_ms >
                COMMAND_TIMEOUT_MS
            ) {
                stop_motors();

                uart_reply(
                    "EVENT,FAILSAFE_STOP"
                );
            }
        }

        sleep_ms(1);
    }

    return 0;
}
