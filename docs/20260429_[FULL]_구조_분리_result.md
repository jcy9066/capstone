# 구조 분리 작업 결과 보고서

## 작업 요약

관제 센터 대시보드, 영상 수신 및 pose estimation 파이프라인, 향후 SLAM/자율주행 영역을 디렉토리 단위로 분리했다. 코드 로직은 수정하지 않고 파일 위치를 중심으로 정리했다.

## 생성된 디렉토리

- `frontend/`: 관제 센터 대시보드 관련 파일
- `perception/`: 라즈베리파이 영상 수신, 객체 탐지, pose estimation, 행동 인식 관련 파일
- `navigation/`: 향후 SLAM 및 자율주행 코드 배치용 디렉토리
- `docs/`: 작업 계획서와 결과 보고서 저장 디렉토리

## 이동된 파일 및 디렉토리

- `app.py` -> `frontend/app.py`
- `templates/` -> `frontend/templates/`
- `static/` -> `frontend/static/`
- `main.py` -> `perception/main.py`
- `local_cam.py` -> `perception/local_cam.py`
- `core/` -> `perception/core/`
- `models/` -> `perception/models/`
- `stream/` -> `perception/stream/`
- `utils/` -> `perception/utils/`
- `config/` -> `perception/config/`

## 생성된 파일

- `docs/20260429_[FULL]_구조_분리_plan.md`
- `docs/20260429_[FULL]_구조_분리_result.md`
- `navigation/.gitkeep`

## 수정된 문서

- `AGENT.md`
  - 주요 파일 위치를 새 디렉토리 구조에 맞게 갱신했다.
  - 실행 예시를 `frontend/app.py`, `perception/local_cam.py`, `perception/main.py` 기준으로 갱신했다.
- `README.md`
  - 테스트 영상 실행 모드와 RTSP 실행 모드 명령을 `perception/main.py` 기준으로 갱신했다.

## 유지한 항목

- `PROJECT.md`, `README.md`, `.gitignore`, `.env`는 루트에 유지했다.
- `data/`, `weights/`, `output/`은 입력 데이터, 모델 가중치, 분석 산출물 성격이 강하므로 루트에 유지했다.
- 코드 내부 import, 경로 문자열, 실행 로직은 이번 작업에서 변경하지 않았다.

## 검증 결과

- `find` 명령으로 `frontend/`, `perception/`, `navigation/`, `docs/` 구조가 생성된 것을 확인했다.
- `git status --short`로 이전 위치 삭제와 새 위치 추가 상태를 확인했다.
- 코드 실행 테스트는 수행하지 않았다. 이번 작업은 파일 위치 재배치가 목적이며 코드 내용 변경은 최소화했다.
