# LiDAR 실시간 상태 UI 구현 계획

## 작업 목적

웹 대시보드의 `MAP AREA`에서 LiDAR 데이터가 실제로 들어오고 있는지 즉시 확인할 수 있도록 다음 3가지 표시를 추가한다.

- LiDAR Live Badge: 현재 LiDAR 수신 상태를 `LIVE`, `STALE`, `OFFLINE`으로 표시
- Scan Pulse Ring: 새 `/scan` 데이터가 들어올 때마다 로봇 위치 주변에 짧은 펄스 링 표시
- Offline/Stale Overlay: 데이터가 없거나 오래된 경우 미니맵 위에 상태 오버레이 표시

## 변경 대상

- `frontend/templates/index.html`
  - 미니맵 내부에 LiDAR 상태 배지와 stale/offline 오버레이 요소 추가
  - 정적 파일 캐시 버전 갱신

- `frontend/static/script.js`
  - scan 수신 시각과 scan 주기를 추적하는 상태 추가
  - live/stale/offline 판정 함수 추가
  - scan 갱신 시 pulse animation 트리거
  - 상태 배지, meta text, overlay class/text 업데이트

- `frontend/static/style.css`
  - LiDAR live badge 스타일 추가
  - stale/offline overlay 스타일 추가
  - pulse 상태에서도 기존 map/scan/robot 표시가 흐트러지지 않도록 z-index 정리

## 판정 기준

- `LIVE`: 서버 상태가 `mapping` 또는 `scan_only`이고 마지막 갱신 시간이 약 3초 이내
- `STALE`: 최근 데이터는 있으나 마지막 갱신 시간이 3초를 초과
- `OFFLINE`: map/scan/pose 데이터가 없거나 서버 상태가 offline

## 검증

- `node --check frontend/static/script.js`로 JS 문법 확인
- 브라우저에서 MAP AREA에 다음 상태가 표시되는지 확인
  - LiDAR 수신 중: `LIVE` badge와 scan pulse
  - LiDAR 중단 후: `STALE` overlay
  - 데이터 없음: `OFFLINE` overlay
