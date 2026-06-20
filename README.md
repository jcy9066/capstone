# Autonomous Patrol Bot

자율주행 AI 방범 로봇 프로젝트다. Raspberry Pi 4 기반 로봇이 카메라 영상과 상태를 서버로 보내고, GPU 서버가 영상 스트리밍, 객체 추적, pose/action 분석, 관제 대시보드, 로봇 명령 중계를 담당하는 구조로 개발 중이다.

현재 저장소의 구현 중심은 `server/app.py`의 FastAPI 통합 서버다. ROS/SLAM, 실제 GPIO 모터 제어, DB 영속화는 프로젝트 목표에 포함되어 있지만 아직 애플리케이션 코드와 완전히 연결되지 않았다.

## 현재 진행 상황

구현되어 있는 부분:

- FastAPI 통합 서버
  - 대시보드 HTML/CSS/JS 제공
  - Raspberry Pi H.264 스트림 수신
  - JPEG 프레임 테스트 수신
  - MJPEG 대시보드 영상 송출
  - 로봇 상태 수신 및 조회
  - WebSocket 기반 로봇 명령 채널
  - 텔레그램 신고 메시지 전송
- 실시간 스트리밍 처리
  - `/stream/h264`에서 ffmpeg로 H.264를 raw frame으로 디코딩
  - preview publish와 모델 추론 worker를 분리
  - latest-frame 방식으로 오래된 추론 후보 frame drop
  - 카메라/로봇 연결 끊김 상태 표시
- AI perception 파이프라인
  - YOLO, DINO, RTMPose, ViTPose, ST-GCN, ST-GCN++, PoseConv3D 조합 실험
  - 1~9번 파이프라인 선택
  - 사람 추적, pose skeleton, 행동 label overlay
  - 휴리스틱 폭력성 보조 판정
- Raspberry Pi 테스트 클라이언트
  - OpenCV 카메라 JPEG 업로드
  - 상태 전송
  - WebSocket 명령 수신
  - move, stop, emergency_stop, speak, mode, camera_config 명령 처리
- 관제 대시보드
  - 실시간 영상 영역
  - 카메라 online/offline 상태
  - CPU, 온도, RAM, 배터리, 네트워크 상태 polling
  - 신고 버튼
  - 자동/수동 모드 UI
  - D-Pad 및 키보드 이동 명령

아직 미완성 또는 미연동인 부분:

- 실제 GPIO 모터 드라이버 제어
- 실제 TTS/스피커 출력
- ROS/SLAM/2D LiDAR 기반 자율주행
- DB 저장 및 조회 API
- 이벤트 로그, 순찰 기록, 갤러리, 스냅샷의 영속화
- 사용자 인증/권한
- 운영 환경별 설치 자동화
- Flask 분리 서버의 정상 실행 정리

## 구조

```text
capstone/
  server/          FastAPI 통합 서버. 현재 실행 기준
  frontend/        대시보드 template/static 및 Flask 분리 시도 코드
  perception/      객체 탐지, 추적, pose/action 분석 파이프라인
  raspberry/       Raspberry Pi 테스트 클라이언트와 컨트롤러 stub
  data/database/   DB 스키마 초안
  docs/            작업 계획서와 결과 보고서
  weights/         모델 config/checkpoint 파일
  output/          테스트 영상 분석 결과물
```

주요 문서:

- `PROJECT.md`: 프로젝트 목표와 시스템 명세
- `AGENTS.md`: 개발/작업 규칙
- `RTK.md`: 작업 기록 규칙
- `data/database/init_schema.sql`: `users`, `event_log`, `system_status`, `action_log` 스키마 초안
- `docs/20260519_[DOC]_모델_대시보드_오버레이_현재구현.md`: 모델 overlay 현재 구현 정리
- `docs/20260507_[RESULT]_카메라_스트리밍_latency_개선.md`: streaming latency 개선 결과
- `docs/20260506_[FULL]_카메라_연결끊김_표시_result.md`: offline 표시 구현 결과

## 실행 준비

기본 서버/대시보드 실행에 필요한 Python 패키지는 프로젝트 루트의 `requirements.txt`에서 관리한다. 현재 파일은 `capstone` conda 환경에 설치된 버전을 기준으로 pinning했다.

```bash
conda activate capstone
cd ~/capstone
pip install -r requirements.txt
```

H.264 stream 수신에는 서버에 `ffmpeg`가 필요하다. 현재 `capstone` conda 환경에는 `ffmpeg`가 conda 패키지로 설치되어 있다.

`requirements.txt`의 범위는 기본 FastAPI 서버와 대시보드 실행이다. 모델 추론까지 실행하려면 GPU/CUDA 환경과 다음 계열 패키지가 추가로 필요하다. 현재 `capstone` 환경에서 확인한 주요 버전은 다음과 같다.

```text
torch==2.1.2+cu121
ultralytics==8.4.32
mmdet==3.2.0
mmpose==1.3.2
mmaction2==1.2.0
mmengine==0.10.7
mmcv==2.1.0
```

가중치와 config는 `weights/`에 있다. 현재 확인된 주요 파일은 `yolo11n.pt`, `yolo11x.pt`, `yolo11x-pose.pt`, `yolo26m.pt`, `yolo26m-pose.pt`, DINO/RTMPose/ViTPose/ST-GCN 계열 config와 checkpoint다.

## 환경 변수

`capstone/.env`를 사용한다. 비밀값은 커밋하지 않는다.

자주 쓰는 값:

```env
SERVER_HOST=0.0.0.0
SERVER_PORT=21063
ROBOT_ID=pi-01

STREAM_WIDTH=640
STREAM_HEIGHT=480
STREAM_FPS=15
STREAM_JPEG_QUALITY=75
PREVIEW_MAX_FPS=15

PIPELINE=1
MODEL_REQUIRED=false
INFERENCE_ENABLED=true
VISUALIZATION_ENABLED=true
STREAM_INFER_EVERY_N=1
INFERENCE_MAX_FPS=15
INFERENCE_DROP_OLDER_THAN_SEC=2.0
INFERENCE_MAX_RESULT_AGE_SEC=3.0

CUDA_DEVICE_INDEX=0
DEVICE=cuda:0
GPU_REQUIRED_FOR_INFERENCE=true

CAMERA_TIMEOUT_SEC=3.0
ROBOT_STATUS_TIMEOUT_SEC=5.0

TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
```

주의:

- `INFERENCE_ENABLED=false`여도 `VISUALIZATION_ENABLED=true`이면 `MODEL_ACTIVE=True`로 계산되어 모델 로딩을 시도할 수 있다.
- 모델을 완전히 끄고 서버/대시보드만 확인하려면 `INFERENCE_ENABLED=false`, `VISUALIZATION_ENABLED=false`, `MODEL_REQUIRED=false`를 함께 둔다.
- 현재 `perception/device.py`는 모델 추론을 CUDA 전제로 검증한다. CPU fallback은 없다.
- `.env`의 모델 관련 값은 서버 실행 중에도 일부 reload된다.

## FastAPI 통합 서버 실행

현재 권장 실행 방식:

```bash
cd ~/capstone
uvicorn server.app:app --host 0.0.0.0 --port 21063
```

또는:

```bash
cd ~/capstone
python server/app.py
```

대시보드:

```text
http://localhost:21063
```

서버 시작 시 `MODEL_ACTIVE=True`이면 선택된 pipeline을 로드한다. GPU나 가중치 문제가 있어도 `MODEL_REQUIRED=false`이면 서버는 계속 뜨고, 오류는 `/api/stream_status`, `/api/latest_result`, `/api/pipelines`에서 확인할 수 있다.

## Raspberry Pi 영상 전송

운영에 가까운 영상 경로는 Python 클라이언트가 아니라 `rpicam-vid`와 `curl`로 H.264를 push하는 방식이다.

모델 없이 preview만 먼저 확인:

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -v -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://<GPU_SERVER_IP>:21063/stream/h264?robot_id=pi-01&infer=false"
```

모델 추론/overlay 포함:

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -v -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://<GPU_SERVER_IP>:21063/stream/h264?robot_id=pi-01&infer=true"
```

무한 실시간 스트림은 `curl --data-binary @-`보다 `-T -`와 chunked upload를 사용한다.

## Raspberry Pi Python 클라이언트

`raspberry/pi_client.py`는 OpenCV/JPEG 테스트와 WebSocket 명령 수신 확인용이다.

```bash
cd ~/capstone
python raspberry/pi_client.py \
  --server-base-url http://<GPU_SERVER_IP>:21063 \
  --robot-id pi-01
```

동작:

- `/frame?robot_id=<id>`로 JPEG frame 전송
- `/status`로 상태 전송
- `/ws/robot/<id>`에 접속해 명령 수신
- 명령 timeout 또는 WebSocket disconnect 시 모터 stop 호출

현재 `raspberry/controllers/motor_controller.py`, `speaker_controller.py`는 실제 GPIO/TTS 연동 전 단계의 stub 성격이다.

## 주요 API

| Method | Path | 역할 |
| --- | --- | --- |
| `GET` | `/` | 관제 대시보드 |
| `POST`, `PUT` | `/stream/h264` | Raspberry Pi H.264 stream 수신 |
| `POST` | `/frame` | JPEG frame 테스트 수신 |
| `GET` | `/video_feed` | 대시보드 MJPEG stream |
| `POST` | `/status`, `/update_status` | 로봇 상태 갱신 |
| `GET` | `/get_status` | 최신 로봇 상태 조회 |
| `GET` | `/api/stream_status` | 카메라/stream/inference/GPU 상태 조회 |
| `GET` | `/api/latest_result` | 최신 AI 탐지 결과 조회 |
| `GET` | `/api/pipelines` | pipeline 목록과 현재 선택 상태 조회 |
| `GET` | `/api/robots/{robot_id}` | 로봇 연결/상태/탐지 결과 조회 |
| `POST` | `/api/robots/{robot_id}/command` | WebSocket 연결된 로봇에 명령 전송 |
| `WS` | `/ws/robot/{robot_id}` | Raspberry Pi 명령 채널 |
| `POST` | `/send_telegram` | 텔레그램 신고 메시지 전송 |

명령 전송 예시:

```bash
curl -X POST http://<GPU_SERVER_IP>:21063/api/robots/pi-01/command \
  -H "Content-Type: application/json" \
  -d '{"type":"move","direction":"forward","speed":0.4}'
```

상태 전송 예시:

```bash
curl -X POST http://<GPU_SERVER_IP>:21063/status \
  -H "Content-Type: application/json" \
  -d '{"robot_id":"pi-01","cpu_usage":12.3,"cpu_temp":48.1,"ram_usage":31.2,"battery":90,"internet":"ok"}'
```

정지 이미지 frame 테스트:

```bash
curl -X POST -F "file=@test.jpg" "http://<GPU_SERVER_IP>:21063/frame?robot_id=pi-01&infer=false"
```

## 모델 파이프라인

`perception/pipeline_factory.py` 기준 선택 가능한 pipeline:

| 번호 | 이름 | 구성 |
| --- | --- | --- |
| `1` | `YOLO11n_ByteTrack_RTMPose_STGCN` | YOLO11n + ByteTrack + RTMPose + ST-GCN |
| `2` | `YOLO11x_ByteTrack_RTMPose_STGCN` | YOLO11x + ByteTrack + RTMPose + ST-GCN |
| `3` | `DINO_BotSORT_ViTPose_STGCNpp` | DINO + Bot-SORT + ViTPose(H) + ST-GCN++ |
| `4` | `YOLO11x_BotSORT_RTMPose_STGCNpp` | YOLO11x + Bot-SORT + RTMPose + ST-GCN++ |
| `5` | `YOLO11xPose_BotSORT_STGCNpp` | YOLO11x-Pose + Bot-SORT + ST-GCN++ |
| `6` | `YOLO26m_BotSORT_RTMPose_STGCNpp` | YOLO26m + Bot-SORT + RTMPose + ST-GCN++ |
| `7` | `YOLO26m_BotSORT_RTMPose_PoseConv3D` | YOLO26m + Bot-SORT + RTMPose + PoseConv3D |
| `8` | `YOLO26mPose_BotSORT_STGCNpp` | YOLO26m-Pose + Bot-SORT + ST-GCN++ |
| `9` | `YOLO26mPose_BotSORT_PoseConv3D` | YOLO26m-Pose + Bot-SORT + PoseConv3D |

현재 detector 설정은 대부분 `classes=[0]`으로 사람만 추적한다. `server/app.py`에는 사람 외 객체를 `WEAPON`으로 처리하는 방어 코드가 남아 있지만, person-only 설정에서는 정상적으로 실행되지 않는다.

대시보드 overlay는 프론트엔드가 직접 그리는 방식이 아니다. 서버가 OpenCV로 skeleton과 label을 frame에 그린 뒤 JPEG/MJPEG로 송출한다. Bounding box 렌더링은 현재 주석 처리되어 있고, skeleton과 label 위주로 표시된다.

## 테스트 영상 분석

영상 파일로 perception pipeline을 단독 검증할 수 있다.

```bash
cd ~/capstone
python perception/main.py --source data/test_videos/scene3_assault.mp4 --pipeline 1 --max-frames 30
```

결과:

```text
output/<pipeline_name>/result_<source_filename>
```

주의:

- `perception/main.py`의 `LocalVideoReader`는 파일 경로 존재 여부를 먼저 확인한다.
- 따라서 `--source rtsp` 같은 값은 현재 코드만으로는 바로 동작하지 않는다.
- RTSP 수신 보조 코드는 `perception/stream/rtsp_receiver.py`에 있지만 `main.py`와 완전히 연결되어 있지는 않다.

## 프론트엔드 상태

현재 실제 대시보드는 FastAPI 서버가 `frontend/templates/index.html`과 `frontend/static/`을 직접 서빙한다.

프론트엔드 JS는 다음 API를 사용한다.

- `/get_status`
- `/api/stream_status`
- `/send_telegram`
- `/api/robots/{ROBOT_ID}/command`

`frontend/app.py`와 `frontend/__init__.py`에는 Flask 기반 분리 서버 코드가 남아 있다. 다만 현재 파일 상태에서는 `frontend/__init__.py`가 `frontend.routes.stream`을 import하지만 실제 `stream.py`가 없고, `frontend/routes/status.py` 안에 stream 관련 blueprint 코드가 들어 있다. 따라서 Flask 분리 서버는 정리 전 상태로 보고, 운영/시연은 `server/app.py` 기준으로 진행한다.

## 데이터베이스 상태

`data/database/init_schema.sql`에는 MySQL/MariaDB용 `dabom` DB 스키마 초안이 있다.

포함 테이블:

- `users`: 관리자 계정
- `event_log`: AI/시스템 이벤트
- `system_status`: 로봇 상태 스냅샷
- `action_log`: 관리자 조치 기록

현재 FastAPI 서버는 DB에 연결하지 않고 전역 메모리 상태를 사용한다. 이벤트, 상태, 조치 로그 저장은 후속 작업이다.

## 현재 설계상 주의점

- 서버 전역 상태는 단일 프로세스 테스트/시연 구조다. 멀티 워커, 인증, DB 저장이 붙으면 상태 저장 구조를 다시 설계해야 한다.
- H.264 수신은 서버에 `ffmpeg` 바이너리가 있어야 한다.
- CUDA/GPU가 없으면 모델 pipeline은 로드되지 않는다.
- `MODEL_REQUIRED=true`이면 모델 로딩 실패가 서버 시작 실패로 이어질 수 있다.
- 텔레그램 기능은 `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`와 외부 네트워크에 의존한다.
- `requirements.txt`는 기본 서버/대시보드 런타임만 관리한다. 모델/GPU 패키지는 설치 경로와 CUDA 조합이 민감하므로 별도 환경 관리 대상으로 둔다.
- `websockets` 패키지는 현재 `capstone` conda 환경에 설치되어 있지 않다. `raspberry/pi_client.py`의 WebSocket 명령 수신까지 쓰려면 환경에 추가 설치가 필요하다.
- `weights/`, `output/`, `received_frames/`, `__pycache__/`는 대용량 또는 생성물로 취급한다.

## 다음 작업 후보

1. Flask 분리 서버 파일 구조 정리 또는 제거
2. 실제 Raspberry Pi GPIO 모터/TTS 연동
3. DB 연결 계층과 이벤트/상태 저장 API 구현
4. AI 탐지 결과를 이벤트 로그, 갤러리, 신고 상태와 연결
5. RTSP receiver를 `perception/main.py` 또는 통합 서버 입력으로 정식 연결
6. ROS/SLAM/2D LiDAR 위치 정보를 대시보드와 DB에 연결
7. 모델/GPU 의존성용 별도 requirements 또는 conda environment 파일 정리
