# 20260507 [PLAN] 카메라 스트리밍 latency 개선

## 1. 목표

현재 Raspberry Pi 카메라에서 송신한 영상을 모델 추론 없이 대시보드에 표시할 때도 약 1초 latency가 발생한다.
모델 추론을 켜면 이 지연이 더 커지므로, 영상 표시 경로와 추론 경로를 분리해 대시보드는 항상 최신 프레임을 보여주도록 개선한다.

목표 지표:

- 모델 OFF: Raspberry Pi -> 대시보드 표시 latency를 LAN 기준 300~500ms 이하로 낮춘다.
- 모델 ON: 영상 preview는 밀리지 않고, 모델 결과 표시 latency는 최대 2~3초 이내로 제한한다.
- 모델 ON latency는 2~3초를 상한으로 잡되, GPU 추론과 frame drop 정책으로 가능하면 1초대까지 낮춘다.
- 모델이 느릴 때는 backlog를 쌓지 않고 오래된 프레임을 버린다.
- 모델 추론은 CPU가 아니라 GPU를 기본 전제로 둔다.

이번 문서는 계획만 다룬다. 코드 수정은 별도 작업에서 진행한다.

## 2. 현재 구조 요약

현재 프로젝트에는 영상 송신 경로가 두 가지 있다.

### 2.1. 운영 권장 경로: H.264 stream

README 기준 운영 구조:

```text
Raspberry Pi
  rpicam-vid
  -> curl chunked upload
  -> POST /stream/h264

GPU 통합 서버
  server/app.py
  -> ffmpeg subprocess로 H.264 decode
  -> BGR raw frame
  -> process_and_publish_frame()
  -> current_frame JPEG 갱신
  -> GET /video_feed MJPEG

Dashboard
  frontend/templates/index.html
  -> img#camera-stream
```

관련 파일:

- `README.md`
- `server/app.py`
- `frontend/templates/index.html`
- `frontend/static/script.js`

### 2.2. 테스트 경로: JPEG frame POST

`raspberry/pi_client.py`는 OpenCV로 카메라를 읽고 JPEG로 인코딩한 뒤 `/frame`으로 multipart POST한다.

```text
cv2.VideoCapture(0)
-> cap.read()
-> cv2.imencode(".jpg")
-> requests.post("/frame")
-> server cv2.imdecode()
-> process_and_publish_frame()
-> server cv2.imencode(".jpg")
-> /video_feed MJPEG
-> dashboard img
```

이 경로는 프레임마다 HTTP 요청과 JPEG encode/decode가 반복되므로 latency와 CPU 사용량이 커지기 쉽다.
운영 스트리밍에는 `/stream/h264` 경로를 우선 사용해야 한다.

정리하면, 현재 프로젝트가 항상 매 프레임 JPEG 파일을 서버에 보내는 것은 아니다.
운영 권장 경로는 H.264 연속 stream이고, 매 프레임 JPEG POST는 `raspberry/pi_client.py`의 테스트/보조 경로다.
실시간 관제 목적이라면 굳이 JPEG 이미지를 매 프레임 전송할 필요가 없고, H.264 stream 또는 장기적으로 WebRTC 계열이 더 적합하다.

## 3. latency 발생 지점

### 3.1. JPEG 경로의 반복 encode/decode

`raspberry/pi_client.py`는 매 프레임마다 다음 작업을 수행한다.

```text
camera frame
-> JPEG encode
-> multipart POST
```

서버의 `/frame`은 다시 다음 작업을 수행한다.

```text
request body
-> JPEG decode
-> optional inference
-> JPEG encode
-> current_frame 저장
```

모델을 돌리지 않더라도 이중 JPEG 처리와 프레임별 HTTP 요청 비용이 latency를 만든다.

추가로 현재 `/frame` 경로는 `process_and_publish_frame()`을 기본값으로 호출하므로 `infer=True`가 적용된다.
따라서 Python 클라이언트 테스트 경로에서는 의도와 달리 모델이 실행될 수 있다.

### 3.2. MJPEG 표시 구조의 브라우저 버퍼

대시보드는 `img#camera-stream`에서 `/video_feed`를 MJPEG로 표시한다.

`server/app.py`의 `generate_frames()`는 live 상태에서 약 0.03초마다 현재 `current_frame`을 yield한다.
이 방식은 단순하지만 다음 문제가 있다.

- 새 프레임이 들어오지 않아도 같은 frame을 반복 송출할 수 있다.
- 브라우저나 네트워크가 느리면 MJPEG stream 내부에 오래된 frame이 남을 수 있다.
- 서버가 최신 frame만 들고 있어도 client 표시 쪽에서는 지연이 누적될 수 있다.

### 3.3. H.264 decode와 inference가 같은 흐름에 있음

`/stream/h264`에서는 ffmpeg stdout에서 raw frame을 읽고 `process_and_publish_frame()`을 호출한다.
현재 구조에서는 추론을 켜면 frame 처리 루프가 모델 처리 시간만큼 느려진다.

```text
ffmpeg decode
-> frame read
-> inference
-> JPEG encode
-> publish
```

모델이 1 frame 처리에 200ms 이상 걸리면 입력 stream은 계속 들어오는데 처리 루프가 밀린다.
이때 과거 frame을 순서대로 처리하려고 하면 대시보드 영상 latency가 계속 증가한다.

### 3.4. 모델 파이프라인 자체가 무거움

`perception/pipeline_factory.py`에는 YOLO, DINO, RTMPose, ViTPose, ST-GCN, PoseConv3D 조합이 있다.
특히 pose/action 계열 모델은 단일 frame 추론 비용뿐 아니라 temporal buffer도 사용한다.

따라서 모델 결과를 매 프레임 영상에 직접 합성한 뒤 보여주는 구조는 실시간 preview에 불리하다.

## 4. 개선 방향

핵심 원칙은 다음과 같다.

```text
대시보드 영상 표시 = latest raw preview frame
모델 추론 = latest frame을 별도 worker에서 처리
모델 결과 표시 = frame stream과 분리된 metadata overlay
```

즉, 영상은 항상 최신 프레임을 보여주고, 추론은 가능한 속도로 따라오게 만든다.
느린 추론 때문에 영상이 과거로 밀리면 안 된다.

## 5. 단계별 적용 계획

### 5.1. 1단계: 운영 송신 경로를 H.264로 고정

운영에서는 `raspberry/pi_client.py`의 `/frame` JPEG 전송을 사용하지 않고 README의 H.264 명령을 사용한다.

권장 실행 형태:

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://<GPU_SERVER_IP>:21063/stream/h264?robot_id=pi-01&infer=false"
```

추가로 Raspberry Pi 쪽에서 low latency 옵션을 검토한다.

- GOP/keyframe 간격을 너무 길게 두지 않는다.
- 필요 이상으로 높은 해상도/FPS를 사용하지 않는다.
- 초기 목표는 `640x480`, `15fps`로 유지한다.
- 네트워크가 불안정하면 Wi-Fi 대신 유선 LAN 또는 5GHz Wi-Fi를 우선한다.

### 5.2. 2단계: 서버 publish를 latest-frame 방식으로 변경

`server/app.py`에서 frame publish 상태를 sequence 기반으로 관리한다.

추가할 상태 개념:

```text
current_frame
current_frame_seq
current_frame_published_at
frame_condition
```

동작:

- 새 frame이 들어올 때만 `current_frame_seq`를 증가시킨다.
- `/video_feed`는 마지막으로 보낸 seq와 현재 seq를 비교한다.
- 같은 frame을 반복해서 빠르게 yield하지 않는다.
- client가 느리면 중간 frame을 건너뛰고 최신 frame만 보낸다.

기대 효과:

- 불필요한 MJPEG 반복 송출 감소
- 브라우저의 오래된 frame 표시 가능성 감소
- 서버의 불필요한 JPEG encode와 네트워크 사용량 감소

### 5.3. 3단계: decode loop와 inference worker 분리

현재 목표 구조:

```text
H.264 request body
-> ffmpeg stdin
-> ffmpeg stdout raw frame
-> decode loop
   -> raw preview publish 즉시 수행
   -> inference_latest_slot에 최신 frame만 교체

inference worker
-> latest frame snapshot 읽기
-> FrameProcessor.process()
-> latest_result 갱신
-> optional annotated_frame 갱신
```

중요 정책:

- inference queue는 `maxsize=1` 또는 단일 latest slot을 사용한다.
- queue가 차 있으면 오래된 frame을 버리고 최신 frame으로 교체한다.
- inference worker는 stream 수신과 decode를 막지 않는다.
- 추론 결과는 늦게 도착해도 대시보드 영상 자체를 지연시키지 않는다.
- inference worker는 GPU 사용 가능 여부를 확인하고, GPU가 없으면 운영 모드에서 경고 또는 실패하도록 한다.

### 5.4. 4단계: raw preview와 annotated result를 분리

기본 `/video_feed`는 raw preview만 표시한다.

추론 결과는 다음 중 하나로 전달한다.

1. 기존 `/api/latest_result` polling 유지
2. 새 WebSocket `/ws/result` 추가

권장안은 WebSocket이다.

```text
server inference worker
-> latest_result update
-> connected dashboard clients에 result push
-> frontend에서 box/label/danger overlay 갱신
```

이렇게 하면 모델 결과가 늦어도 영상 stream은 최신 상태를 유지한다.

단, bounding box를 HTML/CSS overlay로 정확히 맞추려면 다음 정보가 필요하다.

- 원본 frame width/height
- dashboard에 표시된 image 영역의 실제 크기
- letterbox/object-fit 적용 여부

초기 구현에서는 `/api/latest_result` polling을 유지하고, 위험 상태/객체 목록만 먼저 갱신해도 된다.

### 5.5. 5단계: GPU 추론 경로 고정

모델 추론은 CPU가 아니라 GPU를 사용하도록 명시한다.
현재 `perception/config/config.yaml`에도 `device: "cuda:0"` 설정이 있으므로, 통합 서버의 실시간 추론 경로도 이를 기준으로 맞춘다.

구현 정책:

- 서버 startup에서 `torch.cuda.is_available()` 또는 각 모델 framework의 CUDA device 사용 가능 여부를 확인한다.
- 운영 모드에서 GPU를 사용할 수 없으면 모델 추론을 켜지 않거나 명확한 오류를 반환한다.
- `DEVICE=cuda:0` 같은 env를 추가해 pipeline 생성 시 detector, pose, action 모델이 같은 GPU device를 사용하도록 정리한다.
- 가능한 모델은 half precision 또는 TensorRT/ONNX Runtime GPU backend를 후속 최적화 후보로 둔다.
- H.264 decode도 GPU 서버 ffmpeg가 NVDEC/CUDA를 지원하면 GPU decode를 검토한다.

주의할 점:

- 모든 처리를 GPU로 옮길 수는 없다. HTTP 수신, MJPEG 응답, 일부 OpenCV JPEG encode는 CPU 작업이 남는다.
- latency를 크게 좌우하는 모델 추론은 반드시 GPU에서 실행되도록 잡는 것이 핵심이다.
- GPU decode는 ffmpeg 빌드와 NVIDIA driver 환경에 따라 가능 여부가 달라지므로 1차 목표는 GPU inference 고정, 2차 목표는 GPU decode 적용으로 둔다.

### 5.6. 6단계: 모델 추론 빈도 제한과 2~3초 latency budget

`STREAM_INFER_EVERY_N`은 이미 존재한다.
다만 decode loop 내부에서 직접 추론하는 구조에서는 완전한 해결책이 아니다.

worker 분리 후 다음 정책을 사용한다.

- preview publish: 가능한 모든 decoded frame 또는 `PREVIEW_MAX_FPS`까지
- detection/action inference: `INFERENCE_MAX_FPS` 또는 `STREAM_INFER_EVERY_N`
- action recognition: 매 frame이 아니라 일정 간격 또는 trigger 발생 시 실행
- inference queue에 2초보다 오래된 frame이 있으면 추론하지 않고 폐기한다.
- 최신 결과의 age가 3초를 넘으면 dashboard에서 "AI result delayed" 상태로 표시한다.

추천 기본값:

```env
PREVIEW_MAX_FPS=15
INFERENCE_MAX_FPS=5
STREAM_INFER_EVERY_N=3
INFERENCE_MAX_RESULT_AGE_SEC=3.0
INFERENCE_DROP_OLDER_THAN_SEC=2.0
```

사람/위험물 탐지는 비교적 자주 돌리고, pose/action recognition은 trigger 조건을 만족할 때만 실행하는 방향이 좋다.

2~3초 상한을 만족하려면 pipeline 선택도 중요하다.

- 기본 실시간 pipeline은 가장 가벼운 `PIPELINE=1`부터 시작한다.
- DINO, ViTPose, 대형 YOLO, PoseConv3D 조합은 정확도는 좋을 수 있지만 실시간 latency 목표를 넘기기 쉽다.
- action 모델의 temporal window가 길면 구조적으로 결과 latency가 길어질 수 있으므로, 2~3초 목표에서는 sampling window를 줄이거나 trigger 기반으로 실행한다.
- 15fps 기준 2초는 약 30 frame, 3초는 약 45 frame이므로 action 인식 입력도 이 범위 안에서 동작하도록 조정한다.

### 5.7. 7단계: MJPEG 한계가 크면 WebRTC 검토

MJPEG는 구현이 쉽지만 low latency 영상 전송에는 한계가 있다.
브라우저에서 안정적으로 sub-300ms latency를 원하면 WebRTC가 더 적합하다.

장기 후보:

- Pi -> 서버: H.264 RTP/RTSP 또는 WebRTC
- 서버 -> 브라우저: WebRTC
- 모델 결과: WebSocket metadata

다만 WebRTC는 구현 복잡도가 높으므로 이번 1차 개선에서는 MJPEG latest-frame 방식과 inference 분리를 먼저 적용한다.

## 6. 설정 제안

추가하거나 명시할 env:

```env
STREAM_WIDTH=640
STREAM_HEIGHT=480
STREAM_FPS=15
STREAM_JPEG_QUALITY=75

DEVICE=cuda:0
GPU_REQUIRED_FOR_INFERENCE=true
INFERENCE_ENABLED=true
STREAM_INFER_EVERY_N=3
PREVIEW_MAX_FPS=15
INFERENCE_MAX_FPS=5
INFERENCE_MAX_RESULT_AGE_SEC=3.0
INFERENCE_DROP_OLDER_THAN_SEC=2.0

MODEL_REQUIRED=false
SAVE_RECEIVED_FRAMES=false
```

`SAVE_RECEIVED_FRAMES=false`를 권장하는 이유:

- `/frame` 테스트 경로에서 프레임마다 `received_frames/latest.jpg`를 쓸 수 있다.
- 디스크 write는 실시간 영상 경로에서 불필요한 지연 요인이 될 수 있다.
- 운영 중 디버깅이 필요할 때만 켠다.

## 7. latency 측정 계획

개선 전후 비교를 위해 timestamp를 단계별로 기록한다.

서버에서 추가로 볼 지표:

```text
last_byte_at
last_frame_at
latest_frame_age_ms
decode_fps
publish_fps
inference_fps
inference_last_ms
inference_dropped_frames
inference_result_age_ms
inference_device
gpu_name
gpu_memory_used_mb
current_frame_seq
```

측정 방법:

1. 모델 OFF, H.264 경로로 실행한다.
2. `/api/stream_status`를 1초 간격으로 확인한다.
3. 대시보드에서 시계 또는 손동작으로 체감 latency를 확인한다.
4. 모델 ON 후 preview latency가 증가하는지 확인한다.
5. 모델 ON 상태에서 `inference_result_age_ms`가 대부분 3000ms 이하인지 확인한다.
6. inference가 밀릴 때 backlog 대신 dropped frame이 증가하는지 확인한다.
7. `inference_device`가 `cuda:0`로 표시되는지 확인한다.

성공 기준:

- 모델 OFF에서 `latest_frame_age_ms`가 대부분 500ms 이하
- 모델 ON에서도 preview 영상이 1초 이상 밀리지 않음
- 모델 ON에서 AI 결과 latency가 최대 2~3초 이내
- 운영 추론이 GPU에서 실행됨
- 모델 처리 시간이 길어질 때 frame backlog 대신 drop이 발생

## 8. 우선순위

### 우선순위 A: 바로 효과가 큰 작업

1. 운영 경로를 `/stream/h264`로 고정한다.
2. `/video_feed`를 latest-frame sequence 기반으로 변경한다.
3. JPEG quality와 preview FPS를 설정값으로 분리한다.
4. latency 측정 지표를 `/api/stream_status`에 추가한다.

### 우선순위 B: 모델 ON 대응

1. H.264 decode loop와 inference worker를 분리한다.
2. inference queue를 latest-only 구조로 만든다.
3. `DEVICE=cuda:0` 기준으로 GPU 추론을 강제한다.
4. `STREAM_INFER_EVERY_N` 또는 `INFERENCE_MAX_FPS`로 추론 빈도를 제한한다.
5. 모델 결과는 `/api/latest_result` 또는 WebSocket으로 별도 전달한다.
6. AI 결과가 3초보다 오래되면 dashboard에서 지연 상태로 표시한다.

### 우선순위 C: 장기 개선

1. WebRTC 기반 dashboard stream을 검토한다.
2. detector와 action recognition을 계층적으로 분리한다.
3. 위험 후보가 있을 때만 pose/action 모델을 실행한다.
4. 모델별 평균 처리 시간을 기록해 pipeline 선택 기준을 만든다.
5. ffmpeg GPU decode, TensorRT, ONNX Runtime GPU backend를 검토한다.

## 9. 권장 최종 구조

```text
Raspberry Pi
  rpicam-vid H.264
  -> POST /stream/h264

Server receive/decode
  request.stream()
  -> ffmpeg stdin
  -> ffmpeg stdout raw frame
  -> latest raw frame publish
  -> latest inference slot update

Dashboard video
  GET /video_feed
  -> latest raw MJPEG frame

Inference worker
  latest frame only
  -> GPU FrameProcessor.process()
  -> latest_result
  -> optional annotated frame

Dashboard metadata
  GET /api/latest_result or WS /ws/result
  -> object list / danger / labels
```

이 구조에서는 모델이 느려져도 영상 표시 경로가 막히지 않는다.
대시보드는 최신 원본 영상을 먼저 보여주고, 모델 결과는 GPU worker가 2~3초 이내의 최신 상태로 따라오게 된다.

## 10. 다음 구현 작업 목록

다음 작업에서 수정할 후보 파일:

- `server/app.py`
  - latest-frame seq/condition 추가
  - `/video_feed` generator 개선
  - decode loop와 inference worker 분리
  - GPU device 확인 및 inference device 지표 추가
  - stream status 지표 추가
- `frontend/static/script.js`
  - result polling 또는 WebSocket result 수신 정리
  - 필요 시 detection overlay 갱신
- `frontend/templates/index.html`
  - 필요 시 overlay canvas 또는 metadata 표시 영역 추가
- `README.md`
  - 운영 실행 명령과 latency 튜닝 env 문서화

주의:

- latency 개선 구현 시 SQL schema나 DB 파일은 건드리지 않는다.
- 먼저 모델 OFF H.264 경로를 안정화한 뒤 모델 ON 구조를 분리한다.
- Python JPEG `/frame` 클라이언트는 테스트용으로 유지하되 운영 권장 경로로 문서화하지 않는다.
- 모델 ON 목표는 GPU 사용 기준 최대 2~3초 latency이며, CPU 추론은 운영 목표에서 제외한다.
