# SLAM / 2D LiDAR Mapping 설명서

이 문서는 `capstone` 프로젝트에서 **RPLIDAR A1M8-R6 + ROS2 + slam_toolbox**로 mapping을 수행하고, 그 결과를 GPU/FastAPI 서버와 웹 대시보드까지 연결한 과정을 설명한다.

ROS를 처음 보는 사람에게 설명할 수 있도록, ROS2의 기본 개념부터 현재 프로젝트의 노드 구성, 데이터 흐름, 실행 명령, 검증 방법을 함께 정리한다.

## 1. 현재 목표

현재 단계의 목표는 완전한 자율주행이 아니라 **2D LiDAR 기반 mapping 시각화**다.

즉, 로봇이 주변을 LiDAR로 스캔하면 다음 결과를 얻는다.

- `/scan`: LiDAR가 한 바퀴 돌며 측정한 각도별 거리값
- `/map`: `slam_toolbox`가 `/scan`을 누적해서 만든 2D 점유 격자 지도
- `/pose`: map 좌표계 기준 로봇 위치와 방향
- `/scan` overlay: 지금 이 순간 LiDAR가 보고 있는 실시간 장애물 점들

현재 연결 흐름은 다음과 같다.

```text
RPLIDAR A1M8-R6
-> Raspberry Pi ROS2
-> /scan
-> slam_toolbox
-> /map + TF
-> map_bridge
-> GPU FastAPI server
-> /api/navigation/map, /pose, /scan
-> 웹 대시보드 MAP AREA
```

## 2. ROS2 기본 개념

ROS2는 로봇 프로그램을 여러 개의 작은 실행 단위로 나누고, 이 실행 단위들이 메시지를 주고받게 하는 middleware다.

### 2.1. Node

Node는 ROS2에서 실행되는 프로그램 하나다.

예를 들어 현재 프로젝트에는 다음 node들이 있다.

| Node | 역할 |
| --- | --- |
| `rplidar_node` | RPLIDAR 장치에서 거리값을 읽어 `/scan` topic으로 publish |
| `base_to_laser_tf` | 로봇 중심과 LiDAR 위치 관계를 TF로 publish |
| `temporary_odom_to_base_tf` | encoder odometry가 아직 없으므로 임시 `odom -> base_link` TF publish |
| `slam_toolbox` | `/scan`을 받아 2D map 생성 |
| `map_bridge` | ROS2 map/pose/scan을 GPU 서버 HTTP API로 전송 |
| `mapping_rviz` | RViz2 시각화 도구. `start_rviz:=true`일 때만 실행 |

### 2.2. Topic

Topic은 node끼리 메시지를 주고받는 이름 있는 통신 채널이다.

예를 들어:

```text
rplidar_node --publish--> /scan --subscribe--> slam_toolbox
```

현재 주요 topic은 다음과 같다.

| Topic | 메시지 타입 | 설명 |
| --- | --- | --- |
| `/scan` | `sensor_msgs/LaserScan` | LiDAR 거리값. 각도별 range 배열 |
| `/map` | `nav_msgs/OccupancyGrid` | SLAM으로 만든 2D 격자 지도 |
| `/tf` | TF transform | 움직이는 좌표계 관계 |
| `/tf_static` | Static TF transform | 고정된 좌표계 관계 |

### 2.3. Publish / Subscribe

- publish: node가 topic에 메시지를 내보내는 것
- subscribe: node가 topic을 구독해서 메시지를 받는 것

현재 예시는 다음과 같다.

```text
rplidar_node
  publish /scan

slam_toolbox
  subscribe /scan
  publish /map
  publish map 관련 TF

map_bridge
  subscribe /map
  subscribe /scan
  read TF map -> base_link
  POST to FastAPI server
```

### 2.4. TF

TF는 로봇의 여러 좌표계 사이 관계를 나타낸다.

현재 목표 좌표계 구조는 다음과 같다.

```text
map
└── odom
    └── base_link
        └── laser
```

각 frame의 의미는 다음과 같다.

| Frame | 의미 |
| --- | --- |
| `map` | SLAM이 만든 전역 지도 좌표계 |
| `odom` | 로봇이 출발 후 움직인 상대 좌표계 |
| `base_link` | 로봇 본체 중심 좌표계 |
| `laser` | LiDAR 센서 중심 좌표계 |

현재는 motor encoder odometry를 아직 연결하지 않았다.
그래서 1차 mapping에서는 임시로 `odom -> base_link`를 static transform으로 둔다.

```text
temporary_odom_to_base_tf
  odom -> base_link = (0, 0, 0)
```

이 방식은 mapping 시각화용 임시 구성이다.
나중에 navigation 단계에서는 encoder를 읽어 실제 `/odom`을 publish해야 한다.

## 3. 왜 ROS2 노드는 Raspberry Pi에서 실행하는가

LiDAR가 Raspberry Pi에 USB로 연결되어 있기 때문이다.

RPLIDAR driver는 실제 `/dev/ttyUSB0` 같은 serial 장치를 열어 LiDAR 데이터를 읽는다.
따라서 아래 ROS2 패키지는 Raspberry Pi에 있어야 한다.

```text
navigation/ros/patrol_navigation/
```

현재 저장소에서 **실제 기준 source package 위치는 `capstone/navigation/ros/patrol_navigation/`**이다.
같은 `capstone/navigation/ros/` 아래에 `build/`, `install/`, `log/` 디렉터리도 보일 수 있는데, 이 세 디렉터리는 `colcon build`가 만든 산출물이다. 패키지 원본은 `patrol_navigation/` 디렉터리다.

Raspberry Pi에서 실행되는 것:

```text
RPLIDAR driver
slam_toolbox
map_bridge
optional RViz
```

GPU 서버에서 실행되는 것:

```text
FastAPI server
web dashboard
AI perception pipeline
```

즉 역할 분리는 다음과 같다.

| 장치 | 역할 |
| --- | --- |
| Raspberry Pi | LiDAR 읽기, ROS2 mapping, map/pose/scan 전송 |
| GPU/FastAPI 서버 | 데이터 수신, 저장, 웹 대시보드 표시 |

## 4. ROS2 패키지 구성

현재 ROS2 패키지 source는 다음 위치에 있다.

```text
capstone/navigation/ros/patrol_navigation/
```

이 디렉터리가 `package.xml`, `setup.py`, `launch/`, `config/`, `rviz/`, Python node 코드를 가진 실제 ROS2 package다.

주요 파일:

```text
patrol_navigation/
  package.xml
  setup.py
  setup.cfg
  launch/
    lidar.launch.py
    mapping.launch.py
  config/
    rplidar_a1m8.yaml
    slam_toolbox.yaml
  rviz/
    mapping.rviz
  patrol_navigation/
    map_bridge.py
```

라즈베리파이로 옮길 때는 이 디렉터리 자체를 ROS2 workspace의 `src` 아래에 둔다.

권장 위치:

```text
~/ros2_ws/src/patrol_navigation/
```

즉 다음 두 경로는 같은 package 내용을 가리킨다고 이해하면 된다.

```text
개발 서버 저장소: capstone/navigation/ros/patrol_navigation/
Raspberry Pi 실행 위치: ~/ros2_ws/src/patrol_navigation/
```

## 5. Launch 파일 구조

ROS2 launch 파일은 여러 node를 한 번에 실행하는 설정 파일이다.

현재 중심 launch 파일은 다음이다.

```text
navigation/ros/patrol_navigation/launch/mapping.launch.py
```

이 파일은 다음 node들을 실행한다.

Pi에서 실제 구동하면서 수정된 현재 launch 파일은 단순히 node를 동시에 띄우지 않는다. `slam_toolbox`가 lifecycle node로 동작하므로, `TimerAction`과 `ros2 lifecycle set` 명령으로 `configure -> activate` 단계를 시간차로 실행한다.

```text
1. RPLIDAR driver 실행
2. base_link -> laser static TF 실행
3. odom -> base_link 임시 static TF 실행
4. slam_toolbox node 실행
5. 3초 뒤 slam_toolbox configure
6. 6초 뒤 slam_toolbox activate
7. 8초 뒤 map_bridge 실행
8. start_rviz:=true이면 RViz 실행
```

이 시간차가 필요한 이유는 `/scan`, TF, `slam_toolbox` lifecycle 상태가 준비되기 전에 `map_bridge`가 먼저 pose를 조회하면 `map` frame이 없다는 경고가 반복될 수 있기 때문이다. 실제 테스트 중 발생했던 `TF lookup failed map->base_link` 문제를 줄이기 위한 구성이다.

### 5.1. RPLIDAR node

`mapping.launch.py`는 내부에서 `lidar.launch.py`를 include한다.

`lidar.launch.py`는 `rplidar_ros` package의 driver를 실행한다.

기본 설정:

```text
serial_port: /dev/ttyUSB0
serial_baudrate: 115200
frame_id: laser
scan_mode: Sensitivity
angle_compensate: true
```

역할:

```text
RPLIDAR USB serial data
-> rplidar_node
-> /scan publish
```

### 5.2. base_link -> laser TF

LiDAR는 로봇 중심에서 조금 위에 장착되어 있다고 가정했다.

현재 static transform:

```text
base_link -> laser
x = 0.0
y = 0.0
z = 0.12
roll = 0.0
pitch = 0.0
yaw = 0.0
```

즉 LiDAR가 로봇 중심에서 위쪽으로 약 12cm 떨어져 있다고 본다.

실제 장착 위치가 달라지면 `laser_x`, `laser_y`, `laser_z`, `laser_yaw` 값을 조정해야 한다.

### 5.3. 임시 odom -> base_link TF

현재 encoder odometry는 아직 테스트하지 않았다.
그래서 임시로 다음 TF를 publish한다.

```text
odom -> base_link = 0, 0, 0
```

이 node 이름은 다음이다.

```text
temporary_odom_to_base_tf
```

나중에 encoder 기반 `/odom`을 붙이면 이 임시 TF는 꺼야 한다.

```bash
ros2 launch patrol_navigation mapping.launch.py start_fake_odom:=false
```

### 5.4. slam_toolbox

`slam_toolbox`는 `/scan`을 받아서 `/map`을 만든다.

설정 파일:

```text
navigation/ros/patrol_navigation/config/slam_toolbox.yaml
```

현재 Pi에서 실제 구동하면서 `slam_toolbox`는 lifecycle node로 다룬다.
`mapping.launch.py`는 `ExecuteProcess`로 다음 명령을 시간차로 실행한다.

```text
ros2 lifecycle set /slam_toolbox configure
ros2 lifecycle set /slam_toolbox activate
```

이 과정이 끝나야 `slam_toolbox`가 정상적으로 `/scan`을 처리하고 `/map`을 publish한다.

중요 설정:

```text
mode: mapping
map_frame: map
odom_frame: odom
base_frame: base_link
scan_topic: /scan
resolution: 0.05
max_laser_range: 12.0
```

의미:

- `/scan`을 입력으로 받는다.
- 5cm 해상도 지도를 만든다.
- RPLIDAR A1M8-R6의 12m range를 기준으로 한다.
- 결과를 `/map`으로 publish한다.

### 5.5. map_bridge

`map_bridge.py`는 우리가 직접 만든 ROS2 node다.

현재 실제 launch에서는 `map_bridge`를 바로 실행하지 않고, `TimerAction(period=8.0)`로 약 8초 뒤 실행한다.
이는 RPLIDAR `/scan`, static TF, `slam_toolbox configure/activate`, `map` frame, `/map` topic이 먼저 준비될 시간을 주기 위한 것이다.

역할:

```text
ROS2 /map, /scan, TF
-> JSON 변환
-> GPU FastAPI 서버로 HTTP POST
```

기본 전송 주기:

| 데이터 | 주기 | 서버 endpoint |
| --- | --- | --- |
| map | 1.0초마다 | `POST /navigation/map` |
| pose | 0.2초마다 | `POST /navigation/pose` |
| scan | 0.2초마다 | `POST /navigation/scan` |

`map_bridge`가 읽는 것:

```text
subscribe /map
subscribe /scan
lookup TF map -> base_link
```

`map_bridge`가 보내는 것:

```text
POST http://<GPU_SERVER_IP>:21063/navigation/map
POST http://<GPU_SERVER_IP>:21063/navigation/pose
POST http://<GPU_SERVER_IP>:21063/navigation/scan
```

### 5.6. RViz2

RViz2는 ROS2 데이터를 눈으로 확인하는 시각화 도구다.

기본으로는 자동 실행하지 않는다.
필요할 때만 다음 옵션을 켠다.

```bash
start_rviz:=true
```

RViz 설정 파일:

```text
navigation/ros/patrol_navigation/rviz/mapping.rviz
```

RViz에서 보는 것:

- `/scan`: 현재 LiDAR scan 점
- `/map`: slam_toolbox가 만든 지도
- TF: `map`, `odom`, `base_link`, `laser` 관계

## 6. FastAPI 서버 연결

GPU 서버의 FastAPI는 Raspberry Pi에서 보낸 map/pose/scan을 받는다.

수신 endpoint:

| Method | Path | 역할 |
| --- | --- | --- |
| POST | `/navigation/map` | 최신 SLAM map 저장 |
| POST | `/navigation/pose` | 최신 로봇 pose 저장 |
| POST | `/navigation/scan` | 최신 LiDAR scan 저장 |

조회 endpoint:

| Method | Path | 역할 |
| --- | --- | --- |
| GET | `/api/navigation/status` | navigation 수신 상태 |
| GET | `/api/navigation/map` | 최신 map |
| GET | `/api/navigation/pose` | 최신 pose |
| GET | `/api/navigation/scan` | 최신 scan |
| POST | `/api/navigation/maps/save` | 현재 map 파일 저장 |
| GET | `/api/navigation/maps` | 저장된 map 목록 |

현재 서버에서 확인한 정상 상태 예시:

```json
{
  "robot_id": "pi-01",
  "status": "mapping",
  "has_map": true,
  "has_pose": true,
  "has_scan": true,
  "last_update_age_sec": 0.1
}
```

이 상태는 다음을 의미한다.

- Raspberry Pi에서 map이 들어오고 있다.
- pose도 들어오고 있다.
- scan도 들어오고 있다.
- 데이터가 거의 실시간으로 갱신되고 있다.

## 7. 웹 대시보드 시각화

웹 대시보드에서는 기존 `MAP AREA` 영역을 LiDAR canvas로 교체했다.

사용 파일:

```text
frontend/templates/index.html
frontend/static/script.js
frontend/static/style.css
```

표시 방식:

```text
/map  -> 누적 지도 배경
/pose -> 로봇 위치와 방향 화살표
/scan -> 현재 LiDAR scan point overlay
```

즉 웹에서는 다음 두 종류의 정보를 동시에 본다.

1. 누적 map
   - 벽, 복도, 고정 장애물처럼 SLAM에 누적된 구조
2. 실시간 scan
   - 지금 LiDAR가 바로 보고 있는 거리점
   - 사람이 지나가거나 물체가 생기면 더 즉각적으로 반응

## 8. Map 저장 기능

대시보드의 `MAP AREA`에는 `SAVE` 버튼이 있다.

이 버튼은 현재 서버가 가지고 있는 최신 `/map`을 파일로 저장한다.

저장 위치:

```text
navigation/maps/
```

저장 파일:

```text
<map_name>.pgm
<map_name>.yaml
<map_name>.meta.json
<map_name>.raw.json
```

각 파일의 의미:

| 파일 | 의미 |
| --- | --- |
| `.pgm` | ROS map server에서 쓰는 occupancy image |
| `.yaml` | map 해상도, 원점, threshold metadata |
| `.meta.json` | 프로젝트용 map metadata |
| `.raw.json` | 서버가 받은 원본 map payload |

## 9. 여러 map을 저장하면 매 scan마다 비교하는가

아니다.

일반적으로 로봇이 여러 map을 저장한다고 해서 매 scan마다 모든 map과 계속 비교하지 않는다.

보통은 다음 흐름을 쓴다.

```text
1. mapping mode에서 구역별 map 저장
2. 운영할 때 현재 구역의 active map 선택
3. active map 기준으로 localization 수행
4. 그 active map 위에서 navigation 수행
```

여러 map을 비교하는 경우는 제한적이다.

- 로봇이 어느 구역에 있는지 모를 때
- 층/건물/순찰 구역이 바뀔 때
- active map 선택이 필요한 초기화 단계

즉 현재 프로젝트에서 map 저장 기능은 **map library를 만드는 단계**다.
다음 단계에서 저장된 map 중 하나를 active map으로 선택하고, 그 map 위에서 localization과 navigation을 수행하게 된다.

## 10. 실행 명령

### 10.1. GPU 서버 실행

GPU/FastAPI 서버에서:

```bash
cd ~/capstone
uvicorn server.app:app --host 0.0.0.0 --port 21063
```

서버가 떠 있는지 Raspberry Pi에서 확인:

```bash
curl http://<GPU_SERVER_IP>:21063/api/navigation/status
```

### 10.2. Raspberry Pi ROS2 workspace 준비

라즈베리파이에 ROS2 패키지가 다음 위치에 있다고 가정한다.

```text
~/ros2_ws/src/patrol_navigation/
```

개발 서버에서 Raspberry Pi로 보낼 source는 다음 디렉터리다.

```text
capstone/navigation/ros/patrol_navigation/
```

주의할 점:

```text
capstone/navigation/ros/
```

위 경로는 현재 저장소에서 ROS2 빌드 산출물인 `build/`, `install/`, `log/`가 들어간 workspace 성격이다.
라즈베리파이에 복사해야 하는 package source 기준 경로는 `capstone/navigation/ros/patrol_navigation/`이다.

빌드:

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select patrol_navigation
source install/setup.bash
```

### 10.3. Mapping 실행

Raspberry Pi에서:

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash

ros2 launch patrol_navigation mapping.launch.py \
  serial_port:=/dev/ttyUSB0 \
  server_base_url:=http://<GPU_SERVER_IP>:21063 \
  robot_id:=pi-01
```

RViz까지 같이 띄우려면:

```bash
ros2 launch patrol_navigation mapping.launch.py \
  serial_port:=/dev/ttyUSB0 \
  server_base_url:=http://<GPU_SERVER_IP>:21063 \
  robot_id:=pi-01 \
  start_rviz:=true
```

## 11. 검증 명령

### 11.1. ROS2 topic 확인

Raspberry Pi의 다른 터미널에서:

```bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash

ros2 node list
ros2 topic list
ros2 topic hz /scan
ros2 topic hz /map
```

기대값:

```text
/scan 이 publish되어야 함
/map 이 publish되어야 함
/tf, /tf_static 이 있어야 함
```

### 11.2. TF 확인

```bash
ros2 run tf2_ros tf2_echo base_link laser
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo map base_link
```

의미:

- `base_link -> laser`: LiDAR 장착 위치 확인
- `odom -> base_link`: 현재는 임시 static TF
- `map -> base_link`: SLAM이 map frame을 만들고 pose를 계산하면 확인 가능

### 11.3. GPU 서버 수신 확인

GPU 서버 또는 같은 네트워크의 PC에서:

```bash
curl http://<GPU_SERVER_IP>:21063/api/navigation/status
curl http://<GPU_SERVER_IP>:21063/api/navigation/map
curl http://<GPU_SERVER_IP>:21063/api/navigation/pose
curl http://<GPU_SERVER_IP>:21063/api/navigation/scan
```

정상 상태:

```text
status = mapping
has_map = true
has_pose = true
has_scan = true
```

## 12. 현재 실제 검증 결과

LiDAR를 연결한 뒤 현재 확인된 상태는 다음과 같다.

```text
/api/navigation/status -> status: mapping
has_map: true
has_pose: true
has_scan: true
last_update_age_sec: 약 0.1초
```

각 API도 정상 응답했다.

```text
/api/navigation/map  -> 200
/api/navigation/pose -> 200
/api/navigation/scan -> 200
```

수신된 map 예시:

```text
frame_id: map
resolution: 약 0.05m
width: 109
height: 142
```

수신된 scan 예시:

```text
frame_id: laser
range_max: 12.0m
```

따라서 현재 결론은 다음과 같다.

```text
RPLIDAR 연결 성공
ROS2 /scan 수신 성공
slam_toolbox /map 생성 성공
map_bridge 서버 전송 성공
FastAPI map/pose/scan 수신 성공
웹 대시보드 표시 경로 연결 완료
```

## 13. 현재 한계와 다음 단계

현재 mapping은 동작하지만, navigation으로 넘어가려면 보강이 필요하다.

### 13.1. Encoder odometry 연결

현재는 임시 `odom -> base_link` static TF를 사용한다.

다음 단계에서는 motor encoder를 읽어서 실제 `/odom`을 publish해야 한다.
그래야 로봇이 이동할 때 pose가 더 자연스럽게 변하고 localization/navigation 품질이 좋아진다.

### 13.2. 저장 map 기반 localization

현재는 mapping mode다.

다음 단계는 다음과 같다.

```text
저장된 map 선택
-> localization mode 실행
-> 현재 위치 추정
-> waypoint navigation
```

### 13.3. Navigation2 또는 자체 waypoint controller

자율주행을 위해서는 두 선택지가 있다.

1. ROS2 Navigation2 사용
2. 프로젝트에 맞는 단순 waypoint controller 직접 구현

현재 프로젝트는 우선 map/pose/scan 시각화까지 완료했고, 이후 navigation 단계에서 선택하면 된다.
