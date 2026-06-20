from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    serial_port = LaunchConfiguration("serial_port")
    serial_baudrate = LaunchConfiguration("serial_baudrate")
    frame_id = LaunchConfiguration("frame_id")
    driver_package = LaunchConfiguration("driver_package")
    driver_executable = LaunchConfiguration("driver_executable")
    scan_mode = LaunchConfiguration("scan_mode")
    inverted = LaunchConfiguration("inverted")
    angle_compensate = LaunchConfiguration("angle_compensate")

    laser_x = LaunchConfiguration("laser_x")
    laser_y = LaunchConfiguration("laser_y")
    laser_z = LaunchConfiguration("laser_z")
    laser_roll = LaunchConfiguration("laser_roll")
    laser_pitch = LaunchConfiguration("laser_pitch")
    laser_yaw = LaunchConfiguration("laser_yaw")
    base_frame = LaunchConfiguration("base_frame")

    return LaunchDescription([
        DeclareLaunchArgument("serial_port", default_value="/dev/ttyUSB0"),
        DeclareLaunchArgument("serial_baudrate", default_value="115200"),
        DeclareLaunchArgument("frame_id", default_value="laser"),
        DeclareLaunchArgument("driver_package", default_value="rplidar_ros"),
        DeclareLaunchArgument("driver_executable", default_value="rplidar_composition"),
        DeclareLaunchArgument("scan_mode", default_value="Sensitivity"),
        DeclareLaunchArgument("inverted", default_value="false"),
        DeclareLaunchArgument("angle_compensate", default_value="true"),
        DeclareLaunchArgument("base_frame", default_value="base_link"),
        DeclareLaunchArgument("laser_x", default_value="0.0"),
        DeclareLaunchArgument("laser_y", default_value="0.0"),
        DeclareLaunchArgument("laser_z", default_value="0.12"),
        DeclareLaunchArgument("laser_roll", default_value="0.0"),
        DeclareLaunchArgument("laser_pitch", default_value="0.0"),
        DeclareLaunchArgument("laser_yaw", default_value="0.0"),
        Node(
            package=driver_package,
            executable=driver_executable,
            name="rplidar_node",
            output="screen",
            parameters=[{
                "channel_type": "serial",
                "serial_port": serial_port,
                "serial_baudrate": ParameterValue(serial_baudrate, value_type=int),
                "frame_id": frame_id,
                "inverted": ParameterValue(inverted, value_type=bool),
                "angle_compensate": ParameterValue(angle_compensate, value_type=bool),
                "scan_mode": scan_mode,
            }],
        ),
        Node(
            package="tf2_ros",
            executable="static_transform_publisher",
            name="base_to_laser_tf",
            output="screen",
            arguments=[
                laser_x,
                laser_y,
                laser_z,
                laser_yaw,
                laser_pitch,
                laser_roll,
                base_frame,
                frame_id,
            ],
        ),
    ])
