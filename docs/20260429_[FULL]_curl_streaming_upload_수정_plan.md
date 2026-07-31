# 20260429 [FULL] curl streaming upload 수정 계획

## 1. 문제

Raspberry Pi에서 다음 형태의 명령을 실행하면 `curl` 프로세스는 계속 떠 있지만 GPU 서버의 `/api/stream_status`는 `bytes_received=0`으로 남는다.

```bash
rpicam-vid ... -o - | curl --data-binary @- ...
```

## 2. 원인

`--data-binary @-`는 stdin 전체를 POST body로 다루는 옵션이다. 입력이 끝나는 일반 파일/짧은 스트림에는 적합하지만, `rpicam-vid -t 0`처럼 끝나지 않는 실시간 스트림에서는 HTTP 요청 시작이 지연되거나 body 전송이 기대처럼 streaming upload로 동작하지 않을 수 있다.

따라서 서버 입장에서는 `/stream/h264` 요청이 아직 도착하지 않고, `bytes_received=0`이 유지된다.

## 3. 해결 방향

`curl`을 streaming upload 모드로 사용한다.

```bash
curl -T - -X POST ...
```

또는 명시적으로 chunked transfer를 사용한다.

```bash
curl --http1.1 -T - -X POST -H "Transfer-Encoding: chunked" ...
```

서버도 `POST /stream/h264`와 `PUT /stream/h264`를 모두 허용해 테스트 편의성을 높인다.

## 4. 수정 대상

```text
server/app.py
README.md
docs/*
```

