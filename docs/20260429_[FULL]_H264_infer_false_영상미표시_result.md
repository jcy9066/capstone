# 20260429 [FULL] H.264 infer=false 영상 미표시 디버그 결과

## 1. 작업 요약

`infer=false`에서도 영상이 표시되지 않는 문제를 진단하기 위해 H.264 stream 처리 경로의 계측을 보강했다.

## 2. 수정 파일

```text
server/app.py
```

## 3. 변경 내용

- ffmpeg stdin에 chunk를 쓴 뒤 `flush()`를 호출하도록 수정했다.
- `/api/stream_status`에서 확인할 수 있는 필드를 추가했다.

추가 필드:

```text
last_byte_at
ffmpeg_returncode
```

## 4. 검증

수행:

```bash
python -m py_compile server/app.py
```

결과:

```text
문법 검사 통과
```

## 5. 다음 확인 명령

GPU 서버 재시작:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 21063
```

Pi에서 원본 stream 전송:

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -v -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://10.108.90.21:21063/stream/h264?robot_id=pi-01&infer=false"
```

GPU 서버에서 상태 확인:

```bash
curl http://localhost:21063/api/stream_status
```

## 6. 해석

```text
bytes_received = 0
-> Pi의 POST가 서버에 도달하지 않음

bytes_received > 0, frames_decoded = 0
-> ffmpeg 디코딩 문제

ffmpeg_returncode 값 존재
-> ffmpeg가 종료됨. ffmpeg_stderr_tail 확인

frames_decoded > 0, has_current_frame = true
-> 서버는 frame을 만들고 있으므로 대시보드 표시 경로 확인
```

