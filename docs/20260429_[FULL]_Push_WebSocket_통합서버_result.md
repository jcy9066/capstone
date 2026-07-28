# 20260429 [FULL] Push + WebSocket 통합 서버 구현 결과

## 1. 작업 요약

Raspberry Pi 4가 GPU 서버로 영상과 상태를 push하고, 명령은 Raspberry Pi가 먼저 연 WebSocket 연결을 통해 받는 구조를 구현했다.

GPU 서버와 Control Dashboard는 분리하지 않고, 하나의 FastAPI 통합 서버에서 다음 역할을 함께 처리하도록 구성했다.

```text
Frame receiver
Status receiver
Model inference
MJPEG dashboard stream
Robot command WebSocket
Control dashboard
```

## 2. 주요 변경 사항

### 2.1. FastAPI 통합 서버 추가

추가 파일:

```text
server/__init__.py
server/app.py
```

구현한 엔드포인트:

```text
GET  /
POST /frame
POST /status
POST /update_status
GET  /get_status
GET  /video_feed
GET  /api/latest_result
GET  /api/pipelines
GET  /api/robots/{robot_id}
POST /api/robots/{robot_id}/command
WS   /ws/robot/{robot_id}
```

주요 동작:

```text
/frame에서 JPEG 프레임 수신
OpenCV 디코딩
선택된 PIPELINE 모델로 프레임 처리 시도
처리 결과를 latest_result.jpg 및 MJPEG 스트림에 반영
/status에서 Raspberry Pi 상태 수신
/ws/robot/{robot_id}로 Pi 명령 채널 유지
대시보드 명령 API가 연결된 Pi WebSocket으로 명령 전송
```

모델 로드는 서버 startup에서 1회만 시도한다. 모델 로드가 실패해도 기본값에서는 서버가 계속 뜨도록 했다.

```env
MODEL_REQUIRED=false
```

모델 실패 시에도 `/frame`, `/status`, `/video_feed`, WebSocket 명령 채널은 계속 사용할 수 있다.

### 2.2. 모델 파이프라인 분리

추가 파일:

```text
perception/pipeline_factory.py
perception/frame_processor.py
```

변경 파일:

```text
perception/main.py
```

주요 동작:

```text
1~9번 모델 생성 로직을 create_pipeline(choice)로 분리
CLI와 FastAPI 서버가 같은 모델 생성 로직을 사용
단일 프레임 처리 로직을 FrameProcessor로 분리
detector.track -> CascadingTrigger -> action analyzer -> annotation draw 흐름 재사용
```

기존 CLI는 유지하면서 `--pipeline`, `--max-frames` 옵션을 추가했다.

```bash
python perception/main.py --source data/test_videos/scene3_assault.mp4 --pipeline 1 --max-frames 30
```

### 2.3. Raspberry Pi 클라이언트 추가

추가 파일:

```text
raspberry/__init__.py
raspberry/pi_client.py
raspberry/controllers/__init__.py
raspberry/controllers/motor_controller.py
raspberry/controllers/speaker_controller.py
```

주요 동작:

```text
카메라 프레임 캡처
JPEG 인코딩
POST /frame 전송
POST /status 전송
WebSocket /ws/robot/{robot_id} 연결 유지
move / stop / speak / mode / camera_config 명령 처리
명령 timeout 및 WebSocket disconnect 시 stop
```

현재 모터/스피커 제어는 실제 GPIO 제어 전 단계의 stub이다.

```text
motor_controller.py -> print/log 기반 move/stop
speaker_controller.py -> print/log 기반 speak
```

### 2.4. Dashboard 명령 연결

변경 파일:

```text
frontend/static/script.js
```

주요 동작:

```text
자동/수동 모드 변경 시 mode 명령 전송
D-Pad 및 키보드 방향키 조작 시 move 명령 전송
키보드 방향키 해제 시 stop 명령 전송
경고 버튼 클릭 시 speak 명령 전송
```

명령 API:

```text
POST /api/robots/pi-01/command
```

### 2.5. 설정 및 문서 갱신

변경 파일:

```text
.env
README.md
perception/config/settings.py
```

추가 설정:

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

## 3. 실행 방법

### 3.1. GPU 서버

```bash
cd ~/capstone
uvicorn server.app:app --host 0.0.0.0 --port 21063
```

대시보드:

```text
http://localhost:21063
```

### 3.2. Raspberry Pi

```bash
cd ~/capstone
python raspberry/pi_client.py
```

필요 패키지:

```bash
pip install requests websockets opencv-python python-dotenv
```

### 3.3. 정지 이미지 테스트

```bash
curl -X POST -F "file=@test.jpg" http://10.108.90.21:21063/frame
```

### 3.4. 상태 테스트

```bash
curl -X POST http://10.108.90.21:21063/status \
  -H "Content-Type: application/json" \
  -d '{"robot_id":"pi-01","cpu_usage":12.3,"cpu_temp":48.1,"ram_usage":31.2,"battery":90,"internet":"ok"}'
```

### 3.5. 명령 테스트

```bash
curl -X POST http://10.108.90.21:21063/api/robots/pi-01/command \
  -H "Content-Type: application/json" \
  -d '{"type":"move","direction":"forward","speed":0.4}'
```

## 4. 검증 결과

수행한 검증:

```text
Python 문법 검사: 통과
JavaScript 문법 검사: 통과
pipeline_factory import 검사: 통과
```

실행한 명령:

```bash
python -m py_compile capstone/server/app.py capstone/perception/main.py capstone/perception/pipeline_factory.py capstone/perception/frame_processor.py capstone/raspberry/pi_client.py capstone/raspberry/controllers/motor_controller.py capstone/raspberry/controllers/speaker_controller.py
node --check capstone/frontend/static/script.js
```

현재 작업 환경의 기본 Python에는 `cv2`가 없어 `server.app`과 `raspberry/pi_client.py`의 import 실행 검증은 기본 환경에서 실패했다.

```text
ModuleNotFoundError: No module named 'cv2'
```

다만 GPU 서버 conda 환경에는 앞선 테스트에서 `opencv-python`을 설치한 것으로 정리되어 있으므로, 실제 실행은 해당 conda 환경에서 진행해야 한다.

## 5. 남은 작업

```text
1. GPU 서버 conda 환경에서 uvicorn server.app:app 실행
2. Raspberry Pi에서 pi_client.py 실행
3. /frame 연속 전송 FPS 확인
4. /video_feed 대시보드 표시 확인
5. WebSocket 연결 후 대시보드 D-Pad 명령 수신 확인
6. 실제 모터 드라이버 GPIO 코드 연결
7. 실제 스피커/TTS 코드 연결
8. PIPELINE=1부터 모델 로드 및 추론 FPS 확인
```

## 6. 주의사항

- `MODEL_REQUIRED=false` 기본값에서는 모델 로드 실패 시에도 서버가 계속 실행된다.
- 실제 모델 추론을 필수로 강제하려면 `.env`에 `MODEL_REQUIRED=true`를 추가한다.
- Raspberry Pi 클라이언트의 모터/스피커 controller는 현재 stub이다.
- 수동 조종 안전을 위해 Pi 내부 `COMMAND_TIMEOUT_SEC` failsafe가 유지되어야 한다.
- GPU 서버와 Dashboard는 이번 구조에서 분리하지 않는다.

