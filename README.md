# Autonomous Patrol Bot

Raspberry Pi 3 Model B (1GB) 기반 이동 로봇과 GPU 서버를 연결한 자율주행 AI 방범 로봇 프로젝트다.

Raspberry Pi는 카메라·LiDAR·바퀴 엔코더 수집과 Pico W 모터 제어, 센서/영상 전송을 담당한다. GPU 서버는 FastAPI 관제 서버, 영상 AI 분석, ROS 2 Mapping·Localization·Nav2, 지도 관리와 웹 대시보드를 담당한다.

> Pi: Raspberry Pi 3 Model B 1GB / Ubuntu Server 22.04 arm64  
> ROS 2: Humble / Server Port: `21063` / Robot ID: `pi-01`

## 프로젝트 실행 방법

### 1. 공통 준비

```bash
git clone https://github.com/jcy9066/dabom_capstone.git
cd dabom_capstone
```

환경 변수 파일을 생성한다.

```bash
cp .env.example .env
```

실행 스크립트 권한을 부여한다.

```bash
chmod +x server/scripts/start_gpu_server.sh
chmod +x raspberry/scripts/setup_pi3b.sh
chmod +x raspberry/scripts/validate_pi3b.sh
chmod +x raspberry/scripts/start_camera_stream.sh
chmod +x raspberry/scripts/start_robot_command_client.sh
chmod +x raspberry/scripts/start_lidar_sender.sh
```

---

### 2. Raspberry Pi 3B 최초 설정

현재 로봇의 Raspberry Pi 기준 환경은 다음과 같다.

```text
Board: Raspberry Pi 3 Model B (non-Plus)
RAM: 1GB
OS: Ubuntu Server 22.04 64-bit (arm64/aarch64)
Wi-Fi: built-in 2.4GHz
ROS 2: Humble
```

Pi의 역할은 다음으로 제한한다.

```text
OV5647 H.264 capture/stream
RPLIDAR /scan collection/forwarding
Pico W UART motor/LED control
encoder telemetry forwarding
WebSocket / HTTP communication
```

다음 연산은 GPU Server에서 수행한다.

```text
SLAM Toolbox
Localization / AMCL
Nav2
AI Perception
FastAPI / Web Dashboard
DB / logging
```

#### Pi 3B 시스템 설정

Pi 3B에서 repository와 `.env`를 준비한 뒤 실행한다.

```bash
cd ~/dabom_capstone
sudo bash raspberry/scripts/setup_pi3b.sh
```

`setup_pi3b.sh`는 다음을 설정한다.

- Pi 3 Model B 및 `aarch64` 확인
- GPIO14/15 UART 활성화
- Bluetooth 비활성화
- PL011 UART를 `/dev/serial0` primary UART로 사용
- Linux serial console의 UART 점유 제거
- `dialout`, `video`, `render` device group 설정
- Wi-Fi power saving OFF 및 재부팅 후 유지
- `.env`의 Pi 3B camera/UART 기본값 적용

설정 후 반드시 재부팅한다.

```bash
sudo reboot
```

재부팅 후 read-only 환경 검증을 실행한다.

```bash
cd ~/dabom_capstone
bash raspberry/scripts/validate_pi3b.sh
```

핵심 정상 기준:

```text
Board = Raspberry Pi 3 Model B
Architecture = aarch64
OS = Ubuntu 22.04
/dev/serial0 -> /dev/ttyAMA0
Bluetooth/hciuart inactive
Wi-Fi connected on 2.4GHz
Wi-Fi power saving OFF
ROS 2 Humble available
rpicam-vid available
OV5647 detected when connected
/dev/ttyUSB0 present when RPLIDAR is connected
```

#### UART 배선

```text
Raspberry Pi GPIO14 / TXD (physical pin 8)
    -> Pico W GP1 / UART0 RX

Raspberry Pi GPIO15 / RXD (physical pin 10)
    <- Pico W GP0 / UART0 TX

Raspberry Pi GND
    <-> Pico W GND
```

기본 UART 설정:

```text
Port: /dev/serial0
Physical UART after setup: PL011 / ttyAMA0
Baudrate: 115200
Format: 8N1
```

#### Pi 3B 카메라 기본 profile

```text
STREAM_WIDTH=1280
STREAM_HEIGHT=720
STREAM_FPS=15
STREAM_BITRATE=2500000
```

Pi 3B는 내장 5GHz Wi-Fi를 지원하지 않으므로 로봇 운용 AP는 반드시 2.4GHz를 제공해야 한다.

Python dependency를 준비한다.

```bash
cd ~/dabom_capstone
python3 -m pip install -r raspberry/requirements.txt
```

ROS 2 Humble, `rpicam-vid`, RPLIDAR ROS driver는 Pi에 별도로 설치되어 있어야 한다.

---

### 3. GPU Server 실행

#### 최초 1회: Python 및 ROS package 준비

```bash
cd ~/dabom_capstone
python3 -m pip install -r requirements.txt

source /opt/ros/humble/setup.bash
cd navigation/ros
colcon build --symlink-install --packages-select patrol_navigation
cd ../..
```

#### 서버 실행

```bash
cd ~/dabom_capstone
bash server/scripts/start_gpu_server.sh
```

이 스크립트는 다음 항목을 함께 실행한다.

- FastAPI 통합 서버
- Encoder ROS bridge
- `/wheel_ticks` 기반 wheel odometry
- `/odom` topic
- `odom -> base_link` TF

AI 모델 없이 서버와 대시보드만 실행하려면:

```bash
cd ~/dabom_capstone
INFERENCE_ENABLED=false VISUALIZATION_ENABLED=false MODEL_REQUIRED=false bash server/scripts/start_gpu_server.sh
```

대시보드 접속:

```text
http://<GPU_SERVER_IP>:21063
```

---

### 4. Raspberry Pi 실행

Pi에서는 아래 세 스크립트를 **각각 별도 터미널**에서 실행한다.

#### 터미널 1: 카메라 전송

```bash
cd ~/dabom_capstone
bash raspberry/scripts/start_camera_stream.sh
```

동작:

```text
OV5647
  -> rpicam-vid H.264
  -> HTTP chunked upload
  -> GPU Server /stream/h264
```

#### 터미널 2: 모터 명령 및 엔코더 전송

```bash
cd ~/dabom_capstone
bash raspberry/scripts/start_robot_command_client.sh
```

동작:

```text
GPU WebSocket command
  -> Raspberry Pi 3B
  -> UART /dev/serial0
  -> Pico W
  -> MDD10A

Pico W encoder
  -> UART
  -> Raspberry Pi 3B WebSocket
  -> GPU /wheel_ticks
```

기본 UART 설정:

```text
Port: /dev/serial0
Baudrate: 115200
```

#### 터미널 3: LiDAR 전송

최초 1회 ROS package를 빌드한다.

```bash
source /opt/ros/humble/setup.bash
cd ~/dabom_capstone/navigation/ros
colcon build --symlink-install --packages-select patrol_navigation
```

LiDAR driver와 WebSocket sender를 실행한다.

```bash
cd ~/dabom_capstone
bash raspberry/scripts/start_lidar_sender.sh
```

동작:

```text
RPLIDAR A1M8
  -> Pi ROS 2 /scan
  -> WebSocket
  -> GPU ROS 2 /scan
```

기본 LiDAR 설정:

```text
Port: /dev/ttyUSB0
Baudrate: 115200
Frame: laser
```

---

### 5. 실행 확인

GPU Server:

```bash
curl http://127.0.0.1:21063/api/stream_status
curl http://127.0.0.1:21063/api/lidar/bridge
curl http://127.0.0.1:21063/api/encoder/bridge
curl http://127.0.0.1:21063/api/navigation/status
```

ROS 2:

```bash
source /opt/ros/humble/setup.bash
source ~/dabom_capstone/navigation/ros/install/setup.bash

ros2 topic hz /scan
ros2 topic hz /wheel_ticks
ros2 topic hz /odom
ros2 run tf2_ros tf2_echo odom base_link
```

정상 실행 기준:

```text
카메라: dashboard에서 실시간 영상 출력
LiDAR: /scan 지속 발행
엔코더: /wheel_ticks 지속 발행
Odometry: /odom 및 odom -> base_link TF 발행
Pi: /ws/robot/pi-01 연결
```

Pi 3B 전환 후 최초 통합 검증은 다음 순서로 수행한다.

```text
1. validate_pi3b.sh PASS/WARN 확인
2. Pico W UART PING/ACK 확인
3. encoder stream 확인
4. RPLIDAR /scan 확인
5. LiDAR WebSocket -> GPU /scan 확인
6. 1280x720 15FPS H.264 stream 확인
7. camera + LiDAR + UART/encoder 동시 실행
8. 수동 주행
9. Mapping
10. 저장 지도 + AMCL + Nav2 검증
```

---

## Codex 개발 자동화 구성

본 프로젝트는 Codex 기반 개발을 위해 Skill, Hook, Sub-Agent, MCP와 linked Git worktree를 사용한다.

```text
dabom_capstone/
├─ AGENTS.md
├─ .agents/
│  └─ skills/
│     ├─ implement-feature/SKILL.md
│     ├─ validate-server/
│     │  ├─ SKILL.md
│     │  └─ scripts/validate_server.py
│     ├─ validate-dashboard/
│     │  ├─ SKILL.md
│     │  └─ references/
│     │     ├─ dashboard_flows.md
│     │     └─ expected_states.md
│     ├─ validate-navigation/
│     │  ├─ SKILL.md
│     │  ├─ scripts/validate_navigation.py
│     │  └─ references/ros_interfaces.md
│     ├─ validate-raspberry/
│     │  ├─ SKILL.md
│     │  ├─ scripts/validate_uart_protocol.py
│     │  └─ references/uart_protocol.md
│     └─ review-change/
│        ├─ SKILL.md
│        └─ scripts/review_change.py
├─ .codex/
│  ├─ config.toml
│  ├─ hooks.json
│  ├─ agents/
│  │  ├─ code-explorer.toml
│  │  ├─ dashboard-reviewer.toml
│  │  ├─ ros-reviewer.toml
│  │  ├─ hardware-reviewer.toml
│  │  └─ test-reviewer.toml
│  └─ hooks/
│     ├─ pre_tool_policy.py
│     └─ validate_on_stop.py
└─ raspberry/
   └─ scripts/
      ├─ setup_pi3b.sh
      └─ validate_pi3b.sh
```

### AGENTS.md

루트에 하나만 유지하며 다음 공통 규칙을 정의한다.

- 통합 서버 기준은 `server/app.py`이다.
- ROS 2 package는 `navigation/ros/patrol_navigation/`이다.
- Raspberry Pi target은 Pi 3 Model B 1GB + Ubuntu Server 22.04 arm64이다.
- Raspberry Pi client는 `raspberry/robot_command_client.py`이다.
- Pi 3B provisioning은 `raspberry/scripts/setup_pi3b.sh`이다.
- Pi 3B read-only 검증은 `raspberry/scripts/validate_pi3b.sh`이다.
- Pico W firmware 기준은 `raspberry/pico_w_sdk/main.c`이다.
- 수정 전 실제 import, API, launch 및 실행 경로를 확인한다.
- 요청 범위 밖 파일은 수정하지 않는다.
- 변경 영역에 해당하는 검증 Skill을 실행한다.
- 하드웨어 미연결 상태에서 실제 동작을 검증했다고 표현하지 않는다.
- `setup_pi3b.sh`는 시스템 상태를 변경하므로 Agent가 자동 실행하지 않는다.
- 모터, GPIO, Pico W flash는 명시적 요청 없이 실행하지 않는다.
- `.env`, token, weight, build 결과 및 runtime 생성물을 커밋하지 않는다.
- `main`과 `dev`에서는 source/config commit을 생성하지 않는다.
- 구현은 별도 linked feature worktree에서 수행한다.
- branch 간 merge/cherry-pick/rebase는 사용자가 직접 수행한다.

### Skills

- `implement-feature`: 영향 범위 조사, 코드 수정, 영역별 검증 및 결과 보고
- `validate-server`: FastAPI, 인증, WebSocket, DB, Python 및 API 검증
- `validate-dashboard`: Playwright MCP를 이용한 로그인, UI, console, network 검증
- `validate-navigation`: ROS 2 package, launch, config, TF, topic 및 Nav2 검증
- `validate-raspberry`: Pi 3B runtime 설정 + Pi/Pico UART protocol + encoder + timeout/failsafe 검증
- `review-change`: secret, backup, build 결과, 생성 지도, 중복 파일 및 테스트 누락 확인

Pi 3B 관련 변경의 기본 정적 검증:

```bash
bash -n raspberry/scripts/setup_pi3b.sh raspberry/scripts/validate_pi3b.sh
python .agents/skills/validate-raspberry/scripts/validate_uart_protocol.py
```

`validate_pi3b.sh`의 실제 하드웨어 판정은 Pi 3B 실기기에서 실행한 결과만 인정한다.

Browser 검증에서는 실제 이동, 신고, 경고 방송, ROS process 변경, 지도 삭제 등 파괴적 동작을 수행하지 않는다.

### Hooks

#### `pre_tool_policy.py`

현재 Git 정책은 다음과 같다.

허용:

```text
read-only Git commands
git switch --no-guess <existing-branch>
새 feature branch 생성
git worktree add -b <branch> <path> [start-point]
non-protected linked worktree에서 task-scoped git add
non-protected linked worktree에서 새 commit
```

차단:

```text
main/dev에서 add/commit
push, pull, fetch, merge, rebase, cherry-pick
reset, restore, checkout, stash, tag, clean
am, apply, bisect, clone, init, mv, rm
branch delete/rename/force-update
worktree remove/move/prune/repair/lock/unlock
commit --amend 및 history rewrite
GitHub MCP를 통한 repository file/ref 직접 변경
```

#### `validate_on_stop.py`

변경 영역별 필수 검증을 확인한다.

```text
server/ 변경        -> validate-server
frontend/ 변경      -> validate-dashboard
server/app.py 변경  -> validate-server + validate-dashboard
navigation/ 변경    -> validate-navigation
raspberry/ 변경     -> validate-raspberry
전체 변경           -> review-change
```

따라서 `setup_pi3b.sh` 또는 `validate_pi3b.sh` 변경도 자동으로 `validate-raspberry` 범위에 포함된다.

### Sub-Agents

- `code_explorer`: entry point, import 관계, 영향 범위, 중복·미사용 코드 조사
- `dashboard_reviewer`: Playwright 기반 실제 웹 대시보드 검증
- `ros_reviewer`: ROS 2, SLAM, AMCL, Nav2, TF 및 topic 검토
- `hardware_reviewer`: Pi 3B, Pico W, UART, Wi-Fi/camera runtime contract, encoder 및 failsafe 검토
- `test_reviewer`: 최종 diff, regression 및 테스트 누락 검토

Sub-Agent reviewer는 read-only로 사용한다. Implementation worker는 지정된 linked worktree와 ownership 범위에서만 수정한다.

### MCP

#### Playwright Browser MCP

다음 검증에 사용한다.

- 로그인 및 session
- UI 렌더링
- JavaScript console 오류
- network request 실패
- modal, sidebar 및 상태 표시
- 카메라, LiDAR, 로봇 연결 및 navigation UI

#### GitHub MCP

다음 읽기 기능을 허용한다.

- 원격 branch와 파일 조회
- 코드 검색
- commit과 diff 조회
- PR, Issue, review 조회
- GitHub Actions 상태와 로그 조회

Issue, PR comment 등 비코드 쓰기는 사용자 승인 후 실행한다.

다음 repository 쓰기 기능은 비활성화한다.

- 원격 파일 생성·수정·삭제
- 원격 commit/ref/branch 생성 또는 변경
- PR merge
- tag 및 release 생성
- workflow 및 repository 설정 변경

Runtime MCP, ROS MCP, DB MCP, Raspberry Pi MCP는 사용하지 않는다.

### 전체 흐름

```text
사용자 요청
-> AGENTS.md 적용
-> implement-feature
-> code_explorer 분석
-> 작업 DAG / ownership 확정
-> linked worktree별 구현
-> 영역별 검증 Skill
-> 분야별 Sub-Agent 검토
-> review-change
-> test_reviewer
-> validate_on_stop
-> commit hash / integration 순서 보고
-> 사용자가 branch integration 수행
```

최종 역할은 다음과 같다.

```text
Skill       -> 작업 절차와 검증
Hook        -> 위험 작업 차단과 검증 강제
Sub-Agent   -> 분야별 독립 검토
Playwright  -> 실제 웹 브라우저 검증
GitHub MCP  -> 원격 GitHub 정보 조회
Worktree    -> Agent별 독립 구현 환경
통합        -> 사용자가 직접 수행
```

---

## 현재 진행 상황

### 구현 완료

- FastAPI 통합 서버와 관제 대시보드
- H.264 카메라 수신 및 MJPEG 출력
- 9개 AI perception pipeline 선택 구조
- WebSocket 기반 수동 주행 명령
- Raspberry Pi와 Pico W 간 UART protocol
- 바퀴 엔코더 telemetry 전송
- `/wheel_ticks -> /odom` 변환
- LiDAR `/scan` WebSocket bridge
- SLAM Toolbox 기반 Mapping
- 저장 지도 저장·조회·이름 변경
- `map_server`와 AMCL 기반 Localization
- 저장 지도 선택과 `/initialpose` 설정
- Nav2 planner/controller/behavior 구성
- 로그인·회원가입·이메일 인증
- MySQL 사용자 계정 연동
- GPU ROS process 제어 UI

### 부분 완료

- Nav2 Twist를 좌우 바퀴 속도로 변환하는 경로
- LiDAR 기반 dry-run 장애물 회피
- AMCL 초기 pose와 저장 지도 load
- wheel odometry 실측 보정
- AI 이상 행동 탐지 pipeline

### 미완성

- Raspberry Pi 3B 실기기 통합 검증
- Nav2 명령의 실제 모터 출력
- 웹 지도 클릭 기반 목표 지점 주행
- waypoint 반복 순찰
- 실제 이동 중 AMCL·TF 안정성 검증
- GPS와 BNO055 통합
- 실제 TTS·스피커 출력
- 이벤트·운행·신고 기록 DB 저장
- Pi 서비스 원격 시작·중지
- 운영용 HTTPS와 배포 자동화

## 시스템 구조

```text
Raspberry Pi 3 Model B (1GB)
├─ OV5647 Camera
├─ RPLIDAR A1M8
├─ Pico W UART
│  ├─ MDD10A motor control
│  └─ Wheel encoder telemetry
└─ WebSocket / HTTP over 2.4GHz Wi-Fi
        │
        ▼
GPU Server
├─ FastAPI
├─ Web Dashboard
├─ AI Perception
├─ ROS 2 Bridge
├─ Wheel Odometry
├─ SLAM Toolbox
├─ AMCL
├─ Nav2
└─ MySQL Authentication
```

주요 디렉터리:

```text
server/       FastAPI, 인증, ROS bridge, odometry
raspberry/    Pi camera, LiDAR, UART, robot command client
navigation/   SLAM, Localization, Nav2, 지도
perception/   객체 탐지, pose, 행동 분석
frontend/     로그인 및 관제 대시보드
data/         DB schema와 runtime 상태
tests/        dry-run 및 navigation API 테스트
docs/         작업 계획과 검증 결과
```

## ROS 2 실행 모드

| 모드 | 주요 구성 | 상태 |
|---|---|---|
| LiDAR only | `/scan` | 구현 |
| Mapping | SLAM Toolbox, `/map` | 구현 |
| Localization | map_server, AMCL | 구현 |
| Localization + Nav2 | planner, controller, BT | dry-run |
| 실제 자율주행 | Nav2 → Pico W → Motor | 차단 |

### Mapping

```bash
source /opt/ros/humble/setup.bash
source ~/dabom_capstone/navigation/ros/install/setup.bash

ros2 launch patrol_navigation mapping.launch.py \
  server_base_url:=http://127.0.0.1:21063 \
  start_lidar:=false \
  start_fake_odom:=false
```

`start_lidar:=false`는 Pi에서 `start_lidar_sender.sh`로 전달된 GPU `/scan`을 사용할 때 적용한다.

### Localization

```bash
ros2 launch patrol_navigation localization.launch.py \
  map:=~/dabom_capstone/navigation/maps/test_map_20260801.yaml \
  server_base_url:=http://127.0.0.1:21063 \
  start_lidar:=false \
  start_fake_odom:=false
```

### Localization + Nav2

```bash
ros2 launch patrol_navigation navigation.launch.py \
  map:=~/dabom_capstone/navigation/maps/test_map_20260801.yaml \
  server_base_url:=http://127.0.0.1:21063 \
  start_lidar:=false \
  start_fake_odom:=false
```

현재 Nav2 출력은 `/cmd_vel_nav_dry_run`으로 전달되며 실제 모터로 전송되지 않는다.

## 주요 API

| Path | 역할 |
|---|---|
| `/login`, `/main` | 로그인과 대시보드 |
| `/stream/h264` | 카메라 H.264 수신 |
| `/video_feed` | MJPEG 영상 |
| `/ws/robot/{robot_id}` | 명령·상태·엔코더 |
| `/ws/sensors/{robot_id}/lidar` | LiDAR 전송 |
| `/api/stream_status` | 카메라·AI·GPU 상태 |
| `/api/robots/{robot_id}/command` | 로봇 명령 |
| `/api/navigation/status` | Navigation 상태 |
| `/api/navigation/map` | 최신 지도 |
| `/api/navigation/pose` | 최신 위치 |
| `/api/navigation/scan` | 최신 scan |
| `/api/navigation/maps` | 저장 지도 목록 |
| `/api/navigation/maps/load` | 지도 load와 initial pose |
| `/api/system-control/status` | ROS 구성 요소 상태 |

## AI Pipeline

| 번호 | 구성 |
|---|---|
| 1 | YOLO11n + ByteTrack + RTMPose + ST-GCN |
| 2 | YOLO11x + ByteTrack + RTMPose + ST-GCN |
| 3 | DINO + Bot-SORT + ViTPose + ST-GCN++ |
| 4 | YOLO11x + Bot-SORT + RTMPose + ST-GCN++ |
| 5 | YOLO11x-Pose + Bot-SORT + ST-GCN++ |
| 6 | YOLO26m + Bot-SORT + RTMPose + ST-GCN++ |
| 7 | YOLO26m + Bot-SORT + RTMPose + PoseConv3D |
| 8 | YOLO26m-Pose + Bot-SORT + ST-GCN++ |
| 9 | YOLO26m-Pose + Bot-SORT + PoseConv3D |

모델 가중치는 `weights/`에 별도로 준비해야 한다. 현재 `dev` 브랜치에는 대용량 weight 파일이 포함되어 있지 않다.

## 데이터베이스

구현된 연결:

- `users`
- `email_verifications`
- bcrypt 비밀번호 저장
- 로그인 session
- 이메일 인증

스키마만 존재하는 테이블:

- `event_log`
- `system_status`
- `action_log`

기존 운영 DB에는 다음 migration을 사용한다.

```text
data/database/20260731_add_users_login_id_and_email_verifications.sql
```

`init_schema.sql`은 신규 DB 생성용이며 기존 DB를 삭제할 수 있으므로 운영 DB에 직접 실행하지 않는다.

## 안전 설정 및 주의점

- Nav2 `auto_drive`는 서버에서 `blocked=true`로 차단된다.
- `server/app.py`는 자율주행 모터 출력을 코드에서 `False`로 고정한다.
- 수동 `move`는 Pi client가 `manual` 모드일 때만 실행한다.
- 실제 odometry 사용 시 `start_fake_odom:=false`로 실행한다.
- Mapping과 Localization을 동시에 실행하지 않는다.
- wheel diameter, wheel track, encoder tick 값은 실장비 재보정이 필요하다.
- `speaker_controller.py`는 현재 stub이다.
- AI weight와 GPU 패키지는 기본 `requirements.txt`에 완전히 포함되지 않는다.
- Pi 3B에서 camera + LiDAR + UART/encoder를 동시에 실행한 상태의 RAM/온도/Wi-Fi 안정성을 반드시 확인한다.
- 실제 모터 출력 활성화 전 emergency stop, UART disconnect, network disconnect를 다시 검증해야 한다.

## 다음 작업

1. Raspberry Pi 3B 초기 설정 및 통합부하 검증
2. Raspberry Pi ↔ Pico W UART 통신 안정화
3. Wheel odometry 직진·회전 보정
4. 실제 이동 중 AMCL과 TF 검증
5. Nav2 launch 및 dry-run 최종 검증
6. 바퀴를 띄운 상태에서 Nav2 모터 출력 시험
7. 단일 `NavigateToPose` 실주행
8. 웹 목표 지점과 waypoint 순찰 구현
9. AI 이벤트와 DB·Telegram 연동
10. Pi 실행 스크립트 systemd 서비스화
