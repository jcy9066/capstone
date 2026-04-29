# 20260429 [FULL] Push + WebSocket 통합 서버 구현 계획

## 1. 작업 목표

Raspberry Pi 4가 카메라 프레임과 상태 정보를 GPU 서버로 전송하고, GPU 서버가 객체 탐지 및 Pose Estimation 모델을 실행하며, 같은 서버에서 Control Dashboard와 로봇 명령 채널을 함께 관리하는 구조를 구현한다.

이번 작업에서는 GPU 서버와 Control Dashboard를 분리하지 않는다.

```text
GPU Server = Frame receiver + Status receiver + Model inference + Command WebSocket + Control Dashboard
```

## 2. 최종 아키텍처

```text
Raspberry Pi 4
 ├─ Camera capture
 ├─ POST /frame
 ├─ POST /status
 ├─ WebSocket client
 └─ Motor/Speaker controller

GPU Server
 ├─ FastAPI /frame
 ├─ FastAPI /status
 ├─ WebSocket /ws/robot/{robot_id}
 ├─ Pose Estimation / Object Detection model
 └─ Control dashboard
```

## 3. 통신 흐름

### 3.1. 영상

```text
Raspberry Pi -> GPU Server
POST /frame
multipart/form-data 또는 image/jpeg
```

처리 순서:

```text
1. Raspberry Pi가 카메라 프레임 캡처
2. JPEG 인코딩
3. GPU 서버 /frame으로 POST
4. GPU 서버가 OpenCV로 디코딩
5. 선택된 1~9번 모델 파이프라인으로 추론
6. 분석 결과 프레임을 latest frame으로 저장
7. Dashboard /video_feed에서 MJPEG로 표시
```

### 3.2. 상태

```text
Raspberry Pi -> GPU Server
POST /status
application/json
```

예상 payload:

```json
{
  "robot_id": "pi-01",
  "cpu_usage": 23.4,
  "cpu_temp": 51.2,
  "ram_usage": 45.1,
  "battery": 87,
  "internet": "ok",
  "mode": "manual"
}
```

대시보드는 기존 `/get_status` 호환 엔드포인트를 통해 최신 상태를 조회한다.

### 3.3. 명령

```text
Raspberry Pi -> GPU Server
WebSocket /ws/robot/{robot_id}

GPU Server -> Raspberry Pi
열린 WebSocket 연결로 명령 전송
```

명령 예시:

```json
{
  "type": "move",
  "direction": "forward",
  "speed": 0.4,
  "issued_at": 1777440000.0
}
```

추가 명령 타입:

```text
move
stop
speak
camera_config
mode
emergency_stop
```

## 4. 안전 설계

Raspberry Pi 내부에 failsafe를 둔다. 서버나 네트워크가 불안정해도 로봇이 계속 움직이지 않게 하는 것이 핵심이다.

```text
일정 시간 명령 없음 -> 정지
WebSocket 끊김 -> 정지
서버 응답 없음 -> 정지
긴급 정지 명령 수신 -> 즉시 정지
프레임 전송 실패 지속 -> 상태 경고
```

권장 기본값:

```env
COMMAND_TIMEOUT_SEC=0.5
WS_RECONNECT_DELAY_SEC=1.0
FRAME_FPS=10
JPEG_QUALITY=70
```

## 5. 구현 전략

기존 Flask 대시보드가 이미 있으므로, 새 기능은 FastAPI 통합 서버로 작성하고 기존 템플릿/정적 파일을 재사용한다.

이유:

```text
FastAPI는 /frame 수신, /status 수신, WebSocket을 한 서버에서 처리하기 쉽다.
기존 dashboard HTML/CSS/JS는 Jinja2Templates와 StaticFiles로 재사용할 수 있다.
GPU 서버와 Control Dashboard를 같은 프로세스 또는 같은 앱 축에서 운영할 수 있다.
```

기존 `frontend/app.py`는 당장 삭제하지 않고, 호환/백업용으로 유지한다. 새 실행 진입점은 FastAPI 서버로 둔다.

## 6. 예상 추가/수정 파일

### 6.1. 새 서버 파일

```text
server/app.py
```

역할:

```text
FastAPI 앱 생성
대시보드 라우트 /
정적 파일 mount
/frame 수신
/status 수신
/get_status 호환
/video_feed MJPEG 송출
/ws/robot/{robot_id} 로봇 WebSocket
/api/robots/{robot_id}/command 대시보드 명령 입력
```

### 6.2. 모델 파이프라인 분리

```text
perception/pipeline_factory.py
perception/frame_processor.py
```

역할:

```text
pipeline_factory.py
- 1~9번 파이프라인 생성 로직을 함수로 분리
- 기존 perception/main.py와 FastAPI 서버가 같은 로직 사용

frame_processor.py
- 단일 frame 입력
- detector.track(frame)
- CascadingTrigger
- action analyzer
- bounding box/skeleton draw
- 이벤트/위험 여부 결과 반환
```

### 6.3. Raspberry Pi 송신 클라이언트

```text
raspberry/pi_client.py
```

역할:

```text
카메라 프레임 캡처
JPEG 인코딩
POST /frame
시스템 상태 POST /status
WebSocket 연결 유지
명령 수신
failsafe 정지 처리
```

실제 모터/스피커 제어는 하드웨어 연결 상태에 따라 stub부터 둔다.

```text
raspberry/controllers/motor_controller.py
raspberry/controllers/speaker_controller.py
```

초기 구현에서는 print/log 기반으로 명령 수신을 검증하고, 실제 GPIO 제어는 후속 연결한다.

### 6.4. 설정 파일

```text
perception/config/settings.py
.env
README.md
```

추가할 환경 변수:

```env
SERVER_HOST=0.0.0.0
SERVER_PORT=21063
SERVER_BASE_URL=http://10.108.90.21:21063
ROBOT_ID=pi-01
PIPELINE=1
FRAME_FPS=10
JPEG_QUALITY=70
COMMAND_TIMEOUT_SEC=0.5
WS_RECONNECT_DELAY_SEC=1.0
SAVE_RECEIVED_FRAMES=true
```

## 7. API 설계

### 7.1. `POST /frame`

입력:

```text
multipart/form-data: file=<jpeg>
또는 raw image/jpeg body
```

응답:

```json
{
  "ok": true,
  "robot_id": "pi-01",
  "detections": [],
  "danger": false
}
```

### 7.2. `POST /status`

입력:

```json
{
  "robot_id": "pi-01",
  "cpu_usage": 23.4,
  "cpu_temp": 51.2,
  "ram_usage": 45.1,
  "battery": 87,
  "internet": "ok"
}
```

응답:

```json
{"ok": true}
```

### 7.3. `GET /get_status`

기존 frontend JS 호환을 위해 유지한다.

응답:

```json
{
  "cpu_usage": "23.4",
  "cpu_temp": "51.2",
  "battery": "87",
  "ram_usage": "45.1",
  "internet": "ok"
}
```

### 7.4. `GET /video_feed`

대시보드 `<img>` 태그에서 볼 수 있도록 MJPEG 스트림을 반환한다.

```text
multipart/x-mixed-replace; boundary=frame
```

### 7.5. `WebSocket /ws/robot/{robot_id}`

Raspberry Pi가 연결한다.

서버 -> Pi 메시지:

```json
{"type":"move","direction":"left","speed":0.3}
```

Pi -> 서버 메시지:

```json
{"type":"ack","command_id":"...", "ok":true}
```

### 7.6. `POST /api/robots/{robot_id}/command`

대시보드 또는 테스트 도구가 로봇 명령을 넣는 엔드포인트다.

입력:

```json
{"type":"move","direction":"forward","speed":0.4}
```

응답:

```json
{"ok": true, "delivered": true}
```

WebSocket이 연결되어 있지 않으면:

```json
{"ok": false, "delivered": false, "error": "robot not connected"}
```

## 8. 기존 코드와의 관계

### 8.1. `frontend/app.py`

당장 제거하지 않는다.

새 FastAPI 서버가 안정화되기 전까지 기존 Flask 서버는 비교/백업용으로 유지한다.

### 8.2. `frontend/templates/index.html`

가능하면 그대로 재사용한다.

필요 시 명령 버튼이 `/api/robots/pi-01/command`를 호출하도록 `frontend/static/script.js`를 수정한다.

### 8.3. `perception/main.py`

기존 테스트 영상 분석 CLI는 유지한다.

다만 1~9번 모델 생성 로직은 `perception/pipeline_factory.py`로 분리해 CLI와 서버가 같은 코드를 쓰도록 개선한다.

## 9. 구현 순서

1. 계획 문서 작성
2. `pipeline_factory.py`로 1~9번 모델 생성 로직 분리
3. `frame_processor.py`로 단일 프레임 처리 로직 분리
4. FastAPI 통합 서버 `server/app.py` 추가
5. `/frame`, `/status`, `/get_status`, `/video_feed` 구현
6. `/ws/robot/{robot_id}`와 `/api/robots/{robot_id}/command` 구현
7. Raspberry Pi 클라이언트 `raspberry/pi_client.py` 추가
8. 모터/스피커 controller stub 추가
9. README 실행 예시 갱신
10. 결과 보고서 작성

## 10. 검증 계획

### 10.1. 서버 기동

```bash
uvicorn server.app:app --host 0.0.0.0 --port 21063
```

확인:

```text
http://localhost:21063
```

### 10.2. 정지 이미지 POST

```bash
curl -X POST -F "file=@test.jpg" http://10.108.90.21:21063/frame
```

확인:

```text
응답 {"ok": true}
대시보드 /video_feed에 최신 프레임 표시
```

### 10.3. 상태 POST

```bash
curl -X POST http://10.108.90.21:21063/status \
  -H "Content-Type: application/json" \
  -d '{"robot_id":"pi-01","cpu_usage":12.3,"cpu_temp":48.1,"ram_usage":31.2,"battery":90,"internet":"ok"}'
```

확인:

```text
/get_status 응답이 갱신됨
대시보드 상태 표시가 갱신됨
```

### 10.4. WebSocket 명령

확인 항목:

```text
Raspberry Pi client가 /ws/robot/pi-01 연결
대시보드 또는 curl로 /api/robots/pi-01/command 호출
Pi client가 명령 수신
명령 ACK가 서버에 기록
연결 종료 시 Pi client failsafe stop 실행
```

### 10.5. 모델 추론

처음에는 `PIPELINE=1` 경량 모델로 검증한다.

확인 항목:

```text
서버 시작 시 모델 1회 로드
/frame 요청마다 모델 재로드 없음
수신 FPS와 추론 FPS 로그 출력
위험 이벤트 발생 시 latest_result frame에 box/label 표시
```

## 11. 주의사항

- 모델 로드는 서버 시작 시 1회만 수행한다.
- `/frame` 요청마다 모델을 새로 만들면 실시간 처리가 불가능하다.
- 라즈베리파이 클라이언트는 서버 장애 시 모터를 정지해야 한다.
- 대시보드와 GPU 서버는 이번 단계에서 분리하지 않는다.
- 기존 Flask 서버는 백업으로 유지하되, 새 실행 경로는 FastAPI 서버로 둔다.
- `.env`의 토큰, IP, 포트 같은 환경 설정은 커밋하지 않는다.
- `weights/`, `output/`, `data/test_videos/` 대용량 파일은 수정하지 않는다.

