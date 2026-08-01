# 20260429 [FULL] H.264 infer=false 영상 미표시 디버그 계획

## 1. 문제

Raspberry Pi에서 다음 명령을 실행했지만 대시보드에 영상이 표시되지 않았다.

```bash
rpicam-vid -t 0 --nopreview --codec h264 --inline --width 640 --height 480 --framerate 15 -o - | \
curl --http1.1 -v -N -X POST -T - \
  -H "Content-Type: video/H264" \
  -H "Transfer-Encoding: chunked" \
  "http://10.108.90.21:21063/stream/h264?robot_id=pi-01&infer=false"
```

`infer=false`이므로 모델 추론 문제는 제외하고, H.264 수신/디코딩/프레임 publish 경로를 우선 확인한다.

## 2. 가능 원인

```text
1. /stream/h264 요청은 열렸지만 bytes가 서버에 기록되지 않음
2. ffmpeg stdin에 쓰인 데이터가 flush되지 않음
3. ffmpeg가 실행 직후 종료됨
4. ffmpeg는 bytes를 받지만 raw frame을 출력하지 못함
5. current_frame은 갱신됐지만 /video_feed 표시가 갱신되지 않음
```

## 3. 수정 방향

- H.264 chunk를 ffmpeg stdin에 쓴 뒤 flush한다.
- ffmpeg process가 종료됐는지 stream_status에 기록한다.
- 마지막 수신 시각과 ffmpeg return code를 기록한다.

## 4. 확인 기준

```text
bytes_received 증가
  -> Pi에서 서버까지 stream 도달

frames_decoded 증가
  -> ffmpeg 디코딩 성공

has_current_frame true
  -> 대시보드가 읽을 frame 존재

ffmpeg_returncode 존재
  -> ffmpeg가 종료됨
```

