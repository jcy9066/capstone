# Pi–GPU 센서 수신 및 LiDAR dry-run 자율주행 판단 결과

## 구현 요약

Raspberry Pi 카메라는 기존 FastAPI `POST /stream/h264`로 H.264 elementary stream을 HTTP chunked upload 하는 방식으로 유지했다. Raspberry Pi RPLIDAR는 기존 ROS 2 `map_bridge`의 `/scan` → `POST /navigation/scan` 전송 경로를 재사용했다. GPU 서버에는 LiDAR 거리만으로 가상 선속도·각속도와 회피 방향을 계산하는 dry-run planner를 추가했다.

이번 구현은 실제 주행 기능이 아니다. 모든 판단 결과는 API와 메모리 상태에서만 조회하며, ROS `/cmd_vel`, GPIO, serial, Pico W, MDD10A, 모터 controller 호출, WebSocket move 자동 전송을 추가하지 않았다.

## 기존 구현 재사용

- `server/app.py`: 기존 H.264 ffmpeg 디코드·상태 처리와 navigation 전역 상태·`state_lock`을 유지했다.
- `POST /stream/h264`, `GET /api/stream_status`: 기존 구현을 변경하지 않았다.
- `POST /navigation/scan`, `GET /api/navigation/status`: 기존 API를 확장해 scan 수신 때 판단을 갱신하고 status에 판단 요약을 포함했다.
- `navigation/ros/patrol_navigation/patrol_navigation/map_bridge.py`: `/scan` 구독, JSON null 변환, `max_scan_points`, HTTP timeout/retry/throttled warning 구조가 이미 요구사항을 충족해 재사용했다.
- `mapping.launch.py`: 기존 scan 전송 파라미터(`send_scan`, `scan_publish_period_sec`)를 유지했다. LiDAR-only 실행은 별도 ROS run 명령으로 제공했다.

## 생성 및 수정 파일

생성:

- `navigation/dry_run_planner.py`
- `raspberry/scripts/start_camera_stream.sh`
- `.env.example`
- `tests/test_dry_run_planner.py`
- `tests/test_navigation_api.py`
- `docs/20260728_[FULL]_Pi_GPU_센서수신_dryrun_자율주행_plan.md`
- 이 결과 문서

수정:

- `server/app.py`
- `README.md`

기존의 사용자 작업 트리에는 다수의 선행 변경이 있었으므로, 이번 작업과 무관한 파일은 되돌리거나 정리하지 않았다.

## 카메라 데이터 흐름

```text
OV5647 camera
  -> rpicam-vid --codec h264 --inline
  -> raspberry/scripts/start_camera_stream.sh
  -> curl HTTP chunked upload
  -> FastAPI POST /stream/h264
  -> ffmpeg decode / dashboard preview / optional existing inference
```

스크립트 기본값은 GPU 서버 `http://100.100.248.122:21063`, robot `pi-01`, 640x480@15 FPS, `infer=false`이다. `.env` 또는 환경 변수로 변경할 수 있으며, 업로드 종료·실패 뒤 재연결하고 SIGINT/SIGTERM에서 FIFO·카메라·curl 하위 프로세스를 정리한다. RTSP 서버는 만들지 않았다.

## LiDAR 데이터 흐름

```text
RPLIDAR A1M8
  -> ROS 2 LaserScan /scan
  -> existing map_bridge
  -> HTTP JSON POST /navigation/scan
  -> latest navigation_state.scan
  -> navigation.dry_run_planner
  -> GET /api/navigation/decision and /api/navigation/status
```

Pi bridge payload에는 `robot_id`, `frame_id`, `timestamp`, angle/range metadata, `ranges`가 포함된다. NaN·Infinity는 JSON `null`로 변환되며, 기본 실행 명령에서는 0.2초 주기와 최대 180 point를 사용한다. 서버는 malformed scan payload에 400을 반환한다.

## Dry-run 판단 구조

`navigation/dry_run_planner.py`는 ROS/FastAPI/하드웨어 의존성 없는 순수 Python 모듈이다.

- 전방: -20°~+20°
- 좌측: +20°~+90°
- 우측: -90°~-20°
- 무시 값: `None`, NaN, Infinity, 0 이하, `range_min`~`range_max` 밖 값
- 구역 거리: 유효 값의 하위 10 percentile

하위 percentile은 가까운 실제 장애물이 여러 beam에 걸쳐 관측되는 점을 유지하면서, 단일 비정상 beam이 불필요한 정지·회전을 일으키지 않게 한다.

판단은 다음과 같다.

- scan 없음: `WAITING_FOR_SCAN`
- scan timeout: `STOP` / `SCAN_TIMEOUT`
- 전방 <= stop distance: 더 넓은 안전 측으로 `TURN_LEFT` 또는 `TURN_RIGHT`, 양측이 불안전하면 `STOP`
- 전방 <= slow distance: `SLOW_AVOID`와 더 열린 측 각속도
- 전방 충분히 안전: `FORWARD`

기본 환경 변수는 `.env.example`에 있다. 결정 API는 항상 `dry_run=true`, `motor_output_enabled=false`를 반환한다. `MOTOR_OUTPUT_ENABLED=true` 동작은 구현하지 않았으므로 어떤 판단 경로도 실제 명령을 보내지 않는다.

## 실행 명령

GPU 서버는 Windows가 아닌 WSL2 Ubuntu에서 실행한다.

```bash
cd '/mnt/j/박준영_졸작/git clone/dabom_capstone'
python3 -m pip install -r requirements.txt
python3 -m uvicorn server.app:app --host 0.0.0.0 --port 21063
```

모델 없이 API만 확인할 때:

```bash
export INFERENCE_ENABLED=false
export VISUALIZATION_ENABLED=false
export MODEL_REQUIRED=false
python3 -m uvicorn server.app:app --host 0.0.0.0 --port 21063
```

Raspberry Pi 카메라:

```bash
cd ~/dabom_capstone
chmod +x raspberry/scripts/start_camera_stream.sh
SERVER_BASE_URL=http://100.100.248.122:21063 \
ROBOT_ID=pi-01 \
STREAM_INFER=false \
bash raspberry/scripts/start_camera_stream.sh
```

Raspberry Pi LiDAR only:

```bash
source /opt/ros/humble/setup.bash
cd ~/dabom_capstone/navigation/ros
colcon build --packages-select patrol_navigation
source install/setup.bash
ros2 launch patrol_navigation lidar.launch.py serial_port:=/dev/ttyUSB0 serial_baudrate:=115200
ros2 run patrol_navigation map_bridge --ros-args \
  -p robot_id:=pi-01 \
  -p server_base_url:=http://100.100.248.122:21063 \
  -p send_map:=false \
  -p send_pose:=false \
  -p send_scan:=true \
  -p scan_publish_period_sec:=0.2 \
  -p max_scan_points:=180
```

확인 API:

```bash
curl http://127.0.0.1:21063/api/stream_status
curl http://127.0.0.1:21063/api/navigation/status
curl http://127.0.0.1:21063/api/navigation/scan
curl http://127.0.0.1:21063/api/navigation/decision
```

## 테스트 및 검증 결과

성공:

- WSL `python3 -m unittest tests/test_dry_run_planner.py -v`: 10 tests passed
  - FORWARD, 좌/우 회전, SLOW_AVOID, scan 없음, timeout, invalid range, 모든 전방 값 무효, 거리 경계 포함
- WSL `bash -n raspberry/scripts/start_camera_stream.sh`: passed
- WSL `python3 -m py_compile navigation/dry_run_planner.py server/app.py tests/test_dry_run_planner.py tests/test_navigation_api.py`: passed
- WSL에 FastAPI 0.136.1, OpenCV 4.8.1.78, python-dotenv, NumPy, requests, ffmpeg 4.4.2가 설치된 것을 확인했다.

미실행:

- `pytest`는 WSL에 설치되어 있지 않다.
- `tests/test_navigation_api.py`는 FastAPI `TestClient`로 정상 scan POST, decision GET, timeout, malformed payload 400을 검증하도록 추가했지만, 실행 요청은 현재 도구의 자동 승인 사용 한도에 의해 거절되어 우회 실행하지 않았다.
- rpicam, RPLIDAR, ROS 2 Humble, Tailscale 네트워크, 실제 GPU 모델을 이 Windows/WSL 개발 환경에서 실행하지 않았다.

## Raspberry Pi 실장비 체크리스트

- `rpicam-hello` 및 `rpicam-vid`가 OV5647를 정상 인식하는지 확인
- Pi에서 GPU Tailscale IP와 port 21063 연결 확인
- GPU Windows 방화벽의 WSL inbound 경로 확인
- `ros2 topic echo /scan --once`에서 `LaserScan` 수신 확인
- bridge 실행 뒤 `GET /api/navigation/scan`에 robot/frame/ranges가 표시되는지 확인
- `GET /api/navigation/decision`의 `dry_run=true`, `motor_output_enabled=false`와 예상 action 확인
- dashboard에서 `/video_feed` 및 stream status가 live/offline으로 전환되는지 확인

## 현재 한계와 다음 단계

- odometry와 실제 위치 추정이 없다.
- 실제 모터 출력은 의도적으로 미연결이다.
- 실제 주행 검증은 수행할 수 없다.
- 현재 판단은 LiDAR 반응형 장애물 회피 시뮬레이션일 뿐이다.
- 완전한 SLAM/Nav2 기반 자율주행은 후속 작업이다.

다음 단계는 Pi 실장비에서 위 체크리스트와 API 통합 테스트를 수행하고, 안전 interlock·odometry·TF 정확도·Nav2 계획을 별도 설계/검증하는 것이다.
