# 20260506 [FULL] 카메라 연결 끊김 표시 결과

## 1. 작업 브랜치

```text
feat/camera-disconnect-indicator
```

## 2. 목표

라즈베리 파이 또는 라즈베리 파이 카메라 연결이 끊겼을 때, 대시보드의 `실시간 카메라` 영역에 마지막 프레임이 계속 고정되어 보이지 않도록 수정했다.

연결 끊김 상태에서는 다음을 보장한다.

- 마지막 카메라 프레임을 그대로 보여주지 않는다.
- 카메라 영역을 회색 비활성 상태로 표시한다.
- `카메라 연결이 끊겼습니다` 또는 `라즈베리 파이와 연결이 끊겼습니다` 메시지를 표시한다.
- 헤더의 `LIVE` 배지를 `OFFLINE` 상태로 바꾼다.
- `/get_status 200 OK` 같은 정상 access log는 쉘에 계속 출력되지 않게 한다.
- 파이 스트림 종료 시 발생하는 `ClientDisconnect`는 오류가 아닌 정상 종료로 처리한다.

## 3. 변경 파일

### 3.1. 서버

- `server/app.py`

변경 내용:

- 카메라 프레임 타임아웃 설정 추가
  - `CAMERA_TIMEOUT_SEC`
  - `ROBOT_STATUS_TIMEOUT_SEC`
- 공통 프레임 수신 시각 기록 추가
  - `/frame`
  - `/stream/h264`
- 카메라 연결 상태 계산 함수 추가
  - `live`
  - `waiting`
  - `camera_disconnected`
  - `robot_disconnected`
  - `error`
- `/api/stream_status` 응답 확장
  - `camera_state`
  - `camera_connected`
  - `message`
  - `last_frame_age_sec`
  - `last_status_age_sec`
  - `received_fps`
- `/video_feed`에서 연결 끊김 상태일 때 마지막 프레임 대신 회색 offline placeholder JPEG 송출
- H.264 스트림이 끊길 때 발생하는 `ClientDisconnect`를 정상 종료로 처리
- `uvicorn.access` 로그를 `WARNING` 이상만 출력하도록 조정
- `python server/app.py` 실행 시 `access_log=False` 적용

### 3.2. 프론트엔드

- `frontend/static/script.js`
- `frontend/static/style.css`
- `frontend/templates/index.html`

변경 내용:

- 1초마다 `/api/stream_status` polling 추가
- `camera_state`가 `live`가 아니면 카메라 이미지를 숨기고 연결 끊김 메시지 표시
- `#video-wrapper`에 `.camera-offline` 클래스 토글
- `LIVE` 배지를 `OFFLINE`으로 전환
- 카메라 영역 회색 비활성 스타일 추가
- 브라우저 캐시 방지를 위해 `script.js`, `style.css` URL에 버전 쿼리 추가

### 3.3. 구형 Flask 대시보드 호환

- `frontend/app.py`

변경 내용:

- `/api/stream_status` 호환 API 추가
- 프레임 수신 시각 기록 추가
- 연결 끊김 상태에서 마지막 프레임 대신 회색 offline placeholder JPEG 송출

## 4. 동작 방식

### 4.1. 정상 상태

라즈베리 파이에서 새 프레임이 `CAMERA_TIMEOUT_SEC` 이내에 계속 들어오면 서버는 다음 상태를 반환한다.

```json
{
  "camera_state": "live",
  "camera_connected": true,
  "message": "영상 수신 중"
}
```

대시보드는 영상을 표시하고 `LIVE` 배지를 유지한다.

### 4.2. 카메라 스트림 종료

파이에서 카메라 실행을 끊으면 서버 로그에는 다음과 같은 메시지가 나올 수 있다.

```text
[ffmpeg] [h264 @ ...] error while decoding ...
[stream/h264] disconnected robot_id=pi-01
```

이 상태는 카메라 스트림 연결 종료로 간주한다.

서버는 마지막 프레임이 최근 프레임이더라도 `disconnected_at`이 기록된 경우 즉시 `camera_disconnected` 또는 `robot_disconnected`로 판정한다.

대시보드에는 마지막 카메라 화면이 고정되어 남지 않고, 회색 offline 화면이 표시된다.

### 4.3. 라즈베리 파이 전체 연결 종료

프레임도 들어오지 않고 상태 갱신도 `ROBOT_STATUS_TIMEOUT_SEC` 이상 멈추면 서버는 다음 상태를 반환한다.

```json
{
  "camera_state": "robot_disconnected",
  "camera_connected": false,
  "message": "라즈베리 파이와 연결이 끊겼습니다"
}
```

대시보드는 회색 카메라 영역과 연결 끊김 메시지를 표시한다.

## 5. 로그 처리

### 5.1. `ClientDisconnect`

이전에는 파이 스트림 종료 시 아래 예외가 ASGI 오류로 출력됐다.

```text
starlette.requests.ClientDisconnect
```

수정 후에는 정상적인 클라이언트 연결 종료로 처리한다. 따라서 카메라 실행을 중단해도 긴 `ERROR: Exception in ASGI application` 스택트레이스가 출력되지 않아야 한다.

### 5.2. 정상 access log 숨김

이전에는 `/get_status` polling 때문에 쉘에 아래 로그가 반복 출력됐다.

```text
INFO:     10.107.80.56:5369 - "GET /get_status HTTP/1.1" 200 OK
```

수정 후에는 uvicorn access log를 끄거나 `WARNING` 이상으로 낮춰, 정상 200 OK 요청은 쉘에 출력되지 않게 했다.

오류가 발생한 경우에는 기존처럼 오류 로그를 확인할 수 있다.

## 6. 검증

다음 문법 검사를 통과했다.

```bash
python -B -c "import ast, pathlib; ast.parse(pathlib.Path('server/app.py').read_text())"
python -B -c "import ast, pathlib; ast.parse(pathlib.Path('frontend/app.py').read_text())"
node --check frontend/static/script.js
```

## 7. 수동 확인 절차

1. 서버를 재시작한다.
2. 대시보드를 새로고침한다.
3. 라즈베리 파이에서 H.264 카메라 스트림을 시작한다.
4. 대시보드에 영상과 `LIVE` 배지가 표시되는지 확인한다.
5. 파이에서 카메라 실행을 중단한다.
6. 쉘에 `[stream/h264] disconnected robot_id=pi-01` 로그가 찍히는지 확인한다.
7. 대시보드에서 마지막 카메라 프레임이 사라지고 회색 offline 화면이 표시되는지 확인한다.
8. `/get_status 200 OK` 로그가 쉘에 반복 출력되지 않는지 확인한다.
9. 스트림을 다시 시작하면 영상과 `LIVE` 상태로 복귀하는지 확인한다.

## 8. 주의 사항

- 서버 재시작이 필요하다.
- 브라우저가 이전 `script.js` 또는 `style.css`를 캐시할 수 있으므로, 대시보드 확인 시 강력 새로고침을 권장한다.
- `server/__pycache__` 파일은 실행 환경에서 자동 갱신될 수 있다. 코드 리뷰 또는 커밋 시 포함 여부를 별도로 판단한다.
- offline placeholder 프레임의 문구는 OpenCV 기본 폰트 제한 때문에 영어로 표시한다. 실제 한국어 문구는 HTML 오버레이에서 표시한다.

## 9. 완료 기준

- 파이 카메라 스트림 종료 후 마지막 프레임이 대시보드에 고정되지 않는다.
- 대시보드 카메라 영역이 회색 offline 상태로 전환된다.
- `LIVE` 배지가 `OFFLINE`으로 전환된다.
- `/api/stream_status`에서 연결 끊김 상태를 확인할 수 있다.
- 파이 스트림 종료가 `ClientDisconnect` ASGI 오류로 출력되지 않는다.
- 정상 `/get_status` polling 로그가 쉘에 반복 출력되지 않는다.
