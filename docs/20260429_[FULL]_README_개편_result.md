# 20260429 [FULL] README 개편 결과

## 1. 작업 요약

루트 `README.md`를 프로젝트 온보딩 문서로 개편했다. 사용자 요청에는 `READMD.md`라고 적혀 있었지만, 계획서에서 확인한 대로 저장소의 실제 대상 파일인 `README.md`를 수정했다.

## 2. 수정 파일

- `README.md`

## 3. 주요 변경 사항

- 프로젝트 소개를 추가했다.
- 현재 구현된 범위와 진행 중인 범위를 분리했다.
- 현재 디렉토리 구조를 설명했다.
- `.env` 주요 키를 실제 값 없이 placeholder 중심으로 정리했다.
- 기본 설치 패키지와 모델 추론 환경 의존성을 구분했다.
- FastAPI 통합 서버 실행 방법을 권장 실행 경로로 명시했다.
- Raspberry Pi 클라이언트 실행 방법과 동작 흐름을 추가했다.
- 테스트 영상 분석 명령과 결과 저장 위치를 정리했다.
- `perception/pipeline_factory.py` 기준 1~9번 모델 파이프라인 표를 추가했다.
- `/frame`, `/status`, `/api/robots/{robot_id}/command`, `/api/latest_result`, `/api/pipelines` 등 API 테스트 예시를 추가했다.
- 대시보드 기능과 현재 미연동 상태를 정리했다.
- RTSP 관련 구현 상태와 별도 계획 문서 위치를 명시했다.
- `PROJECT.md`, `AGENT.md`, `ERD.png`, `Activity_Diagram.png`, `docs/` 문서로 이어지는 참고 정보를 추가했다.

## 4. 검증 결과

- README 명령어 경로가 현재 파일 위치와 일치하는지 확인했다.
- 실제 `.env` 비밀값은 README에 기록하지 않았다.
- API endpoint 목록을 `server/app.py`와 대조했다.
- 모델 파이프라인 번호를 `perception/pipeline_factory.py`와 대조했다.
- 이번 작업은 문서 수정이므로 서버 실행 테스트나 모델 실행 테스트는 수행하지 않았다.

## 5. 남은 참고 사항

- `frontend/app.py`는 기존 Flask 서버로 남아 있으나 README에서는 현재 권장 경로인 `server/app.py` FastAPI 통합 서버를 중심으로 안내했다.
- `raspberry/controllers/`는 실제 하드웨어 제어 전 단계의 stub임을 README에 명시했다.
- `perception/main.py --source rtsp` 실시간 입력은 계획 문서 기준으로 별도 확장 대상임을 README에 명시했다.

