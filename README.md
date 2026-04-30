# Autonomous Patrol Bot

Raspberry Pi 4 기반 RC카가 카메라와 센서 데이터를 수집하고, GPU 서버가 객체 탐지 및 pose estimation 기반 행동 분석을 수행하며, 웹 관제 대시보드에서 실시간 영상과 로봇 제어를 제공하는 자율주행 AI 방범 로봇 프로젝트다.

현재 구현의 중심 구조는 다음과 같다.

```text
Raspberry Pi 4
  -> POST /stream/h264
  -> POST /status
  -> WebSocket /ws/robot/{robot_id} optional

GPU 통합 서버
  -> FastAPI server.app
  -> H.264 decode
  -> AI inference
  -> MJPEG video feed
  -> Control dashboard
  -> Robot command relay
```

## 현재 구현 상태

구현된 부분:

- FastAPI 통합 서버: H.264 영상 수신, 상태 수신, 모델 추론, MJPEG 스트림, 대시보드, WebSocket 명령 채널
- Raspberry Pi 영상 송신: 운영에서는 `rpicam-vid`와 `curl`로 H.264 stream push
- Raspberry Pi Python 클라이언트: OpenCV/JPEG/WebSocket 테스트용
- 관제 대시보드: 실시간 영상, 상태 바, 신고/경고, 자동/수동 모드, D-Pad 및 키보드 조작
- perception 파이프라인: 1~9번 탐지/pose/action recognition 조합 선택
- 테스트 영상 분석 CLI

진행 중이거나 후속 작업인 부분:

- 실제 GPIO 모터 드라이버 연결
- 실제 TTS/스피커 출력 연결
- ROS/SLAM 기반 자율주행 구현
- ERD 기반 DB 저장
- 이벤트 로그, 순찰 기록, 갤러리의 영속화
- 운영 환경별 패키지/가중치 설치 자동화

## 디렉토리 구조

```text
capstone/
  server/        FastAPI 통합 서버
  raspberry/     Raspberry Pi 송신/명령 수신 클라이언트
  perception/    객체 탐지, pose estimation, 행동 분석 파이프라인
  frontend/      관제 대시보드 HTML/CSS/JS
  navigation/    향후 SLAM 및 자율주행 코드 위치
  docs/          작업 계획서, 결과 보고서, 설계 비교 문서
  data/          테스트 입력 데이터
  weights/       모델 가중치와 설정 파일
  output/        분석 결과 영상
```

주요 문서와 다이어그램:

- `PROJECT.md`: 프로젝트 명세
- `AGENT.md`: 작업 규칙과 개발 안내
- `ERD.png`: 관리자, 상태, 이벤트, 조치 로그 중심 DB 설계 초안
- `Activity_Diagram.png`: Raspberry Pi, GPU/AI 분석, 웹 관제 활동 흐름
- `docs/`: 기능별 계획서와 결과 보고서

## 설치 준비

기본 실행 패키지:

```bash
pip install fastapi "uvicorn[standard]" python-multipart requests websockets opencv-python python-dotenv numpy
```

모델 추론을 실행하려면 별도 GPU/conda 환경과 다음 계열 패키지 및 `weights/` 파일이 필요하다.

```text
torch
ultralytics
mmdet
mmpose
mmaction
mmengine
```

모델 로드가 실패해도 서버/대시보드/명령 채널만 먼저 확인하려면 `.env`에서 `MODEL_REQUIRED=false`로 둔다.

## GPU 통합 서버 실행

프로젝트 루트에서 실행한다.

```bash
cd ~/capstone
uvicorn server.app:app --host 0.0.0.0 --port 21063
```

대시보드 접속:

```text
http://localhost:21063
```

서버 역할:

- `POST /stream/h264`: Raspberry Pi가 push한 H.264 실시간 영상 수신
- `POST /frame`: 정지 이미지/JPEG 프레임 테스트용 수신
- `POST /status`: 로봇 상태 수신
- `GET /video_feed`: 대시보드용 MJPEG 스트림
- `WS /ws/robot/{robot_id}`: Raspberry Pi 명령 채널
- `POST /api/robots/{robot_id}/command`: 대시보드/테스트 명령 입력

## Raspberry Pi 클라이언트 실행

운영 구조에서는 Raspberry Pi에서 Python 클라이언트를 필수로 실행하지 않는다.
Python 클라이언트는 WebSocket 명령과 OpenCV 카메라 테스트용으로 유지한다.

실제 영상 전송은 `rpicam-vid`가 H.264 스트림을 만들고 `curl`이 GPU 서버로 push한다.
실시간 스트림은 끝나지 않는 입력이므로 `--data-binary @-` 대신 `-T -`와 chunked upload를 사용한다.

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -v -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://10.108.90.21:21063/stream/h264?robot_id=pi-01&infer=true"
```

`curl --data-binary @-`는 파일 업로드에는 쓸 수 있지만 `rpicam-vid -t 0` 같은 무한 실시간 스트림에서는 서버에 요청이 늦게 도달하거나 `bytes_received=0`으로 남을 수 있다.

먼저 모델 추론 없이 원본 스트림만 확인하려면 `infer=false`를 붙인다.

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -v -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://10.108.90.21:21063/stream/h264?robot_id=pi-01&infer=false"
```

원본 영상이 대시보드에 보이면 모델 추론을 켠다.

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -v -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://10.108.90.21:21063/stream/h264?robot_id=pi-01&infer=true"
```

테스트용 Python 클라이언트를 사용할 경우 Raspberry Pi 쪽에서 실행한다.

```bash
cd ~/capstone
python raspberry/pi_client.py
```

주요 동작:

- OpenCV로 카메라 프레임 캡처
- JPEG 인코딩 후 `POST /frame` 전송
- 로봇 상태를 `POST /status`로 전송
- 서버의 `WS /ws/robot/{robot_id}`에 연결
- `move`, `stop`, `emergency_stop`, `speak`, `mode`, `camera_config` 명령 처리
- 명령 timeout 또는 WebSocket disconnect 시 모터 정지

현재 `raspberry/controllers/`의 모터/스피커 제어는 실제 GPIO/TTS 연결 전 단계의 stub이다.

## 테스트 영상 분석

로컬 테스트 영상으로 모델 파이프라인을 검증할 수 있다.

```bash
cd ~/capstone
python perception/main.py --source data/test_videos/scene3_assault.mp4 --pipeline 1 --max-frames 30
```

결과 영상은 다음 경로에 저장된다.

```text
output/<pipeline_name>/result_<source_filename>
```

`--pipeline`을 생략하면 실행 중 번호를 입력받는다.

## 모델 파이프라인

`perception/pipeline_factory.py` 기준 선택 가능한 파이프라인은 다음과 같다.

| 번호 | 파이프라인 |
|---|---|
| 1 | YOLO11n + ByteTrack + RTMPose + ST-GCN |
| 2 | YOLO11x + ByteTrack + RTMPose + ST-GCN |
| 3 | DINO + Bot-SORT + ViTPose(H) + ST-GCN++ |
| 4 | YOLO11x + Bot-SORT + RTMPose + ST-GCN++ |
| 5 | YOLO11x-Pose + Bot-SORT + ST-GCN++ |
| 6 | YOLO26m + Bot-SORT + RTMPose + ST-GCN++ |
| 7 | YOLO26m + Bot-SORT + RTMPose + PoseConv3D |
| 8 | YOLO26m-Pose + Bot-SORT + ST-GCN++ |
| 9 | YOLO26m-Pose + Bot-SORT + PoseConv3D |

대상 클래스는 주로 사람과 위험 물체이며, `FrameProcessor`는 다음 흐름으로 단일 프레임을 처리한다.

```text
detector.track(frame)
-> CascadingTrigger
-> action_analyzer.process(frame, obj)
-> skeleton / bounding box draw
-> detections / danger 반환
```

주의:

- 여러 모델 파일은 기본 장치로 `cuda:0`을 사용한다.
- Raspberry Pi에서 직접 전체 모델 파이프라인을 돌리는 구조가 아니라, GPU 서버에서 추론하는 구성을 우선한다.
- 가중치 파일은 `weights/`에 있어야 한다.

## API 테스트

H.264 실시간 영상 전송:

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -v -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://<GPU_SERVER_IP>:21063/stream/h264?robot_id=pi-01"
```

정지 이미지 전송:

```bash
curl -X POST -F "file=@test.jpg" http://<GPU_SERVER_IP>:21063/frame
```

상태 전송:

```bash
curl -X POST http://<GPU_SERVER_IP>:21063/status \
  -H "Content-Type: application/json" \
  -d '{"robot_id":"pi-01","cpu_usage":12.3,"cpu_temp":48.1,"ram_usage":31.2,"battery":90,"internet":"ok"}'
```

명령 전송:

```bash
curl -X POST http://<GPU_SERVER_IP>:21063/api/robots/pi-01/command \
  -H "Content-Type: application/json" \
  -d '{"type":"move","direction":"forward","speed":0.4}'
```

최신 상태 조회:

```bash
curl http://<GPU_SERVER_IP>:21063/get_status
```

최신 탐지 결과 조회:

```bash
curl http://<GPU_SERVER_IP>:21063/api/latest_result
```

파이프라인 목록 조회:

```bash
curl http://<GPU_SERVER_IP>:21063/api/pipelines
```

## 대시보드 기능

대시보드는 `frontend/`의 템플릿과 정적 파일을 FastAPI 서버가 재사용한다.

주요 기능:

- 실시간 카메라 스트림 표시
- CPU, 온도, RAM, 배터리, 네트워크 상태 표시
- 텔레그램 신고 버튼
- 경고 방송 명령 전송
- 자동/수동 순찰 모드 전환
- D-Pad 버튼과 키보드 방향키/WASD를 통한 수동 조종
- 키 해제 시 stop 명령 전송
- 다크 모드
- 북마크, 갤러리, 상태/순찰 로그 UI

아직 실제 DB 저장과 일부 로그/갤러리 데이터는 미연동 상태다.

## RTSP 관련 메모

`perception/stream/rtsp_receiver.py`에는 RTSP 수신기가 있다. 다만 현재 `perception/main.py`의 기본 입력 흐름은 로컬 파일 중심이며, `--source rtsp` 실시간 입력 확장은 별도 계획 문서에서 다룬다.

관련 문서:

- `docs/20260429_[FULL]_실시간_RTSP_모델선택_탐지_plan.md`

## 개발 참고 문서

- `docs/20260429_[FULL]_Push_WebSocket_통합서버_plan.md`
- `docs/20260429_[FULL]_Push_WebSocket_통합서버_result.md`
- `docs/20260429_[FULL]_명령통신방식_비교.md`
- `docs/20260429_[FULL]_구조_분리_plan.md`
- `docs/20260429_[FULL]_구조_분리_result.md`

## 알려진 제약

- `weights/`, `data/`, `output/`은 대용량 파일이 많으므로 git 관리와 배포 방식을 별도로 정리해야 한다.
- `.env`는 비밀값을 포함할 수 있으므로 커밋하지 않는다.
- `frontend/app.py`는 기존 Flask 서버로 남아 있지만, 현재 권장 실행 경로는 `server/app.py` FastAPI 통합 서버다.
- 모터/스피커는 stub이며 실제 하드웨어 제어 코드는 후속 연결이 필요하다.
- SLAM/ROS 자율주행 코드는 `navigation/`에 들어갈 예정이다.
- ERD 기반 데이터베이스 구현은 아직 문서 설계 단계다.
