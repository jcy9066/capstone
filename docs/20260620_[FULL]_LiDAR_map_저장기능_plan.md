# 20260620 [FULL] LiDAR map 저장 기능 계획

## 1. 목표

ROS2 `slam_toolbox`가 만든 최신 `/map` 데이터를 FastAPI 서버가 저장할 수 있게 한다.

저장 대상:

- `navigation/maps/<map_name>.pgm`
- `navigation/maps/<map_name>.yaml`
- `navigation/maps/<map_name>.meta.json`
- `navigation/maps/<map_name>.raw.json`

## 2. map 운용 방식 정리

로봇이 n개의 map을 저장한다고 해서 매 scan마다 모든 map과 비교하는 방식으로 운영하지 않는다.

일반적인 흐름:

1. mapping mode에서 구역별 map을 저장한다.
2. 운영 시 현재 구역에 맞는 active map 하나를 선택한다.
3. localization mode에서 active map 위의 현재 pose를 추정한다.
4. 여러 map 비교는 초기 위치를 모를 때나 구역 전환이 필요할 때 제한적으로 수행한다.

이번 작업은 1번, 즉 map 저장 library를 만드는 단계다.

## 3. 서버 작업

수정 대상:

- `server/app.py`

추가 기능:

- 최신 navigation map 저장 endpoint
- 저장된 map 목록 조회 endpoint
- RLE map decode
- ROS map server 호환 PGM/YAML 저장
- raw payload와 metadata 저장

추가 API:

| Method | Path | 역할 |
| --- | --- | --- |
| POST | `/api/navigation/maps/save` | 최신 map 저장 |
| GET | `/api/navigation/maps` | 저장된 map 목록 조회 |

## 4. 웹 대시보드 작업

수정 대상:

- `frontend/templates/index.html`
- `frontend/static/script.js`
- `frontend/static/style.css`

작업:

- `MAP AREA` overlay에 map 저장 버튼 추가
- 버튼 클릭 시 map 이름 입력
- `/api/navigation/maps/save` 호출
- 저장 성공/실패 피드백 표시

## 5. 의존성

새 pip 패키지는 추가하지 않는다.
JSON, PGM, YAML 문자열 저장은 Python 표준 라이브러리만 사용한다.
따라서 `requirements.txt` 변경은 필요하지 않다.

## 6. 검증 계획

- Python 문법 검사
- JS 구문 검사
- dummy map payload 저장 endpoint 수동 테스트
- `requirements.txt` 변경 없음 확인
