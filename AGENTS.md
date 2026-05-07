@RTK.md

# AGENT.md

이 문서는 `~/capstone` 프로젝트를 이어서 작업하는 에이전트/개발자를 위한 작업 안내서입니다. 프로젝트 핵심 명세는 `PROJECT.md`를 기준으로 삼고, 현재 코드와 모델 관련 구현은 실험 및 진행 중 상태로 취급합니다.

## 프로젝트 핵심

- 프로젝트명: 자율주행 AI 방범 로봇
- 목표: Raspberry Pi 4 기반 모바일 로봇이 특정 구역을 자율 순찰하고, 카메라/비전 AI로 침입, 흉기, 폭력 또는 이상 행동을 탐지해 관제 대시보드와 알림으로 전달하는 시스템
- 주요 하드웨어 가정: Raspberry Pi 4, RC카 프레임, 2D LiDAR, 비전 카메라
- 주요 소프트웨어 가정: ROS, Python, PyTorch 계열 모델, Flask 웹 대시보드
- 계획된 핵심 기능:
  - LiDAR 기반 SLAM 및 장애물 회피
  - ROS 내비게이션 스택 기반 순찰
  - YOLO 계열 객체 탐지 및 추적
  - Pose Estimation 기반 이상 행동 분류
  - 실시간 웹 관제, 영상 스트리밍, 위험 알림

## 현재 저장소 상태 요약

현재 저장소에는 관제 웹 서버, 로컬 카메라 업로드 테스트, 비디오 파일 기반 행동 분석 파이프라인, 텔레그램 알림, RTSP 수신기, 여러 모델 조합 실험 코드가 있다. ROS/SLAM/실제 모터 제어와 완전한 하드웨어 연동은 명세상 목표이며, 저장소 코드에서는 아직 완성된 형태로 확인되지 않는다.

대시보드와 모델 파이프라인은 서로 별도 축으로 개발되어 있다. `frontend/app.py`는 Flask 관제 서버와 MJPEG 스트리밍을 담당하고, `perception/main.py`는 테스트 영상 또는 RTSP 소스를 입력받아 탐지/추적/행동 인식 결과 영상을 저장하는 실험 파이프라인이다. 향후 SLAM 및 자율주행 코드는 `navigation/`에 배치한다.

## 주요 파일과 역할

- `PROJECT.md`: 프로젝트 명세의 기준 문서. 목표, 하드웨어, 소프트웨어 스택, 핵심 기능, 데이터 흐름을 설명한다.
- `ERD.png`: 관리자, 상태, 이벤트, 조치 로그 중심의 데이터베이스 설계 초안이다.
- `Activity_Diagram.png`: Raspberry Pi, GPU/AI 분석, 웹 관제 영역의 시스템 활동 흐름도다.
- `README.md`: 간단 실행 예시. 테스트 영상 모드와 RTSP 모드 명령이 적혀 있다.
- `frontend/app.py`: Flask 기반 관제 서버. `/`, `/video_feed`, `/upload`, `/get_status`, `/update_status`, `/send_telegram` 라우트를 제공한다.
- `frontend/templates/index.html`, `frontend/static/script.js`, `frontend/static/style.css`: 관제 대시보드 UI. 실시간 영상, 상태 바, 알림 패널, 북마크/갤러리 모달, 자동/수동 순찰 토글, D-Pad, 다크 모드가 구현되어 있다.
- `perception/local_cam.py`: 노트북 기본 웹캠을 읽어 `frontend/app.py`의 `/upload`로 JPEG 프레임을 전송하는 로컬 테스트 클라이언트다.
- `perception/main.py`: 행동 분석 파이프라인 선택 CLI. 9개 모델 조합 중 하나를 선택해 입력 영상을 분석하고 `output/<pipeline>/result_<source>`로 저장한다.
- `perception/core/trigger.py`: CascadingTrigger. 객체 추적 결과에서 흉기, 거리, 속도, 박스 비율, 사람 간 밀집도 조건으로 의심 상태를 선별한다.
- `perception/stream/rtsp_receiver.py`: OpenCV/FFmpeg 기반 RTSP 프레임 수신기. 작은 큐를 사용해 오래된 프레임을 버리고 최신 프레임 위주로 처리한다.
- `perception/utils/telegram_notifier.py`: 텔레그램 메시지/사진 알림을 백그라운드 스레드로 전송한다.
- `perception/config/settings.py`: `.env`에서 텔레그램, RTSP, 임계값 관련 환경 변수를 로드한다.
- `perception/config/config.yaml`: RTSP URL, 모델 가중치 경로, 임계값, 알림 웹훅 설정 예시를 담고 있다.
- `perception/models/`: 탐지, 추적, 자세 추정, 행동 분류 실험 코드가 있다.
- `navigation/`: 향후 SLAM, ROS 내비게이션, 경로 계획, 모터 제어 연동 코드를 둘 디렉토리다.
- `weights/`: YOLO, DINO, RTMPose, ViTPose, ST-GCN, ST-GCN++, PoseConv3D 계열 가중치/설정 파일이 있다. 대용량 바이너리이므로 문서나 커밋에 내용을 복사하지 않는다.
- `data/test_videos/`: 테스트용 영상/오디오 파일이 있다.
- `output/`: 분석 결과 영상 산출물이다.

## 모델 및 분석 파이프라인

`perception/main.py`는 다음 조합을 선택할 수 있도록 되어 있다.

1. YOLO11n + ByteTrack + RTMPose + ST-GCN
2. YOLO11x + ByteTrack + RTMPose + ST-GCN
3. DINO + Bot-SORT + ViTPose(H) + ST-GCN++
4. YOLO11x + Bot-SORT + RTMPose + ST-GCN++
5. YOLO11x-Pose + Bot-SORT + ST-GCN++
6. YOLO26m + Bot-SORT + RTMPose + ST-GCN++
7. YOLO26m + Bot-SORT + RTMPose + PoseConv3D
8. YOLO26m-Pose + Bot-SORT + ST-GCN++
9. YOLO26m-Pose + Bot-SORT + PoseConv3D

탐지 대상 클래스는 주로 사람과 일부 흉기/위험 물체로 제한되어 있다. YOLO 계열 구현은 Ultralytics `model.track()`을 사용하고, DINO 구현은 MMDetection과 Ultralytics Bot-SORT를 조합한다. 행동 인식 계열 구현은 MMPose/MMACTION 기반으로 자세 시퀀스를 만들고, 프레임 수가 부족할 때 마지막 자세를 반복해 동적 패딩한 뒤 매 프레임 분류를 시도한다.

주의: 모델 관련 코드는 진행 중이며, 성능/정확도/실시간성/하드웨어 적합성이 확정된 것으로 보지 않는다. 특히 CUDA 장치(`cuda:0`)를 기본값으로 쓰는 코드가 많으므로 Raspberry Pi 또는 CPU 환경에서 그대로 실행되지 않을 수 있다.

## 웹 대시보드 상태

`frontend/app.py`는 서버가 받은 최신 프레임을 `current_frame`에 저장하고 `/video_feed`에서 MJPEG 형태로 스트리밍한다. `/update_status`는 외부 장치가 보내는 CPU, 온도, 배터리, RAM, 네트워크 상태를 받아 `robot_status`에 반영하고, 프론트엔드는 `/get_status`를 1초마다 폴링한다.

프론트엔드는 다음 기능을 포함한다.

- 실시간 카메라 영역 및 전체화면
- 카메라 상단 날짜/시간 오버레이
- 미니맵 자리 표시 및 확대 토글
- 실시간 경고/알림 패널
- 기기 상태 로그, 순찰 기록, 북마크, 갤러리 모달
- 현재 화면 북마크 기록
- 신고 버튼을 통한 `/send_telegram` 호출
- 자동/수동 순찰 모드 토글
- 수동 모드 D-Pad 및 키보드 방향키/WASD 입력 처리
- 사이드바와 다크 모드

다만 순찰 기록, 실제 위치, 실제 로봇 이동 명령, 경고 방송, 감지 결과 push/polling, 갤러리 저장은 아직 프론트엔드 자리 표시 또는 주석 수준의 미연동 영역으로 보인다.

## 다이어그램 기준

- `Activity_Diagram.png`는 Raspberry Pi, GPU/AI 분석, 웹 관제 흐름을 나누어 설명한다. 구현 시 Raspberry Pi 쪽은 순찰 모드 판별, 자율/수동 주행, 센서 수집, 네트워크 연결/오프라인 큐 전송을 담당하는 흐름으로 본다.
- GPU/AI 분석 쪽은 영상 수신, 객체 탐지, 침입/의심 객체 판정, pose estimation 기반 행동 분석, 경고/위험 이벤트 분류, TTS/신고/관리자 통신, 이벤트 전후 영상 저장, 순찰 로그 저장 흐름을 기준으로 한다.
- 웹 관제 쪽은 실시간 영상 수신/송출, 주행 모드 설정, 수동 주행 방향키 조작 및 모터 제어 명령 전송 흐름을 기준으로 한다.
- `ERD.png`는 `users`, `system_status`, `event_log`, `action_log`를 핵심 테이블로 둔다. 실제 DB 구현 시 이벤트, 상태 로그, 관리자 조치 기록은 이 구조를 우선 참고한다.
- `event_log`는 AI/시스템 이벤트의 원천 기록이며, `action_log`는 관리자가 어떤 이벤트에 대해 경고, 수동 이동, 신고, 통신, 메모를 수행했는지 남기는 기록으로 본다.

## 실행 예시

Flask 관제 서버:

```bash
python frontend/app.py
```

노트북 웹캠 프레임 업로드 테스트:

```bash
python perception/local_cam.py
```

테스트 영상 분석:

```bash
python perception/main.py --source data/test_videos/scene3_assault.mp4
```

RTSP 입력 사용 계획:

```bash
python perception/main.py --source rtsp
```

주의: 현재 `perception/main.py`의 `LocalVideoReader`는 파일 경로 존재 여부를 먼저 확인하므로, `--source rtsp`는 README에 적혀 있지만 그대로는 추가 연결 코드가 필요할 수 있다.

## Task & Workflow

사용자가 기능 구현 또는 버그 수정을 요청하면 아래 4단계를 반드시 순차적으로 실행한다. 문서화 단계를 건너뛰고 코드만 단독으로 수정하는 것은 금지한다.

1. 작업 계획서 작성 (Planning)
   - 코드를 수정하기 전, 요구사항을 분석하고 기술적 접근 방식을 정리한다.
   - 계획서는 루트 디렉토리 아래 `docs/` 경로에 저장한다.
   - 파일명 형식: `docs/YYYYMMDD_[Front|Back|FULL]_작업명_plan.md`

2. 코드 구현 (Execution)
   - 1단계의 계획을 바탕으로 `capstone`의 코드를 작성하거나 수정한다.

3. 작업 결과 보고서 작성 (Documentation)
   - 코딩이 완료되면 수정/생성된 파일 목록과 핵심 변경 사항을 요약한다.
   - 결과 보고서는 루트 디렉토리 아래 `docs/` 경로에 저장한다.
   - 파일명 형식: `docs/YYYYMMDD_[Front|Back|FULL]_작업명_result.md`

4. 버전 관리 및 원격 저장소 동기화 (Git & Memento Sync)
   - 3단계 완료 후 코드 푸시가 필요하면 지정 스크립트를 사용한다.
   - 사용 명령: `./scripts/push_with_memento.sh "<커밋 메시지>"`
   - 내장 `git push` 단독 사용은 금지한다.

필수 제약:

- 파일명에는 당일 날짜와 작업 범위 태그(`[Front]`, `[Back]`, `[FULL]` 중 택 1)를 반드시 포함한다.
- 계획서와 결과 보고서 작성 없이 코드만 수정하는 것을 엄격히 금지한다.

## 환경 변수와 비밀값

`.env`는 `.gitignore`에 포함되어 있으며 비밀값을 커밋하지 않는다. 확인된 키 이름은 다음과 같다.

- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`
- `SPATIAL_THRESHOLD_IOU`
- `SPATIAL_THRESHOLD_DIST`
- `TEMPORAL_THRESHOLD_FRAMES`
- `RTSP_URL`

`app.py`와 `utils/telegram_notifier.py` 모두 텔레그램 환경 변수를 사용한다. 알림 기능을 다룰 때는 토큰/채팅 ID를 로그, 문서, 커밋 메시지에 노출하지 않는다.

## 작업 시 주의사항

- `PROJECT.md`를 우선 기준으로 삼되, 코드/모델 구현은 아직 실험 중임을 전제로 설명하거나 수정한다.
- `weights/`, `data/test_videos/`, `output/`, `__pycache__/`, `.git/` 내부 파일은 대용량/생성물/메타데이터로 취급하고 불필요하게 편집하지 않는다.
- 모델 파일을 수정할 때는 9개 파이프라인의 import 경로와 반환 객체 형태를 맞춘다. `perception/main.py`는 탐지 결과가 `id`, `box`, `cls`, `center`를 가진 dict 리스트라고 가정한다.
- YOLO-Pose 계열은 `keypoints`, `keypoints_scores`를 추가로 넘기며, 해당 행동 인식기는 MMPose를 생략한다.
- `CascadingTrigger`는 행동 인식을 모든 객체에 수행하지 않고 의심 상태 객체만 넘기기 위한 1차 필터다. 임계값 변경은 오탐/미탐에 직접 영향을 준다.
- Flask 서버의 전역 상태(`current_frame`, `robot_status`)는 단순 테스트 구조다. 동시성, 인증, 저장소, 실제 장치 제어가 필요해지면 별도 설계가 필요하다.
- 프론트엔드에는 실제 데이터 연동 전 자리 표시 값이 있다. 새 기능을 추가할 때 더미 데이터를 실제 데이터처럼 문서화하지 않는다.
- 텔레그램 전송은 네트워크 의존 기능이므로 테스트 실패 시 토큰, 채팅 ID, 네트워크, API 응답을 분리해서 확인한다.

## 우선 연결하면 좋은 미완성 지점

- `perception/main.py --source rtsp`가 실제로 `perception/stream/rtsp_receiver.py`를 사용하도록 연결
- 분석 파이프라인 결과를 Flask 대시보드의 영상/알림/갤러리/로그로 전달
- `/move` 같은 로봇 수동 제어 API와 실제 모터 제어 코드 연결
- ROS/SLAM 위치 정보를 미니맵과 상태 로그에 연결
- 감지 이벤트 저장 구조 설계: 시간, 위치, 객체, 행동, 점수, 스냅샷, 신고 여부
- Raspberry Pi 환경에서 실행 가능한 경량 모델/CPU 또는 가속기 전략 정리
