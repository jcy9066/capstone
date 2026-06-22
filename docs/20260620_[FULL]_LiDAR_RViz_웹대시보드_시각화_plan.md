# 20260620 [FULL] LiDAR RViz 및 웹 대시보드 시각화 계획

## 1. 목표

RPLIDAR A1M8-R6 기반 mapping 결과를 두 군데에서 확인할 수 있게 한다.

- 로컬/ROS2 확인용: RViz2
- 관제 확인용: 기존 웹 대시보드의 `MAP AREA` 영역

웹 대시보드에서는 `/map` 누적 지도, `/pose` 로봇 위치, `/scan` 실시간 LaserScan overlay를 함께 표시한다.

## 2. ROS2/RViz 작업

- `patrol_navigation` 패키지에 RViz 설정 파일을 추가한다.
- `mapping.launch.py`에 `start_rviz` launch argument를 추가한다.
- 기본 실행에서는 RViz를 자동으로 켜지 않고, 사용자가 로컬 확인이 필요할 때 `start_rviz:=true`로 실행한다.
- RViz display는 `/map`, `/scan`, TF를 기본으로 둔다.
- scan overlay를 웹으로 보내기 위해 `map_bridge`의 `send_scan` 기본값을 켠다.

## 3. 웹 대시보드 작업

수정 대상:

- `frontend/templates/index.html`
- `frontend/static/script.js`
- `frontend/static/style.css`

작업:

- `MAP AREA` placeholder를 canvas 기반 LiDAR map panel로 교체한다.
- `/api/navigation/status`, `/api/navigation/map`, `/api/navigation/pose`, `/api/navigation/scan`을 polling한다.
- OccupancyGrid RLE payload를 decode해서 canvas에 그린다.
- pose를 화살표로 표시한다.
- scan ranges를 현재 pose 기준 point overlay로 표시한다.
- 데이터가 없거나 stale이면 상태 label을 표시한다.

## 4. 검증 계획

- Python 파일 문법 검사
- `colcon list`로 ROS2 패키지 인식 확인
- 프론트엔드 정적 파일에 syntax 수준 문제가 없는지 확인
- 실제 RViz 실행과 LiDAR scan 확인은 ROS2 CLI와 LiDAR 연결 후 수행한다.

## 5. 의존성

새 pip 패키지는 추가하지 않는다.
`requirements.txt` 변경은 필요하지 않다.
RViz 관련 ROS2 의존성은 `package.xml`에 반영한다.
