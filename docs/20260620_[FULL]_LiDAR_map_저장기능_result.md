# 20260620 [FULL] LiDAR map 저장 기능 결과

## 1. 작업 결과

FastAPI 서버가 현재 수신 중인 LiDAR SLAM map을 파일로 저장할 수 있게 했다.

저장 위치:

```text
navigation/maps/
```

저장 파일:

```text
<map_name>.pgm
<map_name>.yaml
<map_name>.meta.json
<map_name>.raw.json
```

## 2. map 운용 방식

로봇이 여러 map을 저장하더라도 매 scan마다 모든 map과 비교하는 구조로 운영하지 않는다.

권장 흐름:

1. mapping mode에서 구역별 map을 저장한다.
2. 운영 시 현재 구역에 맞는 active map 하나를 선택한다.
3. localization mode에서 active map 기준으로 현재 pose를 추정한다.
4. 여러 map 후보 비교는 초기 위치를 모를 때나 구역 전환이 필요할 때 제한적으로 수행한다.

이번 작업은 1번에 해당하는 map library 저장 기능이다.

## 3. 서버 API

수정 파일:

```text
server/app.py
```

추가 API:

| Method | Path | 역할 |
| --- | --- | --- |
| POST | `/api/navigation/maps/save` | 최신 navigation map 저장 |
| GET | `/api/navigation/maps` | 저장된 map 목록 조회 |

저장 API 요청 예시:

```json
{
  "map_name": "patrol_area_1"
}
```

응답은 저장된 map 이름과 파일 경로 metadata를 반환한다.

## 4. 웹 대시보드

수정 파일:

```text
frontend/templates/index.html
frontend/static/script.js
frontend/static/style.css
```

변경 내용:

- `MAP AREA` overlay에 `SAVE` 버튼 추가
- 현재 map이 있을 때 map 이름을 입력받아 저장 API 호출
- 저장 성공/실패 alert 표시

## 5. 저장 포맷

- `.pgm`: ROS map server 호환 occupancy image
- `.yaml`: ROS map metadata
- `.meta.json`: 서버/대시보드용 metadata
- `.raw.json`: 서버가 받은 원본 map payload 보존

PGM 변환 기준:

- unknown: 205
- free: 254
- occupied: 0

## 6. 의존성

새 pip 패키지는 추가하지 않았다.
`requirements.txt` 변경 없음.

## 7. 검증 결과

수행한 검증:

```bash
python3 -m py_compile   capstone/server/app.py   capstone/navigation/ros/patrol_navigation/patrol_navigation/map_bridge.py   capstone/navigation/ros/patrol_navigation/launch/lidar.launch.py   capstone/navigation/ros/patrol_navigation/launch/mapping.launch.py   capstone/navigation/ros/patrol_navigation/setup.py
```

결과: 통과.

```bash
node --check capstone/frontend/static/script.js
```

결과: 통과.

제한 사항:

- 현재 셸의 Python에는 `cv2`가 없어 `server.app` runtime import 기반 저장 테스트는 수행하지 못했다.
- 실제 저장 버튼 동작은 FastAPI 서버 실행 환경과 LiDAR map 수신 후 확인해야 한다.

## 8. 다음 작업

1. LiDAR 연결 후 `/api/navigation/map`에 map이 들어오는지 확인
2. 웹 `MAP AREA`에서 `SAVE` 버튼으로 map 저장
3. `navigation/maps/`에 `.pgm`, `.yaml`, `.meta.json`, `.raw.json` 생성 확인
4. 저장 map을 localization mode에서 사용할 active map으로 선택하는 기능 추가
