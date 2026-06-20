# 20260620 [FULL] 2D LiDAR mapping ROS2 node 구성 결과

## 1. 작업 결과

RPLIDAR A1M8-R6 기반 1차 mapping 시각화를 위한 ROS2 패키지 뼈대와 서버 수신 API를 추가했다.

이번 작업은 현재 LiDAR가 연결되어 있지 않은 상태를 전제로 한다. 따라서 실제 `/scan` 수신, `slam_toolbox` mapping 품질, serial port, baudrate, RViz 표시는 추후 Raspberry Pi에 LiDAR를 연결한 뒤 검증해야 한다.

## 2. 추가한 ROS2 패키지

추가 위치:

```text
navigation/ros/patrol_navigation/
```

구성:

```text
package.xml
setup.py
setup.cfg
resource/patrol_navigation
patrol_navigation/__init__.py
patrol_navigation/map_bridge.py
launch/lidar.launch.py
launch/mapping.launch.py
config/rplidar_a1m8.yaml
config/slam_toolbox.yaml
```

역할:

- `lidar.launch.py`
  - SLAMTEC RPLIDAR ROS2 driver node 실행
  - 기본 serial port: `/dev/ttyUSB0`
  - 기본 baudrate: `115200`
  - 기본 frame: `laser`
  - `base_link -> laser` static transform publish
- `mapping.launch.py`
  - RPLIDAR launch include
  - 임시 `odom -> base_link` static transform publish
  - `slam_toolbox` 실행
  - `map_bridge` 실행
- `map_bridge.py`
  - `/map` subscribe
  - TF에서 `map -> base_link` pose 조회
  - 선택적으로 `/scan` downsample 전송 가능
  - FastAPI 서버로 map/pose/scan JSON 전송

## 3. 서버 API 추가

수정 파일:

```text
server/app.py
```

추가 endpoint:

| Method | Path | 역할 |
| --- | --- | --- |
| POST | `/navigation/map` | ROS2 bridge가 보낸 OccupancyGrid map 저장 |
| POST | `/navigation/pose` | ROS2 bridge가 보낸 로봇 pose 저장 |
| POST | `/navigation/scan` | 선택적으로 downsample scan 저장 |
| GET | `/api/navigation/status` | navigation 상태 조회 |
| GET | `/api/navigation/map` | 최신 map 조회 |
| GET | `/api/navigation/pose` | 최신 pose 조회 |
| GET | `/api/navigation/scan` | 최신 scan 조회 |

`/api/robots/{robot_id}` 응답에도 navigation status를 포함하도록 확장했다.

## 4. 의존성 반영

새 pip 패키지는 추가하지 않았다.

`map_bridge.py`는 HTTP 전송에 `requests`를 사용하지만, `requirements.txt`에 이미 `requests==2.28.2`가 존재하므로 변경하지 않았다.

ROS2 의존성은 `navigation/ros/patrol_navigation/package.xml`에 명시했다.

주요 ROS2 의존성:

- `rclpy`
- `nav_msgs`
- `sensor_msgs`
- `tf2_ros`
- `rplidar_ros`
- `slam_toolbox`
- `launch`
- `launch_ros`

## 5. 실행 예시

Raspberry Pi에서 ROS2 workspace로 빌드한 뒤 실행하는 형태를 기준으로 한다.

```bash
cd ~/capstone/navigation/ros
colcon build --packages-select patrol_navigation
source install/setup.bash
ros2 launch patrol_navigation mapping.launch.py   serial_port:=/dev/ttyUSB0   server_base_url:=http://<GPU_SERVER_IP>:21063   robot_id:=pi-01
```

LiDAR가 다른 serial path로 잡히면 `serial_port`만 바꾼다.

```bash
ros2 launch patrol_navigation mapping.launch.py serial_port:=/dev/ttyACM0
```

나중에 encoder 기반 `/odom`을 붙이면 임시 static odom transform을 끈다.

```bash
ros2 launch patrol_navigation mapping.launch.py start_fake_odom:=false
```

## 6. 검증 결과

수행한 검증:

```bash
python3 -m py_compile   capstone/server/app.py   capstone/navigation/ros/patrol_navigation/patrol_navigation/map_bridge.py   capstone/navigation/ros/patrol_navigation/launch/lidar.launch.py   capstone/navigation/ros/patrol_navigation/launch/mapping.launch.py   capstone/navigation/ros/patrol_navigation/setup.py
```

결과: 통과.

```bash
colcon list --base-paths capstone/navigation/ros
```

결과:

```text
patrol_navigation capstone/navigation/ros/patrol_navigation (ros.ament_python)
```

현재 환경에서는 `ros2` CLI가 잡히지 않아 실제 `ros2 launch` 실행 검증은 하지 못했다.
또한 LiDAR 장치가 연결되어 있지 않으므로 `/scan`, `/map`, TF, RViz 검증은 추후 하드웨어 연결 후 진행한다.

## 7. 다음 작업

1. Raspberry Pi에 RPLIDAR A1M8-R6 연결
2. serial device 확인
3. `ros2 launch patrol_navigation mapping.launch.py` 실행
4. `/scan` topic 확인
5. RViz에서 LaserScan과 map 확인
6. FastAPI 서버에서 `/api/navigation/status`, `/api/navigation/map`, `/api/navigation/pose` 확인
7. 대시보드 canvas map 표시 구현
