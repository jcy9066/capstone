# 20260622 [FULL] ROS 주석 한국어 변환 계획

## 1. 목표

ROS2 mapping 관련 launch/config/setup 파일에 추가된 영어 주석을 한국어로 변환한다.

## 2. 대상 파일

- `navigation/ros/patrol_navigation/launch/mapping.launch.py`
- `navigation/ros/patrol_navigation/launch/lidar.launch.py`
- `navigation/ros/patrol_navigation/config/slam_toolbox.yaml`
- `navigation/ros/patrol_navigation/config/rplidar_a1m8.yaml`
- `navigation/ros/patrol_navigation/setup.py`

## 3. 작업 방식

- 코드 동작과 설정값은 변경하지 않는다.
- 영어 설명 주석만 한국어 설명으로 바꾼다.
- ROS 초보자가 이해하기 쉽도록 용어를 풀어서 작성한다.

## 4. 검증

- Python launch/setup 파일 문법 검사
- 변경 후 주요 주석 확인
