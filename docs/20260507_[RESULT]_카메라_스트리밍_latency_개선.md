# 20260507 [RESULT] 카메라 스트리밍 latency 개선

## 1. 작업 요약

Raspberry Pi 카메라 영상이 대시보드에 표시될 때 발생하던 latency를 줄이기 위해 서버의 H.264 stream 처리 구조를 개선했다.

핵심 변경은 영상 preview 경로와 모델 추론 경로를 분리한 것이다.
이제 `/stream/h264`로 들어온 frame은 먼저 최신 preview frame으로 즉시 publish되고, 모델 추론은 별도 worker가 최신 frame만 가져가 처리한다.

목표:

- 모델 OFF에서는 대시보드 preview latency를 낮춘다.
- 모델 ON에서도 preview 영상이 모델 처리 속도 때문에 계속 밀리지 않게 한다.
- 모델 결과는 GPU worker가 가능한 최신 frame을 처리하고, 오래된 frame은 버린다.

## 2. 수정 파일

```text
server/app.py
perception/pipeline_factory.py
perception/models/detector_yolo.py
docs/20260507_[PLAN]_카메라_스트리밍_latency_개선.md
```

새로 작성한 결과 문서:

```text
docs/20260507_[RESULT]_카메라_스트리밍_latency_개선.md
```

## 3. 주요 변경 사항

### 3.1. latest-frame preview publish

기존 `/video_feed`는 live 상태에서 약 0.03초마다 현재 `current_frame`을 반복 yield했다.

변경 후에는 다음 상태를 추가해 새 frame이 들어왔을 때만 송출하도록 했다.

```text
current_frame_seq
frame_condition
publish_stats
```

동작:

- 새 preview frame이 publish될 때 `current_frame_seq`가 증가한다.
- `/video_feed` client는 마지막으로 보낸 seq와 현재 seq를 비교한다.
- 같은 frame을 반복 송출하지 않는다.
- client가 느리면 중간 frame을 건너뛰고 최신 frame을 받는다.

### 3.2. H.264 decode와 inference worker 분리

기존 H.264 처리 흐름:

```text
ffmpeg decode
-> frame read
-> process_and_publish_frame()
-> optional inference
-> JPEG encode
-> /video_feed
```

변경 후 흐름:

```text
ffmpeg decode
-> frame read
-> latest preview publish
-> latest inference slot update

inference worker
-> latest frame only
-> FrameProcessor.process()
-> latest_result update
```

이 구조에서는 모델 추론이 느려져도 H.264 decode loop와 preview publish가 직접 막히지 않는다.

### 3.3. latest-only inference slot

모델 추론 입력은 queue를 길게 쌓지 않고 단일 latest slot으로 관리한다.

정책:

- 새 추론 후보 frame이 들어왔는데 이전 후보가 아직 처리 전이면 이전 frame을 버린다.
- `INFERENCE_DROP_OLDER_THAN_SEC`보다 오래된 frame은 추론하지 않는다.
- 새 H.264 stream이 시작되면 이전 stream의 늦은 추론 결과를 버리도록 `stream_id`를 둔다.

이를 통해 모델 ON 상태에서 frame backlog가 쌓이며 latency가 계속 증가하는 문제를 줄인다.

### 3.4. GPU inference 설정

모델 추론은 CPU가 아니라 GPU를 기본 전제로 두도록 설정을 추가했다.

추가 설정:

```env
DEVICE=cuda:0
GPU_REQUIRED_FOR_INFERENCE=true
```

서버 startup에서 GPU 사용 가능 여부를 확인한다.

- `INFERENCE_ENABLED=true`
- `GPU_REQUIRED_FOR_INFERENCE=true`
- `DEVICE=cuda:*`

위 조건에서 GPU를 사용할 수 없으면 모델을 로드하지 않고 `latest_result["model_error"]`에 오류를 기록한다.
`MODEL_REQUIRED=true`인 경우에는 서버 startup을 실패시킨다.

### 3.5. pipeline device 전달

`perception/pipeline_factory.py`의 `create_pipeline()`에 `device` 인자를 추가했다.

```python
create_pipeline(choice, device="cuda:0")
```

각 pipeline의 detector/action analyzer 생성 시 같은 device를 전달한다.

`perception/models/detector_yolo.py`도 `device`를 받아 YOLO `track()` 호출에 전달하도록 변경했다.

### 3.6. `/frame` 테스트 경로 보강

`POST /frame`은 기존처럼 JPEG frame 테스트용으로 유지했다.

추가로 query parameter를 지원한다.

```text
/frame?infer=false
/frame?infer=true
```

이를 통해 Python JPEG 테스트 경로에서도 모델 추론 여부를 명시할 수 있다.

### 3.7. stream status 지표 확장

`GET /api/stream_status`에 latency와 GPU 상태 확인용 필드를 추가했다.

추가된 주요 필드:

```text
latest_frame_seq
latest_frame_age_ms
decode_fps
publish_fps
stream_jpeg_quality
inference_available
inference_max_fps
inference_max_result_age_sec
inference_drop_older_than_sec
inference_fps
inference_requested_frames
inference_completed_frames
inference_dropped_frames
inference_last_ms
inference_result_age_ms
inference_result_stale
inference_device
gpu_required_for_inference
gpu_available
gpu_name
gpu_memory_used_mb
gpu_error
```

이제 대시보드 latency 문제가 생겼을 때 다음을 분리해서 볼 수 있다.

- H.264 byte 수신 여부
- decode FPS
- preview publish FPS
- 최신 frame age
- inference FPS
- inference frame drop 수
- GPU 사용 가능 여부

## 4. 추가 설정 기본값

`server/app.py`에 추가하거나 변경한 기본값:

```env
SAVE_RECEIVED_FRAMES=false
STREAM_JPEG_QUALITY=75
PREVIEW_MAX_FPS=<STREAM_FPS 기본값>
DEVICE=cuda:0
GPU_REQUIRED_FOR_INFERENCE=true
INFERENCE_MAX_FPS=5
INFERENCE_MAX_RESULT_AGE_SEC=3.0
INFERENCE_DROP_OLDER_THAN_SEC=2.0
```

`SAVE_RECEIVED_FRAMES`는 기본값을 `false`로 바꿨다.
운영 중 매 frame마다 디스크에 `latest.jpg`를 쓰는 작업은 latency에 불리하므로, 필요할 때만 env로 켜는 방향이다.

## 5. 기대 효과

모델 OFF:

- 같은 MJPEG frame 반복 송출 감소
- 최신 frame 기준 송출
- 불필요한 디스크 write 기본 비활성화
- JPEG quality 설정 가능

모델 ON:

- preview publish와 모델 추론이 분리된다.
- 모델이 느려도 preview stream이 추론 처리 순서를 기다리지 않는다.
- 오래된 추론 후보 frame은 버려 latency 누적을 막는다.
- GPU device 기준으로 모델을 로드한다.
- AI 결과 latency가 오래되면 `inference_result_stale`로 확인할 수 있다.

## 6. 검증 결과

수행한 정적 검증:

```bash
python -c "import ast; [ast.parse(open(p, encoding='utf-8').read(), filename=p) for p in ['capstone/server/app.py','capstone/perception/pipeline_factory.py','capstone/perception/models/detector_yolo.py']]; print('ast ok')"
```

결과:

```text
ast ok
```

추가로 `python -m py_compile`도 한 번 수행했고 통과했다.
다만 py_compile 과정에서 `__pycache__` 파일이 갱신되어, 검증 부산물은 정리했다.

서버 import 검증:

```bash
python -c "import sys; sys.path.insert(0, 'capstone'); import server.app as app"
```

현재 로컬 Python 환경에서는 `cv2`가 없어 실패했다.

```text
ModuleNotFoundError: No module named 'cv2'
```

따라서 실제 서버 runtime 검증은 OpenCV가 설치된 프로젝트 실행 환경에서 수행해야 한다.

## 7. 운영 확인 방법

GPU 서버 실행:

```bash
cd ~/capstone
uvicorn server.app:app --host 0.0.0.0 --port 21063
```

Raspberry Pi에서 모델 OFF preview 확인:

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://<GPU_SERVER_IP>:21063/stream/h264?robot_id=pi-01&infer=false"
```

모델 ON 확인:

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://<GPU_SERVER_IP>:21063/stream/h264?robot_id=pi-01&infer=true"
```

상태 확인:

```bash
curl http://localhost:21063/api/stream_status
```

확인할 핵심 필드:

```text
camera_state
latest_frame_age_ms
decode_fps
publish_fps
inference_fps
inference_dropped_frames
inference_result_age_ms
inference_result_stale
inference_device
gpu_available
gpu_name
```

## 8. 남은 작업

- OpenCV, ffmpeg, torch, CUDA, 모델 가중치가 있는 실제 GPU 서버에서 runtime 검증
- Raspberry Pi 실기기에서 모델 OFF latency 측정
- 모델 ON 상태에서 `inference_result_age_ms <= 3000ms` 유지 여부 확인
- pipeline별 평균 `inference_last_ms` 기록
- 필요 시 `INFERENCE_MAX_FPS`, `STREAM_INFER_EVERY_N`, `PREVIEW_MAX_FPS` 튜닝
- dashboard에서 `inference_result_stale` 상태를 UI로 표시하는 후속 작업
- WebRTC 전환 여부는 MJPEG latest-frame 개선 후 측정 결과를 보고 판단

## 9. 주의 사항

- 이번 변경은 서버 streaming/inference 구조 중심이며 DB schema는 수정하지 않았다.
- `/frame` JPEG 경로는 테스트용으로 유지했다.
- 운영 영상 송신은 `/stream/h264` 사용을 권장한다.
- CPU 추론은 운영 목표에서 제외하고, GPU 추론 기준으로 latency 목표를 잡는다.
