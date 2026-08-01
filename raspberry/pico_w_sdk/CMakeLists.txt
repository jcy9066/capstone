cmake_minimum_required(VERSION 3.13)

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(pico_motor_controller C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(pico_motor_controller
    main.c
)

target_link_libraries(pico_motor_controller
    pico_stdlib
    hardware_uart
    hardware_pwm
    hardware_clocks
)

# UART0은 프로그램에서 직접 사용한다.
pico_enable_stdio_usb(pico_motor_controller 0)
pico_enable_stdio_uart(pico_motor_controller 0)

pico_add_extra_outputs(pico_motor_controller)
