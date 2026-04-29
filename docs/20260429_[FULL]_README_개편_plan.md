# 20260429 [FULL] README 개편 계획

## 1. 작업 목표

`~/capstone` 내부 파일을 검토한 내용을 바탕으로 루트 `README.md`를 프로젝트 온보딩 문서로 개편한다.

사용자 요청에는 `READMD.md`라고 적혀 있으나, 저장소에 존재하는 대상 문서는 `README.md`이므로 실제 수정 대상은 `README.md`로 본다.

## 2. 검토 범위

### 2.1. 직접 읽은 텍스트 파일

- `README.md`
- `PROJECT.md`
- `AGENT.md`
- `.gitignore`
- `.env` 키 목록만 확인
- `server/app.py`
- `raspberry/pi_client.py`
- `raspberry/controllers/motor_controller.py`
- `raspberry/controllers/speaker_controller.py`
- `frontend/app.py`
- `frontend/templates/index.html`
- `frontend/static/script.js`
- `perception/main.py`
- `perception/frame_processor.py`
- `perception/pipeline_factory.py`
- `perception/core/trigger.py`
- `perception/stream/rtsp_receiver.py`
- `perception/config/settings.py`
- `perception/config/config.yaml`
- `perception/models/*.py`
- `docs/20260429_[FULL]_실시간_RTSP_모델선택_탐지_plan.md`
- `docs/20260429_[FULL]_Push_WebSocket_통합서버_plan.md`
- `docs/20260429_[FULL]_Push_WebSocket_통합서버_result.md`
- `docs/20260429_[FULL]_명령통신방식_비교.md`

### 2.2. 내용 대신 위치/역할만 확인할 파일

- `ERD.png`
- `Activity_Diagram.png`
- `weights/` 내 모델 가중치와 설정 파일
- `data/test_videos/` 내 테스트 영상/오디오
- `output/` 내 분석 결과 영상
- `__pycache__/` 생성물

## 3. 현재 프로젝트 구조 요약

현재 저장소는 다음 실행 축을 갖는다.

- `server/`: FastAPI 통합 서버. 프레임 수신, 상태 수신, 모델 추론, MJPEG 스트림, 대시보드, WebSocket 명령 채널을 담당한다.
- `raspberry/`: Raspberry Pi 클라이언트. 카메라 프레임과 상태를 서버로 push하고, WebSocket 명령을 받아 모터/스피커 stub을 실행한다.
- `perception/`: 모델 파이프라인, 프레임 처리, 객체 탐지, pose estimation, 행동 인식 로직을 담당한다.
- `frontend/`: 대시보드 HTML/CSS/JS. 현재 FastAPI 서버가 이 정적 파일과 템플릿을 재사용한다.
- `navigation/`: 향후 SLAM/자율주행 코드를 둘 자리다.
- `docs/`: 작업 계획서, 결과 보고서, 통신 방식 비교 문서가 있다.
- `data/`, `weights/`, `output/`: 테스트 데이터, 모델 가중치, 분석 산출물이다.

## 4. README 개편 방향

현재 `README.md`는 실행 명령 중심으로 짧게 정리되어 있다. 이번 개편에서는 처음 보는 사람이 프로젝트 목적, 구조, 실행 순서, 환경 변수, API, 모델 파이프라인, 남은 작업을 빠르게 파악하도록 확장한다.

## 5. 제안 목차

1. 프로젝트 소개
   - 자율주행 AI 방범 로봇 목적
   - Raspberry Pi, GPU 서버, 웹 관제, AI 분석의 관계

2. 현재 구현 상태
   - 구현됨: FastAPI 통합 서버, Pi push 클라이언트, WebSocket 명령 채널, 대시보드 재사용, 1~9번 모델 파이프라인 선택, 테스트 영상 분석
   - 진행 중: 실제 GPIO 모터 제어, 실제 TTS/스피커, SLAM/ROS, DB 저장, 이벤트 로그 영속화

3. 디렉토리 구조
   - `server/`
   - `raspberry/`
   - `perception/`
   - `frontend/`
   - `navigation/`
   - `docs/`
   - `data/`, `weights/`, `output/`

4. 아키텍처
   - Raspberry Pi -> GPU Server: `POST /frame`, `POST /status`
   - Raspberry Pi -> GPU Server: WebSocket 연결 시작
   - GPU Server -> Raspberry Pi: 열린 WebSocket으로 명령 전달
   - GPU Server -> Dashboard: `/video_feed`, `/get_status`, `/api/latest_result`
   - `ERD.png`, `Activity_Diagram.png` 참고 안내

5. 환경 변수
   - 텔레그램: `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`
   - RTSP: `RASPBERRY_PI_IP`, `RTSP_PORT`, `RTSP_PATH`, `RTSP_URL`
   - 서버: `SERVER_HOST`, `SERVER_PORT`, `SERVER_BASE_URL`
   - 로봇/명령: `ROBOT_ID`, `COMMAND_TIMEOUT_SEC`, `WS_RECONNECT_DELAY_SEC`
   - 영상 전송: `FRAME_FPS`, `JPEG_QUALITY`, `SAVE_RECEIVED_FRAMES`
   - 모델: `PIPELINE`, `MODEL_REQUIRED`
   - 비밀값은 README에 실제 값을 쓰지 않는다.

6. 설치 및 실행 준비
   - 권장 작업 디렉토리: `cd ~/capstone`
   - Python 패키지 안내
   - OpenCV, FastAPI/Uvicorn, requests, websockets, python-dotenv
   - 모델 실행 환경은 GPU/conda 환경과 가중치 파일이 필요하다는 점 명시

7. GPU 통합 서버 실행
   - `uvicorn server.app:app --host 0.0.0.0 --port 21063`
   - 대시보드 접속: `http://localhost:21063`
   - `MODEL_REQUIRED=false`일 때 모델 로드 실패에도 서버가 계속 뜰 수 있음을 명시

8. Raspberry Pi 클라이언트 실행
   - `python raspberry/pi_client.py`
   - 프레임 전송, 상태 전송, WebSocket 명령 수신, failsafe 설명
   - 현재 모터/스피커는 stub이며 실제 GPIO/TTS 연결은 후속 작업임을 명시

9. 테스트 영상 분석 실행
   - `python perception/main.py --source data/test_videos/scene3_assault.mp4 --pipeline 1 --max-frames 30`
   - 1~9번 파이프라인 표 추가
   - 결과 파일 저장 위치: `output/<pipeline>/result_<source>`

10. API 테스트
    - `POST /frame`
    - `POST /status`
    - `GET /get_status`
    - `GET /api/latest_result`
    - `GET /api/pipelines`
    - `GET /api/robots/{robot_id}`
    - `POST /api/robots/{robot_id}/command`
    - `WS /ws/robot/{robot_id}`

11. 대시보드 기능
    - 실시간 영상
    - 상태 바
    - 신고/경고
    - 자동/수동 모드
    - D-Pad 및 키보드 방향키/WASD 명령
    - 다크 모드, 북마크/갤러리/로그 UI
    - 아직 실제 DB 저장과 일부 로그는 미연동임을 명시

12. 모델 파이프라인
    - `perception/pipeline_factory.py` 기준 1~9번 조합 표
    - YOLO/DINO, ByteTrack/Bot-SORT, RTMPose/ViTPose/YOLO-Pose, ST-GCN/ST-GCN++/PoseConv3D
    - 가중치 위치는 `weights/`
    - CUDA 기본값과 Raspberry Pi 직접 실행 한계를 주의사항으로 명시

13. 문서와 다이어그램
    - `PROJECT.md`
    - `AGENT.md`
    - `ERD.png`
    - `Activity_Diagram.png`
    - `docs/` 내 작업 계획/결과 문서

14. 알려진 제약 및 다음 작업
    - `perception/main.py --source rtsp`는 기존 계획상 확장 대상이며 현재 구현 상태와 README 내용이 충돌하지 않게 표현한다.
    - 실제 GPIO 모터 제어 연결
    - 실제 TTS/스피커 연결
    - ROS/SLAM 구현
    - ERD 기반 DB 저장
    - 이벤트 전후 영상 저장 정책 고도화
    - 운영 환경 의존 패키지 정리

## 6. 수정 시 주의사항

- `.env`의 실제 값은 README에 노출하지 않는다.
- `weights/`, `data/test_videos/`, `output/`의 대용량 파일 목록은 모두 나열하지 않고 역할만 설명한다.
- `frontend/app.py`는 기존 Flask 서버로 남아 있지만, 현재 권장 실행 경로는 `server/app.py` FastAPI 통합 서버로 안내한다.
- `raspberry/controllers/*`는 실제 하드웨어 제어가 아닌 stub 상태임을 명확히 쓴다.
- 모델 로드 실패 시에도 `MODEL_REQUIRED=false`에서는 서버가 계속 동작할 수 있다는 점을 적어 초기 실행자의 혼란을 줄인다.
- README는 실행 중심 문서로 유지하고, 상세 설계는 `PROJECT.md`, `ERD.png`, `Activity_Diagram.png`, `docs/`로 연결한다.

## 7. 검증 계획

README 수정 후 다음을 확인한다.

1. 명령어 경로가 현재 파일 위치와 일치하는지 확인한다.
2. README에 비밀값이 포함되지 않았는지 확인한다.
3. FastAPI 서버 실행 명령, Pi 클라이언트 실행 명령, 테스트 영상 분석 명령이 서로 혼동되지 않게 구분되어 있는지 확인한다.
4. API endpoint 목록이 `server/app.py`와 일치하는지 확인한다.
5. 모델 파이프라인 번호가 `perception/pipeline_factory.py`와 일치하는지 확인한다.
6. 실제 코드 수정은 README 본문에 한정하고, 완료 후 결과 보고서를 `docs/20260429_[FULL]_README_개편_result.md`로 작성한다.

