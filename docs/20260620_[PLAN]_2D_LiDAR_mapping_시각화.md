# 20260620 [PLAN] 2D LiDAR mapping 시각화

## 1. 목표

Raspberry Pi에 2D LiDAR를 연결해 실내/순찰 구역의 2D map을 생성하고, 생성된 map과 로봇 위치를 관제 대시보드에서 시각화한다.

이번 작업의 1차 목표는 완전한 자율주행이 아니라 다음 흐름을 안정적으로 만드는 것이다.

```text
2D LiDAR
-> Raspberry Pi
-> ROS scan topic
-> SLAM/mapping
-> map/pose 데이터 생성
-> 서버 전송
-> 대시보드 시각화
```

목표 지표:

- Raspberry Pi에서 LiDAR scan 데이터가 5~10Hz 이상 안정적으로 수신된다.
- ROS에서 `/scan`, `/map`, `/tf` 또는 이에 준하는 topic이 정상 publish된다.
- 로봇이 저속으로 이동할 때 map이 크게 찢어지지 않고 누적된다.
- 대시보드에서 현재 map, 로봇 위치, 진행 방향, scan point 또는 장애물 정보를 확인할 수 있다.
- 기존 카메라 스트리밍/AI 탐지 경로와 충돌하지 않게 LiDAR 경로를 독립적으로 붙인다.

이번 문서는 계획만 다룬다. 실제 코드/ROS launch 파일 수정은 후속 작업에서 진행한다.

## 2. 확정 사항과 현재 전제

현재 확정된 사항은 다음과 같다.

- LiDAR 모델: `[SLAMTEC] 슬램텍 RPLIDAR A1M8-R6 360도 거리측정 라이다 센서 - 12m`
- ROS 버전: ROS 2
- 1차 범위: mapping 시각화
- SLAM 계열: `slam_toolbox`
- odometry: 모터 encoder는 있지만 현재 테스트할 수 없으므로 1차 mapping에서는 사용하지 않는다.

중요한 현재 전제:

- 현재 이 문서 작성 시점에는 Raspberry Pi에 LiDAR 장치를 연결하고 있지 않다.
- 따라서 `/dev/ttyUSB0` 같은 실제 serial device path, 권한, baudrate, `/scan` 수신 여부는 아직 검증하지 않았다.
- 추후 LiDAR를 실제로 연결한 뒤 장치 인식 결과를 기준으로 launch/config를 확정한다.
- 모터 encoder 기반 odometry는 다음 navigation 단계에서 품질 개선 항목으로 다룬다.

권장 1차 선택:

- ROS 2 기반 구성
- SLAMTEC RPLIDAR ROS 2 driver 사용
- SLAM은 `slam_toolbox` 사용
- Raspberry Pi는 LiDAR/SLAM/상태 송신을 담당
- GPU/FastAPI 서버는 map 데이터 저장과 대시보드 표시를 담당

## 3. 현재 프로젝트와 연결 지점

현재 저장소 기준 관련 영역:

- `raspberry/`
  - Raspberry Pi 테스트 클라이언트와 모터/스피커 controller stub
  - 향후 LiDAR 상태 송신 client 또는 ROS bridge client 추가 후보
- `server/app.py`
  - FastAPI 통합 서버
  - 로봇 상태, 카메라 stream, WebSocket 명령 채널 제공
  - LiDAR map/pose 수신 API와 dashboard 송출 API 추가 후보
- `frontend/`
  - 대시보드 template/static
  - map canvas 또는 SVG overlay 추가 후보
- `navigation/`
  - 현재 `.gitkeep`만 있음
  - ROS launch, mapping 설정, map 저장 스크립트 배치 후보
- `data/database/init_schema.sql`
  - `system_status`, `event_log`에 GPS/LiDAR 좌표 필드 초안 존재
  - map snapshot 또는 patrol pose log가 필요하면 확장 후보

현재 README에도 ROS/SLAM/2D LiDAR 기반 자율주행은 미완성 항목으로 정리되어 있다.
따라서 LiDAR 기능은 기존 카메라/AI 경로를 건드리기보다 `navigation/`과 별도 API로 먼저 붙이는 방식이 적합하다.

## 4. 전체 아키텍처

### 4.1. 1차 mapping/시각화 구조

```text
Raspberry Pi
  RPLIDAR A1M8-R6 USB serial 연결
  -> SLAMTEC RPLIDAR ROS 2 driver
  -> /scan
  -> slam_toolbox
  -> /map, /tf, /pose
  -> map_bridge.py
  -> HTTP/WebSocket/MQTT 중 하나로 서버 전송

현재 상태
  LiDAR 장치는 아직 연결되어 있지 않음
  -> 실제 연결 후 serial path, 권한, scan rate 검증 필요

GPU/FastAPI 서버
  -> map/pose 수신
  -> 최신 map state 보관
  -> dashboard API/WebSocket publish

Dashboard
  -> 2D map view
  -> robot pose arrow
  -> scan/obstacle overlay
  -> mapping status 표시
```

### 4.2. ROS 내부 topic 후보

| Topic | 역할 | 비고 |
| --- | --- | --- |
| `/scan` | LiDAR 거리 scan | driver에서 publish |
| `/map` | OccupancyGrid map | SLAM node에서 publish |
| `/tf` | 좌표계 변환 | `map -> odom -> base_link -> laser` |
| `/odom` | 로봇 odometry | 1차 mapping에서는 사용하지 않음. encoder 검증 후 navigation 단계에서 연결 |
| `/pose` 또는 `/tracked_pose` | 추정 위치 | 1차에서는 `slam_toolbox` mapping 중 추정 pose로 사용 |

좌표계 기본안:

```text
map
└── odom
    └── base_link
        └── laser
```

LiDAR가 로봇 중심에서 앞/뒤/위로 얼마나 떨어져 있는지 `laser` frame의 static transform으로 명시해야 한다.

## 5. 단계별 작업 계획

### 5.1. 1단계: 하드웨어 연결 확인

목표:

- Raspberry Pi에서 RPLIDAR A1M8-R6가 USB serial 장치로 인식되는지 확인한다.
- 전원 부족, serial 권한, baudrate 문제를 먼저 제거한다.

확인 항목:

- `lsusb`로 장치 인식 여부 확인
- `/dev/ttyUSB0`, `/dev/ttyACM0` 등 serial device 확인
- 사용자 권한 확인
  - `dialout` group 필요 여부 확인
- LiDAR 전원 안정성 확인
  - Raspberry Pi USB 전원이 부족하면 별도 전원 또는 powered USB hub 사용

예상 산출물:

- RPLIDAR A1M8-R6 인식 정보
- serial device path
- baudrate
- 정상 회전 여부
- `/scan` 수신 가능 여부
- 현재 미연결 상태에서 연결 완료 상태로 전환된 시점

### 5.2. 2단계: ROS driver 설치 및 `/scan` 확인

목표:

- SLAMTEC RPLIDAR ROS 2 driver를 실행해 `/scan` topic을 publish한다.
- RViz 또는 console topic echo로 scan 데이터를 확인한다.

작업:

- `navigation/ros/` 아래에 RPLIDAR launch/config 파일을 둔다.
- RPLIDAR A1M8-R6 설정을 별도 config로 둔다.
- serial port를 직접 `/dev/ttyUSB0`로 고정하지 않고 udev rule 또는 launch argument로 설정한다.
- 현재는 LiDAR가 미연결 상태이므로 실제 port 값은 연결 후 확정한다.

예상 구조:

```text
navigation/
  ros/
    launch/
      lidar.launch.py
      mapping.launch.py
    config/
      rplidar_a1m8.yaml
      slam_toolbox.yaml
    scripts/
      map_bridge.py
      save_map.sh
```

검증:

```bash
ros2 topic list
ros2 topic hz /scan
ros2 topic echo /scan --once
```

### 5.3. 3단계: SLAM으로 map 생성

목표:

- `/scan`을 입력으로 받아 `/map`을 생성한다.
- 로봇을 천천히 움직였을 때 주변 구조가 누적되는지 확인한다.

작업:

- `slam_toolbox` 설정 작성
- `base_link -> laser` static transform 설정
- 모터 encoder odometry는 1차 mapping에서 제외하고 LiDAR scan matching 중심으로 시작
- TF tree 연결을 위해 1차에서는 임시 `odom -> base_link` static transform을 사용한다.
- encoder 기반 실제 `/odom` 연결은 다음 navigation 단계에서 map 품질 개선 항목으로 진행하며, 이때 임시 static transform은 끈다.
- RC카가 너무 빠르게 회전하지 않도록 mapping 중 주행 속도 제한

초기 운용 원칙:

- mapping 시 직선 이동과 완만한 회전을 사용한다.
- 좁은 공간에서 빠른 제자리 회전을 피한다.
- 유리, 검은색 물체, 얇은 다리 같은 LiDAR 취약 물체를 따로 기록한다.

map 저장 산출물:

```text
navigation/maps/
  patrol_area.yaml
  patrol_area.pgm
  patrol_area.meta.json
```

`meta.json`에는 다음 정보를 둔다.

```json
{
  "map_name": "patrol_area",
  "robot_id": "pi-01",
  "created_at": "2026-06-20T00:00:00Z",
  "lidar_model": "SLAMTEC RPLIDAR A1M8-R6",
  "resolution": 0.05,
  "frame_id": "map"
}
```

### 5.4. 4단계: 서버 전송 bridge 구현

목표:

- Raspberry Pi의 ROS topic을 기존 FastAPI 서버가 이해할 수 있는 JSON 형태로 변환해 전송한다.
- 카메라 streaming과 별도 경로로 운영한다.

전송 데이터는 1차에서 너무 무겁게 보내지 않는다.

권장 1차 API:

```http
POST /navigation/map
POST /navigation/pose
GET  /api/navigation/status
GET  /api/navigation/map
```

map payload 후보:

```json
{
  "robot_id": "pi-01",
  "frame_id": "map",
  "resolution": 0.05,
  "width": 384,
  "height": 384,
  "origin": [-9.6, -9.6, 0.0],
  "data_encoding": "rle",
  "data": "..."
}
```

pose payload 후보:

```json
{
  "robot_id": "pi-01",
  "frame_id": "map",
  "x": 1.25,
  "y": -0.42,
  "yaw": 1.57,
  "linear_velocity": 0.12,
  "angular_velocity": 0.03,
  "timestamp": "2026-06-20T00:00:00Z"
}
```

전송 주기:

- pose: 5~10Hz
- scan point overlay: 필요 시 1~5Hz
- full map: 변경 시 또는 0.5~1Hz
- 대시보드 표시용 downsample map: 필요 시 서버에서 생성

### 5.5. 5단계: 대시보드 map 시각화

목표:

- 기존 대시보드에 map panel을 추가한다.
- 실시간 카메라 영상과 함께 로봇의 현재 위치를 확인할 수 있게 한다.

1차 UI 구성:

- map canvas
- occupancy grid 표시
  - unknown: 회색
  - free: 흰색 또는 옅은 색
  - occupied: 진한 색
- 로봇 위치 arrow
- LiDAR scan point overlay
- mapping 상태 badge
  - `offline`
  - `scan only`
  - `mapping`
  - `stale`
- map 저장/초기화 버튼은 2차로 분리
- `localized` 상태는 저장 map 기반 localization을 붙이는 navigation 단계에서 추가

구현 방식:

- `frontend/static/script.js`에서 navigation API polling 또는 WebSocket 수신
- `canvas` 2D context로 occupancy grid 렌더링
- map 이미지와 pose overlay를 분리해 pose 갱신 때 전체 map을 매번 다시 그리지 않도록 최적화

### 5.6. 6단계: map 저장

목표:

- 1차 mapping 결과를 파일로 저장하고, 이후 navigation 단계에서 재사용할 수 있게 정리한다.

작업:

- mapping mode에서 새 map 생성
- map 파일 저장
- 서버에는 현재 생성 중인 map 이름과 revision을 전송
- 저장된 map 기반 localization은 1차 범위에서 제외하고 navigation 단계에서 진행

후속 navigation 연결:

- waypoint patrol
- 금지 구역/관심 구역 polygon
- 장애물 감지 시 정지 또는 우회
- 이상행동 이벤트 발생 시 LiDAR 좌표와 영상 이벤트를 함께 기록

## 6. 구현 대상 파일 후보

새로 추가할 파일:

- `navigation/ros/launch/lidar.launch.py`
- `navigation/ros/launch/mapping.launch.py`
- `navigation/ros/config/rplidar_a1m8.yaml`
- `navigation/ros/config/slam_toolbox.yaml`
- `navigation/ros/scripts/map_bridge.py`
- `navigation/maps/.gitkeep`
- `docs/20260620_[RESULT]_2D_LiDAR_mapping_시각화.md`

수정 후보:

- `server/app.py`
  - navigation map/pose 수신 API 추가
  - dashboard navigation 상태 API 추가
- `frontend/templates/index.html`
  - map panel 추가
- `frontend/static/script.js`
  - map/pose fetch 또는 WebSocket 처리
  - canvas rendering
- `frontend/static/style.css`
  - dashboard map panel styling
- `README.md`
  - LiDAR 연결/실행 명령 추가
- `requirements.txt`
  - 서버 쪽에 추가 dependency가 필요한 경우만 반영

ROS dependency는 Python 서버 requirements와 분리해서 관리한다.
`requirements.txt`에 ROS package를 섞지 않는다.

## 7. 검증 계획

### 7.1. 단독 센서 검증

현재는 LiDAR 장치를 연결하지 않았으므로, 아래 검증은 추후 실제 연결 후 수행한다.

- 현재 LiDAR 미연결 상태임을 기록
- LiDAR 연결 후 전원과 회전 확인
- serial device 확인
- `/scan` publish 확인
- `/scan` frequency 확인
- RViz에서 LaserScan 표시 확인

통과 기준:

- `/scan`이 5분 이상 끊기지 않는다.
- scan rate가 센서 설정값 근처에서 유지된다.
- 유효 거리값이 지나치게 많이 0 또는 infinity로 나오지 않는다.

### 7.2. mapping 검증

- 로봇을 손으로 밀거나 저속 주행하며 작은 구역 map 생성
- 복도/방 모서리/장애물 위치가 실제와 비슷하게 누적되는지 확인
- 같은 위치로 돌아왔을 때 map이 크게 어긋나지 않는지 확인

통과 기준:

- 벽과 큰 장애물이 일관되게 표현된다.
- 천천히 한 바퀴 이동 후 시작점 근처 위치가 크게 튀지 않는다.
- map 저장 후 다시 열었을 때 scale/origin이 유지된다.

### 7.3. 서버 연동 검증

- Raspberry Pi에서 pose payload 전송
- 서버 API에서 최신 pose 조회
- map payload 전송 후 dashboard에서 표시
- 카메라 stream과 동시에 실행해 CPU/network 충돌 확인

통과 기준:

- pose가 5Hz 이상 dashboard에 반영된다.
- map 갱신 중에도 카메라 preview가 끊기지 않는다.
- 서버가 LiDAR 전송 중단을 `offline` 상태로 표시한다.

### 7.4. 장시간 검증

- 10분 mapping 테스트
- 30분 dashboard 표시 테스트
- Wi-Fi 환경에서 packet loss/재연결 확인

통과 기준:

- 메모리 사용량이 계속 증가하지 않는다.
- LiDAR bridge 재시작 시 서버가 최신 상태를 다시 받는다.
- dashboard가 오래된 pose를 현재 위치처럼 표시하지 않는다.

## 8. 위험 요소와 대응

| 위험 요소 | 영향 | 대응 |
| --- | --- | --- |
| RPLIDAR ROS 2 driver/serial 설정 오류 | `/scan` 미수신 | 연결 후 port, baudrate, udev rule을 먼저 검증 |
| Raspberry Pi 전원 부족 | scan 끊김, USB disconnect | 별도 전원 또는 powered hub 사용 |
| encoder odometry 미사용 | map 품질 저하 | 1차는 저속 mapping, navigation 단계에서 encoder `/odom` 연결 |
| 빠른 회전/진동 | scan matching 실패 | mapping mode 속도 제한 |
| map payload 과대 | dashboard/network 부하 | RLE/downsample/변경분 전송 |
| 좌표계 불일치 | 로봇 위치 표시 오류 | `map`, `odom`, `base_link`, `laser` frame 규칙 문서화 |
| 카메라/AI와 동시 실행 부하 | latency 증가 | LiDAR 전송 주기 제한, map/pose 분리 |

## 9. 작업 순서 제안

1. LiDAR 연결 전제와 RPLIDAR A1M8-R6/ROS 2 구성 확정
2. 추후 LiDAR 연결 후 Raspberry Pi에서 serial 인식 확인
3. SLAMTEC RPLIDAR ROS 2 driver 실행 및 `/scan` 확인
4. RViz에서 LaserScan 시각화
5. SLAM launch 작성 및 `/map` 생성
6. map 저장 절차 정리
7. `map_bridge.py`로 서버에 pose부터 전송
8. 서버에 `/navigation/pose`, `/api/navigation/status` 추가
9. dashboard에 로봇 위치 표시
10. map payload 전송과 canvas occupancy grid 표시
11. 카메라 streaming과 동시 운용 테스트
12. 결과 문서 작성

## 10. 완료 기준

1차 완료 기준:

- Raspberry Pi에서 LiDAR scan이 정상 수신된다.
- ROS SLAM으로 테스트 구역의 2D map을 만들 수 있다.
- 서버가 Raspberry Pi의 map/pose 상태를 수신한다.
- 대시보드에서 map과 로봇 위치가 보인다.
- LiDAR가 끊겼을 때 dashboard에 offline 또는 stale 상태가 표시된다.

2차 확장 기준:

- 저장된 map으로 localization mode를 실행한다.
- 모터 encoder 기반 `/odom`을 연결해 localization/navigation 품질을 개선한다.
- waypoint patrol과 연결한다.
- 이벤트 발생 시 카메라 탐지 결과에 LiDAR 좌표를 함께 기록한다.
- 장애물 감지에 따른 emergency stop 또는 회피 동작을 붙인다.
