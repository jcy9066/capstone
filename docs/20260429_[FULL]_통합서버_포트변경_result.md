# 20260429 [FULL] 통합 서버 포트 변경 결과 (폐기)

> 폐기됨: 최종 결정은 `21063` 단일 포트 사용이다. 이 문서는 중간 변경 기록으로만 남긴다.

## 1. 작업 요약

통합 GPU 서버와 Control Dashboard의 기본 포트를 변경하는 중간 작업을 수행했다.

`21063` 포트에는 기존 테스트용 FastAPI 서버가 실행 중일 수 있으므로, 대시보드 접속과 Raspberry Pi client 연결은 `21063`를 기준으로 사용한다.

```text
Dashboard: http://10.108.90.21:21063
Frame API: http://10.108.90.21:21063/frame
Status API: http://10.108.90.21:21063/status
Robot WebSocket: ws://10.108.90.21:21063/ws/robot/pi-01
```

## 2. 수정 파일

```text
.env
README.md
perception/config/settings.py
raspberry/pi_client.py
docs/20260429_[FULL]_Push_WebSocket_통합서버_plan.md
docs/20260429_[FULL]_Push_WebSocket_통합서버_result.md
```

## 3. 변경 내용

```env
SERVER_PORT=21063
SERVER_BASE_URL=http://10.108.90.21:21063
```

Raspberry Pi client의 기본 접속 주소도 다음으로 변경했다.

```text
http://10.108.90.21:21063
```

README의 `uvicorn`, `curl`, API 테스트 예시도 모두 `21063` 기준으로 갱신했다.

## 4. 실행 방법

GPU 서버:

```bash
cd ~/capstone
uvicorn server.app:app --host 0.0.0.0 --port 21063
```

대시보드:

```text
http://10.108.90.21:21063
```

Raspberry Pi:

```bash
cd ~/capstone
python raspberry/pi_client.py
```

## 5. 검증

수행한 검증:

```bash
python -m py_compile capstone/server/app.py capstone/perception/config/settings.py capstone/raspberry/pi_client.py
```

결과:

```text
문법 검사 통과
```

## 6. 참고

`http://10.108.90.21:21063`에서 `{"detail":"Not Found"}`가 보이면, 해당 포트에는 대시보드 통합 서버가 아니라 이전 테스트용 FastAPI 앱이 실행 중일 가능성이 높다.

통합 서버는 다음 주소로 확인한다.

```text
http://10.108.90.21:21063
```
