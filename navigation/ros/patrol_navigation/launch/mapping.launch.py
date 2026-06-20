from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare("patrol_navigation")
    lidar_launch = PathJoinSubstitution([pkg_share, "launch", "lidar.launch.py"])
    slam_config = LaunchConfiguration("slam_config")
    server_base_url = LaunchConfiguration("server_base_url")
    robot_id = LaunchConfiguration("robot_id")
    start_lidar = LaunchConfiguration("start_lidar")
    start_bridge = LaunchConfiguration("start_bridge")
    start_fake_odom = LaunchConfiguration("start_fake_odom")
    start_rviz = LaunchConfiguration("start_rviz")
    rviz_config = LaunchConfiguration("rviz_config")
    odom_frame = LaunchConfiguration("odom_frame")
    base_frame = LaunchConfiguration("base_frame")

    return LaunchDescription([
        DeclareLaunchArgument("robot_id", default_value="pi-01"),
        DeclareLaunchArgument("server_base_url", default_value="http://127.0.0.1:21063"),
        DeclareLaunchArgument("start_lidar", default_value="true"),
        DeclareLaunchArgument("start_bridge", default_value="true"),
        DeclareLaunchArgument("start_fake_odom", default_value="true"),
        DeclareLaunchArgument("start_rviz", default_value="false"),
        DeclareLaunchArgument("odom_frame", default_value="odom"),
        DeclareLaunchArgument("base_frame", default_value="base_link"),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument(
            "slam_config",
            default_value=PathJoinSubstitution([pkg_share, "config", "slam_toolbox.yaml"]),
        ),
        DeclareLaunchArgument(
            "rviz_config",
            default_value=PathJoinSubstitution([pkg_share, "rviz", "mapping.rviz"]),
        ),
        DeclareLaunchArgument("serial_port", default_value="/dev/ttyUSB0"),
        DeclareLaunchArgument("serial_baudrate", default_value="115200"),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(lidar_launch),
            condition=IfCondition(start_lidar),
            launch_arguments={
                "serial_port": LaunchConfiguration("serial_port"),
                "serial_baudrate": LaunchConfiguration("serial_baudrate"),
            }.items(),
        ),
        Node(
            package="tf2_ros",
            executable="static_transform_publisher",
            name="temporary_odom_to_base_tf",
            output="screen",
            condition=IfCondition(start_fake_odom),
            arguments=["0", "0", "0", "0", "0", "0", odom_frame, base_frame],
        ),
        Node(
            package="slam_toolbox",
            executable="async_slam_toolbox_node",
            name="slam_toolbox",
            output="screen",
            parameters=[
                slam_config,
                {"use_sim_time": LaunchConfiguration("use_sim_time")},
            ],
        ),
        Node(
            package="patrol_navigation",
            executable="map_bridge",
            name="map_bridge",
            output="screen",
            condition=IfCondition(start_bridge),
            parameters=[{
                "robot_id": robot_id,
                "server_base_url": server_base_url,
                "map_topic": "/map",
                "scan_topic": "/scan",
                "pose_parent_frame": "map",
                "pose_child_frame": "base_link",
                "map_publish_period_sec": 1.0,
                "pose_publish_period_sec": 0.2,
                "scan_publish_period_sec": 0.2,
                "send_map": True,
                "send_pose": True,
                "send_scan": True,
            }],
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="mapping_rviz",
            output="screen",
            condition=IfCondition(start_rviz),
            arguments=["-d", rviz_config],
        ),
    ])
