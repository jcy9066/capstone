# 전체 LiDAR mapping pipeline을 실행하는 ROS2 launch 파일.
#
# 이 파일은 1차 mapping에 필요한 노드들을 한 번에 실행한다.
#   RPLIDAR driver -> /scan -> slam_toolbox -> /map + TF -> map_bridge -> FastAPI server
#
# 실제 Raspberry Pi 테스트 중 slam_toolbox가 /scan을 받고 lifecycle 상태를 거쳐야
# map_bridge가 map->base_link TF를 안정적으로 읽을 수 있었기 때문에 몇 초의 지연 실행을 넣었다.

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # 설치된 patrol_navigation package의 share 디렉터리를 찾는다.
    # colcon build 후 launch/config/rviz 파일은 이 package share 경로 아래에 복사된다.
    pkg_share = FindPackageShare("patrol_navigation")
    lidar_launch = PathJoinSubstitution([pkg_share, "launch", "lidar.launch.py"])

    # 명령어에서 바꿀 수 있는 값들이다. 예:
    #   ros2 launch patrol_navigation mapping.launch.py server_base_url:=http://10.108.90.21:21063
    slam_config = LaunchConfiguration("slam_config")
    server_base_url = LaunchConfiguration("server_base_url")
    robot_id = LaunchConfiguration("robot_id")

    # 디버깅할 때 pipeline 일부만 켜거나 끌 수 있는 스위치다.
    start_lidar = LaunchConfiguration("start_lidar")
    start_bridge = LaunchConfiguration("start_bridge")
    start_fake_odom = LaunchConfiguration("start_fake_odom")
    start_rviz = LaunchConfiguration("start_rviz")

    rviz_config = LaunchConfiguration("rviz_config")
    odom_frame = LaunchConfiguration("odom_frame")
    base_frame = LaunchConfiguration("base_frame")

    # slam_toolbox는 /scan을 입력으로 받아 /map을 만든다.
    # async_slam_toolbox_node는 로봇이 움직이는 동안 실시간으로 map을 만드는 online mapping에 적합하다.
    slam_toolbox_node = Node(
        package="slam_toolbox",
        executable="async_slam_toolbox_node",
        name="slam_toolbox",
        output="screen",
        parameters=[
            slam_config,
            {"use_sim_time": LaunchConfiguration("use_sim_time")},
        ],
    )

    # 이 구성에서 slam_toolbox는 lifecycle node로 동작한다.
    # activate 전에 configure 단계가 필요하다. 3초 지연은 /scan과 TF publisher가 먼저 뜰 시간을 주기 위한 것이다.
    configure_slam_toolbox = TimerAction(
        period=3.0,
        actions=[
            ExecuteProcess(
                cmd=["ros2", "lifecycle", "set", "/slam_toolbox", "configure"],
                output="screen",
            )
        ],
    )

    # configure 후 activate해야 slam_toolbox가 실제로 scan 데이터를 처리하고 map을 publish한다.
    activate_slam_toolbox = TimerAction(
        period=6.0,
        actions=[
            ExecuteProcess(
                cmd=["ros2", "lifecycle", "set", "/slam_toolbox", "activate"],
                output="screen",
            )
        ],
    )

    # map_bridge는 ROS 데이터를 FastAPI 서버로 전달한다.
    # slam_toolbox가 먼저 map frame을 만들 시간을 주기 위해 8초 뒤 실행한다.
    map_bridge_node = TimerAction(
        period=8.0,
        actions=[
            Node(
                package="patrol_navigation",
                executable="map_bridge",
                name="map_bridge",
                output="screen",
                condition=IfCondition(start_bridge),
                parameters=[{
                    # 대시보드에서 어떤 로봇의 데이터인지 구분하기 위한 값이다.
                    "robot_id": robot_id,
                    "server_base_url": server_base_url,

                    # map_bridge가 읽을 ROS topic과 TF frame이다.
                    "map_topic": "/map",
                    "scan_topic": "/scan",
                    "pose_parent_frame": "map",
                    "pose_child_frame": "base_link",

                    # HTTP 전송 주기다. scan/pose는 자주 보내고, map은 payload가 크므로 상대적으로 천천히 보낸다.
                    "map_publish_period_sec": 1.0,
                    "pose_publish_period_sec": 0.2,
                    "scan_publish_period_sec": 0.2,

                    # 웹 대시보드에서 map 배경, 로봇 위치, 실시간 scan overlay를 모두 쓰기 위해 세 데이터를 모두 켠다.
                    "send_map": True,
                    "send_pose": True,
                    "send_scan": True,
                }],
            )
        ],
    )

    return LaunchDescription([
        # 실행 시 공통으로 쓰는 인자다.
        DeclareLaunchArgument("robot_id", default_value="pi-01"),
        DeclareLaunchArgument("server_base_url", default_value="http://127.0.0.1:21063"),

        # 디버깅용 스위치다.
        DeclareLaunchArgument("start_lidar", default_value="true"),
        DeclareLaunchArgument("start_bridge", default_value="true"),
        DeclareLaunchArgument("start_fake_odom", default_value="true"),
        DeclareLaunchArgument("start_rviz", default_value="false"),

        # TF와 slam_toolbox가 사용하는 frame 이름이다.
        DeclareLaunchArgument("odom_frame", default_value="odom"),
        DeclareLaunchArgument("base_frame", default_value="base_link"),
        DeclareLaunchArgument("use_sim_time", default_value="false"),

        # 설정 파일 경로다.
        DeclareLaunchArgument(
            "slam_config",
            default_value=PathJoinSubstitution([pkg_share, "config", "slam_toolbox.yaml"]),
        ),
        DeclareLaunchArgument(
            "rviz_config",
            default_value=PathJoinSubstitution([pkg_share, "rviz", "mapping.rviz"]),
        ),

        # RPLIDAR 연결 설정이다. 이 값은 lidar.launch.py로 전달된다.
        DeclareLaunchArgument("serial_port", default_value="/dev/ttyUSB0"),
        DeclareLaunchArgument("serial_baudrate", default_value="115200"),

        # RPLIDAR driver와 base_link->laser static TF를 실행한다.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(lidar_launch),
            condition=IfCondition(start_lidar),
            launch_arguments={
                "serial_port": LaunchConfiguration("serial_port"),
                "serial_baudrate": LaunchConfiguration("serial_baudrate"),
            }.items(),
        ),

        # 임시 odom->base_link transform이다.
        # 현재 mapping 단계에서는 encoder odometry가 아직 없으므로 임시 static TF를 사용한다.
        # 나중에 실제 /odom publisher를 붙이면 start_fake_odom:=false로 실행해야 한다.
        Node(
            package="tf2_ros",
            executable="static_transform_publisher",
            name="temporary_odom_to_base_tf",
            output="screen",
            condition=IfCondition(start_fake_odom),
            arguments=["0", "0", "0", "0", "0", "0", odom_frame, base_frame],
        ),

        # SLAM lifecycle 실행 순서와 서버 bridge 시작 순서다.
        slam_toolbox_node,
        configure_slam_toolbox,
        activate_slam_toolbox,
        map_bridge_node,

        # 로컬 시각화 도구다. GUI 창이 열리므로 headless Pi 환경에서는 기본값 false를 유지한다.
        Node(
            package="rviz2",
            executable="rviz2",
            name="mapping_rviz",
            output="screen",
            condition=IfCondition(start_rviz),
            arguments=["-d", rviz_config],
        ),
    ])
