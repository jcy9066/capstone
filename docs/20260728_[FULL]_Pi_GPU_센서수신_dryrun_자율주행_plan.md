# Pi–GPU 센서 수신 및 LiDAR dry-run 자율주행 판단 계획

## 목적과 범위

Raspberry Pi의 카메라 H.264 스트림과 RPLIDAR `/scan` 데이터를 기존 FastAPI 통합 서버로 전달하고, GPU 서버에서 LiDAR 거리만으로 **실제 주행 없이** 회피 방향·가상 속도를 계산하는 dry-run 판단 단계를 추가한다. 이번 작업은 SLAM/Nav2 완성, odometry, 모터·GPIO·Pico W·MDD10A 제어를 포함하지 않는다.

## 기존 구현 확인 결과

- `server/app.py`에는 `POST /stream/h264`, ffmpeg H.264 디코딩, `/api/stream_status`, `/navigation/map`, `/navigation/pose`, `/navigation/scan`, `/api/navigation/status`가 이미 있다.
- `navigation/ros/patrol_navigation/patrol_navigation/map_bridge.py`는 `/scan`을 구독하여 JSON으로 `/navigation/scan`에 전송한다. 기존 map/pose 전송과 retry/log throttling 구조를 재사용한다.
- `mapping.launch.py`는 map bridge에 `scan_topic`, `scan_period_sec`, `scan_max_ranges` 인자를 이미 전달한다.
- 실제 구동 경로를 만들지 않으며, `/cmd_vel`, GPIO, serial, Pico W, MDD10A, `motor_controller.move()`를 호출하거나 연결하지 않는다.

## 구현 방침

1. `raspberry/scripts/start_camera_stream.sh`를 추가한다. `rpicam-vid` stdout을 curl HTTP chunked upload로 기존 `/stream/h264`에 전달한다. `.env`를 선택적으로 불러오고, 기본 `infer=false`, 재연결 backoff, signal cleanup을 둔다.
2. 기존 `map_bridge.py`를 최소 수정해 scan 전송 값을 명시적으로 검증하고, NaN/Infinity를 JSON `null`로 바꾸며, 최대 range 수와 주기를 파라미터화한다. map/pose 구조와 독립된 LiDAR-only 실행 방법을 launch 파일로 제공한다.
3. `navigation/dry_run_planner.py`에 ROS/FastAPI와 분리된 순수 판단 함수를 둔다. LaserScan을 전방(-20°~+20°), 좌(+20°~+90°), 우(-90°~-20°)로 나누고 유효 거리의 하위 percentile을 사용해 한 개의 이상치가 회피 판단을 지배하지 않도록 한다.
4. `server/app.py`의 기존 `navigation_state`와 `state_lock`을 재사용한다. scan POST 때 dry-run 판단을 갱신하고, `GET /api/navigation/decision` 및 확장된 `/api/navigation/status`에서 읽기 전용 상태를 제공한다. 모든 응답에는 `dry_run=true`과 실제 제어가 수행되지 않음을 명시한다.
5. `.env`는 수정하지 않는다. `.env.example`과 README에 WSL GPU 서버·Pi 실행 명령, API 점검, 환경 변수, 실장비 체크리스트를 추가한다.
6. planner 단위 테스트와 FastAPI 통합 테스트를 추가한다. WSL의 Python 문법 검사, 테스트, shell script 문법 검사, diff check를 수행한다. ROS 2·RPLIDAR·카메라·GPU 실장비 검증은 실행하지 않았음을 결과 문서에 구분해 기록한다.

## 안전 경계

- `MOTOR_OUTPUT_ENABLED` 기본값은 `false`로 문서화하며, 이번 코드에는 이를 `true`일 때 동작시키는 구현이 없다.
- WebSocket robot command 채널에는 move 명령을 자동 전송하지 않는다.
- scan timeout, scan 부재, 모든 값 무효 상태는 정지 또는 대기 판단만 반환한다.

## 검증 기준

- planner: 전진, 좌/우 회전, slow avoid, scan 부재, timeout, 무효 range, 임계값 경계를 검사한다.
- API: 정상 scan POST, decision 조회, timeout 반영, 잘못된 scan payload의 400을 검사한다.
- H.264 기존 경로는 정적 확인만 하며 실제 ffmpeg/camera 스트림을 이 Windows/WSL 개발 환경에서 생성하지 않는다.
