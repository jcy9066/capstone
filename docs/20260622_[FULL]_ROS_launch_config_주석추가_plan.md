# 20260622 [FULL] ROS launch/config 주석 추가 계획

## 1. 목표

RPLIDAR mapping 구성을 처음 보는 사람이 이해할 수 있도록 ROS2 관련 launch/config 파일에 설명 주석을 추가한다.

## 2. 대상 파일

- `navigation/ros/patrol_navigation/launch/mapping.launch.py`
- `navigation/ros/patrol_navigation/launch/lidar.launch.py`
- `navigation/ros/patrol_navigation/config/slam_toolbox.yaml`
- `navigation/ros/patrol_navigation/config/rplidar_a1m8.yaml`
- `navigation/ros/patrol_navigation/setup.py`

## 3. 주석 방향

- 각 node가 왜 필요한지 설명한다.
- launch argument가 실제 실행 명령에서 어떻게 바뀌는지 설명한다.
- `slam_toolbox` lifecycle configure/activate와 `map_bridge` 지연 실행 이유를 명시한다.
- 설정값은 바꾸지 않고 설명 주석만 추가한다.

## 4. 검증

- Python launch/setup 파일 문법 검사
- YAML 파일은 설정값 변경 없이 주석만 추가했는지 확인
