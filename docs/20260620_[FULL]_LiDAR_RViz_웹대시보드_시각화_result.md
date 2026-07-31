# 20260620 [FULL] LiDAR RViz 및 웹 대시보드 시각화 결과

## 1. 작업 결과

LiDAR mapping 결과를 두 경로에서 확인할 수 있게 구성했다.

- RViz2: ROS2 로컬 확인용
- 웹 대시보드: 기존 카메라 화면 위 `MAP AREA` 영역

현재 LiDAR 장치는 아직 연결되어 있지 않으므로 실제 `/scan`, `/map`, RViz 화면, 웹 실시간 변화는 추후 RPLIDAR A1M8-R6 연결 후 검증한다.

## 2. RViz 연결

추가 파일:

```text
navigation/ros/patrol_navigation/rviz/mapping.rviz
```

수정 파일:

```text
navigation/ros/patrol_navigation/launch/mapping.launch.py
navigation/ros/patrol_navigation/setup.py
navigation/ros/patrol_navigation/package.xml
```

변경 내용:

- `start_rviz` launch argument 추가
- `rviz_config` launch argument 추가
- `rviz2 -d mapping.rviz` node 추가
- RViz display 기본값으로 `/map`, `/scan`, TF 구성
- `package.xml`에 `rviz2` ROS2 의존성 추가

실행 예시:

```bash
cd ~/capstone/navigation/ros
colcon build --packages-select patrol_navigation
source install/setup.bash
ros2 launch patrol_navigation mapping.launch.py   serial_port:=/dev/ttyUSB0   server_base_url:=http://<GPU_SERVER_IP>:21063   robot_id:=pi-01   start_rviz:=true
```

RViz를 띄우지 않고 서버/웹 대시보드만 연결하려면 기본값 그대로 실행한다.

```bash
ros2 launch patrol_navigation mapping.launch.py   serial_port:=/dev/ttyUSB0   server_base_url:=http://<GPU_SERVER_IP>:21063   robot_id:=pi-01
```

## 3. 웹 대시보드 연결

수정 파일:

```text
frontend/templates/index.html
frontend/static/script.js
frontend/static/style.css
```

변경 내용:

- 기존 `MAP AREA` placeholder를 `canvas#lidar-map-canvas`로 교체
- `/api/navigation/status` polling 추가
- `/api/navigation/map` polling 추가
- `/api/navigation/pose` polling 추가
- `/api/navigation/scan` polling 추가
- OccupancyGrid RLE map decode 및 canvas 렌더링 추가
- 로봇 pose 화살표 렌더링 추가
- 현재 LaserScan point overlay 렌더링 추가
- stale/offline/mapping 상태 label 표시 추가
- 미니맵 확대/축소 시 canvas 재렌더링 추가

웹 표시 구성:

```text
/map  -> 누적 OccupancyGrid 지도 배경
/pose -> 로봇 위치 및 진행 방향 화살표
/scan -> 현재 LiDAR scan point overlay
```

## 4. scan 실시간 overlay

웹에서 주변 환경 변화를 즉각적으로 보기 위해 `map_bridge` 기본 설정을 변경했다.

```text
send_scan: true
scan_publish_period_sec: 0.2
```

따라서 bridge가 실행되면 서버는 최신 scan을 `/navigation/scan`으로 받고, 대시보드는 `/api/navigation/scan`을 통해 scan point를 overlay한다.

## 5. 의존성

새 pip 패키지는 추가하지 않았다.

- `requirements.txt` 변경 없음
- ROS2 의존성은 `package.xml`에만 반영
- 추가 ROS2 의존성: `rviz2`

## 6. 검증 결과

수행한 검증:

```bash
python3 -m py_compile   capstone/server/app.py   capstone/navigation/ros/patrol_navigation/patrol_navigation/map_bridge.py   capstone/navigation/ros/patrol_navigation/launch/lidar.launch.py   capstone/navigation/ros/patrol_navigation/launch/mapping.launch.py   capstone/navigation/ros/patrol_navigation/setup.py
```

결과: 통과.

```bash
node --check capstone/frontend/static/script.js
```

결과: 통과.

```bash
colcon list --base-paths capstone/navigation/ros
```

결과:

```text
patrol_navigation capstone/navigation/ros/patrol_navigation (ros.ament_python)
```

현재 환경에서는 `ros2` CLI가 잡히지 않고 LiDAR도 연결되어 있지 않으므로, 실제 RViz 실행과 `/scan`/`/map` 확인은 추후 하드웨어 연결 후 진행한다.

## 7. 다음 확인 항목

1. Raspberry Pi에 RPLIDAR A1M8-R6 연결
2. `/dev/ttyUSB0` 또는 실제 serial path 확인
3. `ros2 launch patrol_navigation mapping.launch.py start_rviz:=true` 실행
4. RViz에서 `/scan`, `/map`, TF 확인
5. FastAPI 서버 실행 후 웹 대시보드 접속
6. `MAP AREA` 영역에서 map, pose, scan overlay 확인
