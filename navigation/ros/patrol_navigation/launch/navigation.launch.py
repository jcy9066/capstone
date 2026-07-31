# 저장 지도 기반 localization과 Nav2를 함께 실행하는 launch 파일.
#
# 실행 구조:
#   localization.launch.py
#     - SLLIDAR
#     - map_server
#     - AMCL
#     - 임시 odom -> base_link TF
#     - map_bridge
#
#   Navigation2
#     - controller_server
#     - smoother_server
#     - planner_server
#     - behavior_server
#     - bt_navigator
#     - waypoint_follower
#     - velocity_smoother
#
# 안전 설정:
#   Nav2 최종 속도 명령은 실제 /cmd_vel이 아니라
#   /cmd_vel_nav_dry_run으로 출력한다.
#
# 따라서 현재 파일만 실행해서는 Pico W, MDD10A, 모터에
# 어떤 명령도 전달되지 않는다.

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution,
)

from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare("patrol_navigation")

    # ---------------------------------------------------------
    # Launch arguments
    # ---------------------------------------------------------
    map_yaml = LaunchConfiguration("map")
    nav2_params = LaunchConfiguration("params_file")

    robot_id = LaunchConfiguration("robot_id")
    server_base_url = LaunchConfiguration("server_base_url")

    serial_port = LaunchConfiguration("serial_port")
    serial_baudrate = LaunchConfiguration("serial_baudrate")

    start_lidar = LaunchConfiguration("start_lidar")
    start_bridge = LaunchConfiguration("start_bridge")
    start_fake_odom = LaunchConfiguration("start_fake_odom")

    # ---------------------------------------------------------
    # 기존 localization launch 재사용
    # ---------------------------------------------------------
    localization_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                pkg_share,
                "launch",
                "localization.launch.py",
            ])
        ),
        launch_arguments={
            "map": map_yaml,
            "robot_id": robot_id,
            "server_base_url": server_base_url,

            "serial_port": serial_port,
            "serial_baudrate": serial_baudrate,

            "start_lidar": start_lidar,
            "start_bridge": start_bridge,
            "start_fake_odom": start_fake_odom,

            "use_sim_time": "false",
        }.items(),
    )

    common_remappings = [
        ("/tf", "tf"),
        ("/tf_static", "tf_static"),
    ]

    # ---------------------------------------------------------
    # Controller server
    # ---------------------------------------------------------
    #
    # Controller가 생성하는 속도 명령을 cmd_vel_nav로 보낸다.
    # velocity_smoother가 이 명령을 받아 최종 dry-run topic으로
    # 출력한다.
    controller_server = Node(
        package="nav2_controller",
        executable="controller_server",
        name="controller_server",
        output="screen",
        parameters=[nav2_params],
        remappings=common_remappings + [
            ("cmd_vel", "cmd_vel_nav"),
        ],
    )

    # ---------------------------------------------------------
    # Path smoother
    # ---------------------------------------------------------
    smoother_server = Node(
        package="nav2_smoother",
        executable="smoother_server",
        name="smoother_server",
        output="screen",
        parameters=[nav2_params],
        remappings=common_remappings,
    )

    # ---------------------------------------------------------
    # Global planner
    # ---------------------------------------------------------
    planner_server = Node(
        package="nav2_planner",
        executable="planner_server",
        name="planner_server",
        output="screen",
        parameters=[nav2_params],
        remappings=common_remappings,
    )

    # ---------------------------------------------------------
    # Recovery / behavior server
    # ---------------------------------------------------------
    #
    # Spin, BackUp 등의 recovery 동작도 실제 /cmd_vel이 아닌
    # dry-run topic으로 강제 분리한다.
    behavior_server = Node(
        package="nav2_behaviors",
        executable="behavior_server",
        name="behavior_server",
        output="screen",
        parameters=[nav2_params],
        remappings=common_remappings + [
            ("cmd_vel", "/cmd_vel_nav_dry_run"),
        ],
    )

    # ---------------------------------------------------------
    # Behavior Tree navigator
    # ---------------------------------------------------------
    bt_navigator = Node(
        package="nav2_bt_navigator",
        executable="bt_navigator",
        name="bt_navigator",
        output="screen",
        parameters=[nav2_params],
        remappings=common_remappings,
    )

    # ---------------------------------------------------------
    # Waypoint follower
    # ---------------------------------------------------------
    waypoint_follower = Node(
        package="nav2_waypoint_follower",
        executable="waypoint_follower",
        name="waypoint_follower",
        output="screen",
        parameters=[nav2_params],
        remappings=common_remappings,
    )

    # ---------------------------------------------------------
    # Velocity smoother
    # ---------------------------------------------------------
    #
    # 입력:
    #   /cmd_vel_nav
    #
    # 출력:
    #   /cmd_vel_nav_dry_run
    #
    # 실제 /cmd_vel에는 publish하지 않는다.
    velocity_smoother = Node(
        package="nav2_velocity_smoother",
        executable="velocity_smoother",
        name="velocity_smoother",
        output="screen",
        parameters=[nav2_params],
        remappings=common_remappings + [
            ("cmd_vel", "cmd_vel_nav"),
            ("cmd_vel_smoothed", "/cmd_vel_nav_dry_run"),
        ],
    )

    # ---------------------------------------------------------
    # Navigation lifecycle manager
    # ---------------------------------------------------------
    #
    # localization 쪽 map_server와 AMCL이 먼저 활성화될 시간을
    # 주기 위해 6초 뒤 Nav2 노드들을 활성화한다.
    lifecycle_manager_navigation = TimerAction(
        period=6.0,
        actions=[
            Node(
                package="nav2_lifecycle_manager",
                executable="lifecycle_manager",
                name="lifecycle_manager_navigation",
                output="screen",
                parameters=[{
                    "use_sim_time": False,
                    "autostart": True,
                    "node_names": [
                        "controller_server",
                        "smoother_server",
                        "planner_server",
                        "behavior_server",
                        "bt_navigator",
                        "waypoint_follower",
                        "velocity_smoother",
                    ],
                }],
            )
        ],
    )

    return LaunchDescription([
        # -----------------------------------------------------
        # 저장 지도
        # -----------------------------------------------------
        DeclareLaunchArgument(
            "map",
            default_value=PathJoinSubstitution([
                EnvironmentVariable("HOME"),
                "dabom_capstone",
                "navigation",
                "maps",
                "slam_test_01.yaml",
            ]),
        ),

        # Nav2 설정
        DeclareLaunchArgument(
            "params_file",
            default_value=PathJoinSubstitution([
                pkg_share,
                "config",
                "nav2_params.yaml",
            ]),
        ),

        # 서버
        DeclareLaunchArgument(
            "robot_id",
            default_value="pi-01",
        ),
        DeclareLaunchArgument(
            "server_base_url",
            default_value="http://127.0.0.1:21063",
        ),

        # LiDAR
        DeclareLaunchArgument(
            "serial_port",
            default_value="/dev/ttyUSB0",
        ),
        DeclareLaunchArgument(
            "serial_baudrate",
            default_value="115200",
        ),

        # 실행 여부
        DeclareLaunchArgument(
            "start_lidar",
            default_value="true",
        ),
        DeclareLaunchArgument(
            "start_bridge",
            default_value="true",
        ),
        DeclareLaunchArgument(
            "start_fake_odom",
            default_value="true",
        ),

        # Localization
        localization_launch,

        # Navigation2
        controller_server,
        smoother_server,
        planner_server,
        behavior_server,
        bt_navigator,
        waypoint_follower,
        velocity_smoother,

        # Lifecycle activation
        lifecycle_manager_navigation,
    ])