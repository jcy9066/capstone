# LiDAR 실시간 상태 UI 구현 결과

## 완료 내용

웹 대시보드의 `MAP AREA`에 LiDAR 수신 상태를 바로 확인할 수 있는 1차 UI를 추가했다.

- LiDAR Live Badge
  - 미니맵 좌상단에 `LiDAR LIVE`, `STALE`, `OFFLINE` 상태 표시
  - live 상태에서는 점멸 표시로 scan 수신 중임을 표현

- Scan Pulse Ring
  - `/api/navigation/scan`에서 새로운 scan 데이터가 감지될 때마다 로봇 위치 주변에 원형 pulse 표시
  - pulse는 캔버스 위에 직접 그리며 약 0.85초 동안 확산 후 사라짐

- Offline/Stale Overlay
  - scan/map/pose 데이터가 없으면 `LiDAR OFFLINE` 오버레이 표시
  - 마지막 navigation 갱신 시간이 3초를 넘으면 `LiDAR STALE` 오버레이 표시
  - 8초를 넘거나 서버 상태가 offline이면 offline 상태로 표시

## 수정 파일

- `frontend/templates/index.html`
  - 미니맵 내부에 `lidar-live-badge`, `lidar-stale-overlay` 요소 추가
  - CSS/JS cache busting 버전을 `20260622-lidar-live`로 변경

- `frontend/static/script.js`
  - scan 갱신 key 추적과 수신 간격 계산 추가
  - live/stale/offline 판정 함수 추가
  - scan pulse ring 렌더링 추가
  - badge/meta/overlay 상태 업데이트 로직 추가

- `frontend/static/style.css`
  - LiDAR live badge 스타일 추가
  - stale/offline overlay 스타일 추가
  - 확장 미니맵 상태에서도 텍스트 크기와 위치가 유지되도록 스타일 추가

- `docs/20260622_[Front]_LiDAR_실시간상태_UI_plan.md`
  - 작업 전 계획 문서 추가

## 검증

```bash
node --check capstone/frontend/static/script.js
```

결과: JS 문법 검사 통과.

## 동작 기준

- `LIVE`: map/scan/pose 중 하나 이상의 데이터가 있고 마지막 갱신 시간이 3초 이내
- `STALE`: 데이터는 있으나 마지막 갱신 시간이 3초 초과
- `OFFLINE`: 데이터가 없거나 서버 상태가 offline이거나 마지막 갱신 시간이 8초 초과

주의: 표시되는 `RX Hz`는 실제 RPLIDAR 회전 주파수가 아니라 웹 대시보드가 새 scan payload를 관측한 수신 주기다.
