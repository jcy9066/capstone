# 20260429 [FULL] 실시간 RTSP 모델 선택 탐지 계획

## 1. 작업 목표

Raspberry Pi 4 카메라 영상을 GPU 서버에서 실시간으로 수신하고, 사용자가 1~9번 분석 파이프라인 중 하나를 선택해 객체 탐지 및 행동 분석을 수행할 수 있도록 `perception/main.py`의 입력 구조를 확장한다.

현재 Raspberry Pi IP는 `192.168.0.127`이지만, 최종 구성에서는 IP가 바뀌어도 코드 수정 없이 `.env` 설정만 바꿔 동작해야 한다.

## 2. 현재 상태 요약

- `perception/main.py`는 1~9번 모델 조합 선택 기능이 이미 있다.
- 현재 입력은 로컬 영상 파일만 안정적으로 처리한다.
- `perception/stream/rtsp_receiver.py`는 RTSP 프레임 수신기가 이미 존재하지만 `main.py`와 연결되어 있지 않다.
- `perception/config/settings.py`는 `.env`에서 `RTSP_URL`을 읽는다.
- `.env`에는 `RTSP_URL=rtsp://raspberrypi.local:8554/stream` 예시가 주석으로만 있다.
- `README.md`에는 `python perception/main.py --source rtsp` 예시가 있으나, 현재 `LocalVideoReader`가 파일 존재 여부를 먼저 검사하므로 그대로는 동작하지 않는다.

## 3. 설정 설계

라즈베리파이 IP처럼 환경마다 바뀌는 값은 `.env`에 둔다.

권장 우선순위:

1. `.env`에 `RTSP_URL`을 직접 설정한다.
   - 예: `RTSP_URL=rtsp://192.168.0.127:8554/stream`
   - 장점: 포트, 경로, 인증 정보가 바뀌어도 한 줄로 대응 가능하다.
2. 보조 옵션으로 `RASPBERRY_PI_IP`, `RTSP_PORT`, `RTSP_PATH`를 둘 수 있다.
   - 예: `RASPBERRY_PI_IP=192.168.0.127`
   - `RTSP_URL`이 없을 때 `rtsp://{RASPBERRY_PI_IP}:{RTSP_PORT}{RTSP_PATH}`를 조립한다.

최종 구현에서는 `RTSP_URL` 직접 지정을 1순위로 사용하고, 없으면 IP 기반 URL을 생성하는 방식이 가장 유연하다.

## 4. 구현 대상

### 4.1. 환경 변수 확장

대상 파일:

- `perception/config/settings.py`
- `.env` 예시

작업:

- `RASPBERRY_PI_IP` 기본값을 `192.168.0.127`로 둔다.
- `RTSP_PORT` 기본값을 `8554`로 둔다.
- `RTSP_PATH` 기본값을 `/stream`으로 둔다.
- `RTSP_URL`이 설정되어 있으면 그대로 사용한다.
- `RTSP_URL`이 없으면 `RASPBERRY_PI_IP`, `RTSP_PORT`, `RTSP_PATH`로 URL을 생성한다.

### 4.2. 입력 리더 통합

대상 파일:

- `perception/main.py`
- `perception/stream/rtsp_receiver.py`

작업:

- 공통 인터페이스를 맞춘다.
  - `get_frame()`
  - `width`
  - `height`
  - `fps`
  - `release()` 또는 `stop()`
- `--source` 값에 따라 분기한다.
  - 일반 파일 경로: 기존 `LocalVideoReader`
  - `rtsp`: `.env`의 RTSP 설정 사용
  - `rtsp://...`: CLI에서 받은 URL 직접 사용
- RTSP 연결 실패 시 명확한 오류 메시지를 출력한다.
- RTSP 수신에서는 오래된 프레임을 버리고 최신 프레임을 유지해 실시간 지연을 줄인다.

### 4.3. 모델 선택 방식 개선

대상 파일:

- `perception/main.py`

작업:

- 기존 대화형 `input()` 방식은 유지한다.
- 추가로 `--pipeline 1..9` 옵션을 지원한다.
- 실시간 실행 예:
  - `python perception/main.py --source rtsp --pipeline 1`
  - `python perception/main.py --source rtsp://192.168.0.127:8554/stream --pipeline 1`
- `--pipeline`이 없으면 기존처럼 번호를 입력받는다.

### 4.4. 실시간 출력 방식

대상 파일:

- `perception/main.py`

작업:

- 파일 입력은 기존처럼 결과 mp4 저장을 기본으로 유지한다.
- RTSP 입력은 무한 스트림이므로 저장 파일이 무한히 커질 수 있다.
- 1차 구현에서는 다음 옵션을 둔다.
  - `--display`: OpenCV 창으로 분석 결과 실시간 표시
  - `--save`: RTSP 결과 영상을 저장
  - `--max-frames`: 테스트용 프레임 수 제한
- 기본값은 실시간 분석을 계속 수행하되, 저장은 명시 옵션으로만 켠다.

### 4.5. 대시보드 연동은 후속 작업으로 분리

이번 작업의 중심은 GPU 서버에서 RTSP를 받아 모델 탐지를 수행하는 것이다.

후속 작업으로 분리할 내용:

- 분석 결과 프레임을 `frontend/app.py`의 `/video_feed`로 전달
- 탐지 이벤트를 웹 알림 패널에 표시
- 이벤트 스냅샷/전후 영상 저장
- 라즈베리파이 수동 제어 API와 모터 제어 연동

## 5. 실행 예시

`.env`:

```env
RASPBERRY_PI_IP=192.168.0.127
RTSP_PORT=8554
RTSP_PATH=/stream
# 또는 아래 한 줄을 직접 사용
# RTSP_URL=rtsp://192.168.0.127:8554/stream
```

GPU 서버에서 실행:

```bash
cd ~/capstone
python perception/main.py --source rtsp --pipeline 1 --display
```

다른 IP로 바뀐 경우:

```env
RASPBERRY_PI_IP=192.168.0.130
```

또는:

```env
RTSP_URL=rtsp://192.168.0.130:8554/stream
```

## 6. 검증 계획

1. 로컬 영상 회귀 테스트
   - `python perception/main.py --source data/test_videos/scene3_assault.mp4 --pipeline 1 --max-frames 30`
   - 기존 파일 입력 분석이 깨지지 않는지 확인한다.
2. RTSP 연결 테스트
   - `python perception/main.py --source rtsp --pipeline 1 --max-frames 100`
   - 라즈베리파이에서 프레임이 들어오는지 확인한다.
3. IP 변경 테스트
   - `.env`의 `RASPBERRY_PI_IP` 또는 `RTSP_URL`을 바꾸고 코드 수정 없이 재실행한다.
4. 모델 선택 테스트
   - 최소 1번 경량 모델과 현재 사용하려는 대표 모델 1개를 실행한다.
5. 장시간 테스트
   - 5~10분 이상 실행해 RTSP 큐 지연, 메모리 증가, 프레임 끊김 여부를 확인한다.

## 7. 위험 요소와 대응

- RTSP URL 형식이 라즈베리파이 송출 도구에 따라 다를 수 있다.
  - 대응: `RTSP_URL` 직접 지정 기능을 1순위로 둔다.
- 9개 모델 중 일부는 GPU 서버의 설치 환경이나 가중치 경로에 따라 실패할 수 있다.
  - 대응: 파이프라인 생성 실패 시 어떤 import 또는 weight에서 실패했는지 출력한다.
- RTSP는 FPS/해상도 값을 즉시 못 읽을 수 있다.
  - 대응: 첫 프레임 수신 후 width/height를 확정하고 FPS는 기본 30으로 fallback한다.
- 실시간 스트림 저장은 파일 크기가 커질 수 있다.
  - 대응: `--save`를 명시했을 때만 저장하고, 테스트에는 `--max-frames`를 사용한다.

## 8. 예상 수정 파일

- `perception/config/settings.py`
- `perception/main.py`
- `perception/stream/rtsp_receiver.py`
- `.env`
- `README.md`
- 작업 완료 후 `docs/20260429_[FULL]_실시간_RTSP_모델선택_탐지_result.md`

