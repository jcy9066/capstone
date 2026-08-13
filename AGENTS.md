# AGENTS.md

이 문서는 `dabom_capstone` 저장소에서 Codex가 따라야 하는 프로젝트 공통 규칙을 정의한다.

## 1. 프로젝트 개요

본 프로젝트는 Raspberry Pi 4 기반 자율주행 방범 로봇 시스템이다.

주요 구성은 다음과 같다.

- Raspberry Pi: 센서 수집, 카메라 전송, Pico W 통신
- Pico W: 모터, 엔코더, 스피커 및 MOSFET 제어
- GPU Server: AI 추론, FastAPI 서버, 웹 관제
- ROS 2: LiDAR, SLAM, localization, Nav2 및 odometry
- Web Dashboard: 영상, 로봇 상태, 지도 및 주행 제어

## 2. 기준 파일과 디렉터리

현재 구현의 기준은 다음과 같다.

- 통합 서버: `server/app.py`
- 웹 템플릿: `frontend/templates/`
- 웹 정적 파일: `frontend/services/static/`
- ROS 2 패키지: `navigation/ros/patrol_navigation/`
- Raspberry Pi 클라이언트: `raspberry/robot_command_client.py`
- Raspberry Pi 모터 제어: `raspberry/controllers/motor_controller.py`
- Pico W 펌웨어: `raspberry/pico_w_sdk/main.c`
- 테스트: `tests/`
- 대표 지도: `navigation/maps/slam_test_01.*`

문서 내용과 실제 코드가 충돌하면 현재 실행 경로와 소스 코드를 우선한다.

과거 Flask 서버, MicroPython 펌웨어, 백업 파일은 현재 기준 구현으로 간주하지 않는다.

## 3. 기본 작업 원칙

Codex의 Primary/Main Agent는 전체 작업의 orchestrator이며, 애플리케이션 소스와 설정 변경의 최종 책임을 가진다.

코드 또는 설정 변경 작업에서는 다음 순서를 따른다.

1. 사용자 요청 범위를 확인한다.
2. `implement-feature` Skill을 적용한다.
3. 실제 파일을 수정하기 전에 `code_explorer` Sub-Agent에게 entry point, import 관계, 호출 경로, 영향 범위, 중복 및 미사용 코드 조사를 반드시 위임한다.
4. `code_explorer` 결과를 받은 뒤 영향 범위와 변경 대상 파일을 확정한다.
5. Primary/Main Agent가 요청에 필요한 코드만 수정한다.
6. 변경 영역에 해당하는 validation Skill을 모두 수행한다.
7. 각 validation Skill에서 지정한 Sub-Agent 검토를 수행한다. 서로 독립적인 검토는 `.codex/config.toml`의 동시 실행 제한 안에서 병렬로 실행할 수 있다.
8. 모든 영역별 검증 결과를 받은 뒤 `review-change`를 수행한다.
9. `review-change`에서 `test_reviewer` Sub-Agent의 최종 regression 검토를 수행한다.
10. 모든 필수 검증과 Sub-Agent 결과를 종합하여 변경 파일, 검증 결과 및 미검증 항목을 보고한다.

설명 전용 요청이나 저장소 읽기 전용 분석처럼 코드 또는 설정을 변경하지 않는 작업에는 위 구현 workflow를 강제하지 않는다.

다음 원칙을 항상 적용한다.

- 사용자가 요청하지 않은 기능을 임의로 추가하지 않는다.
- 요청 범위 밖 파일을 불필요하게 수정하지 않는다.
- 기존 구조와 이름을 임의로 변경하지 않는다.
- 중복 구현을 만들기 전에 기존 구현과 참조 관계를 검색한다.
- 코드가 실제로 사용되는지 확인하지 않고 파일을 제거하지 않는다.
- 하드웨어가 없는 환경에서 실제 하드웨어 동작을 검증했다고 표현하지 않는다.
- 실패한 검사와 실행하지 못한 검사는 명확히 구분한다.
- 매 작업마다 별도의 plan/result 문서를 생성하지 않는다.
- 대규모 설계 변경이나 사용자의 문서화 요청이 있을 때만 문서를 추가한다.

## 4. Skill 사용 기준

구현된 Skill이 존재하면 변경 영역에 맞는 Skill을 사용한다.

- 일반 기능 구현: `implement-feature`
- FastAPI, 인증, WebSocket, DB: `validate-server`
- 웹 대시보드 및 Browser 검증: `validate-dashboard`
- ROS 2, SLAM, localization, Nav2: `validate-navigation`
- Raspberry Pi, Pico W, UART: `validate-raspberry`
- 전체 변경 검토: `review-change`

여러 영역이 함께 변경되면 관련 Skill을 모두 수행한다. 각 Skill의 Sub-Agent delegation 지시는 필수 workflow로 취급한다.

예:

- `server/app.py` 변경
  - `validate-server`
  - `validate-dashboard`
  - `review-change`

- ROS launch 또는 config 변경
  - `validate-navigation`
  - `review-change`

- Pi 또는 Pico UART protocol 변경
  - `validate-raspberry`
  - `review-change`

## 5. Sub-Agent Orchestration

사용자 prompt에 Sub-Agent 사용이 명시되지 않아도 아래 조건이 충족되면 Primary/Main Agent가 해당 Sub-Agent에게 작업을 반드시 delegate한다.

등록된 Project Sub-Agent 이름은 `.codex/agents/*.toml`의 `name` 값을 기준으로 한다.

- `code_explorer`
  - entry point, import 관계, 영향 범위, 중복 및 미사용 코드 조사
  - 코드 또는 설정 수정 전에 실행
  - `validate-server`가 단독 실행되고 현재 변경 범위를 다룬 최신 탐색 결과가 없을 때 서버 호출 관계 조사에도 사용

- `dashboard_reviewer`
  - Playwright MCP를 이용한 실제 웹 대시보드 검사
  - `validate-dashboard`가 필요한 모든 변경에서 실행

- `ros_reviewer`
  - ROS 2, SLAM, AMCL, Nav2, TF 및 topic 검토
  - `validate-navigation`이 필요한 모든 변경에서 실행

- `hardware_reviewer`
  - Raspberry Pi, Pico W, UART, encoder 및 failsafe 검토
  - `validate-raspberry`가 필요한 모든 변경에서 실행

- `test_reviewer`
  - 최종 diff, regression 및 테스트 누락 검토
  - 모든 영역별 validation이 끝난 뒤 `review-change`에서 실행

### Orchestration 규칙

1. Primary/Main Agent가 전체 orchestration을 소유한다.
2. Project Sub-Agent는 부모 Agent가 명시적으로 추가 delegation을 요청한 경우를 제외하고 다른 Project Sub-Agent를 재귀적으로 생성하지 않는다.
3. 현재 thread가 해당 작업의 지정 Sub-Agent인 경우 자기 자신과 같은 역할의 Sub-Agent를 다시 생성하지 않고 할당된 검토를 직접 수행한다.
4. 동일한 현재 working-tree diff와 동일한 검토 범위를 이미 다루는 활성 또는 완료된 Sub-Agent 결과가 있으면 중복 생성하지 않고 그 결과를 재사용할 수 있다.
5. 구현 전 `code_explorer` 결과처럼 다음 단계의 입력이 되는 작업은 결과를 기다린 뒤 진행한다.
6. 구현 후 `dashboard_reviewer`, `ros_reviewer`, `hardware_reviewer`처럼 서로 독립적인 읽기/검토 작업은 동시 실행 제한 안에서 병렬로 실행할 수 있다.
7. `test_reviewer`는 영역별 validation과 관련 reviewer 결과가 모두 준비된 뒤 실행한다.
8. Primary/Main Agent만 애플리케이션 소스와 설정을 수정한다. Sub-Agent는 기본적으로 검토 결과를 반환하며, 테스트/브라우저 검증 과정에서 허용된 임시 산출물 외에는 소스 파일을 수정하지 않는다.
9. Sub-Agent 결과는 근거 자료이며 최종 판단과 사용자 보고 책임은 Primary/Main Agent에 있다.
10. 필수 Sub-Agent를 실행하지 못한 경우 성공으로 간주하지 않고 실행하지 못한 이유를 최종 보고에 명시한다.

## 6. 웹 대시보드 검증

웹 관련 파일이 변경되면 `validate-dashboard` Skill을 사용하고 `dashboard_reviewer`에게 실제 Browser 검증을 위임한다.

검사 대상은 다음과 같다.

- 로그인 및 로그아웃
- session과 CSRF
- 페이지 redirect
- JavaScript console 오류
- network request 실패
- CSS 및 JavaScript asset 404
- modal과 sidebar
- 카메라 online/offline
- 로봇 WebSocket 연결 상태
- LiDAR online/offline
- 저장 지도 목록과 선택 상태
- navigation mode 표시
- 자동/수동 순찰 UI 상태

기본 Browser 검증에서는 다음 동작을 실행하지 않는다.

- 실제 로봇 이동
- D-Pad 또는 키보드 주행
- 실제 신고 전송
- 실제 경고 방송
- ROS process 시작 또는 종료
- 지도 저장 또는 삭제
- 사용자나 DB 데이터 삭제

## 7. ROS 2 및 Navigation 규칙

ROS 관련 변경에서는 `validate-navigation` Skill을 사용하고 `ros_reviewer`에게 ROS 구조와 interface 검토를 위임한다.

다음 사항을 확인한다.

- ROS 2 Humble 기준을 유지한다.
- `setup.py`, launch, config 및 executable 등록 관계를 확인한다.
- build 결과인 `build/`, `install/`, `log/`는 수정하거나 커밋하지 않는다.
- topic과 frame 이름을 임의로 변경하지 않는다.
- 기본 TF 구조는 다음 연결을 유지한다.

```text
map → odom → base_link → laser
```

* mapping, localization, localization + Nav2 모드를 구분한다.
* dry-run 명령과 실제 motor output을 구분한다.
* 실제 `/cmd_vel` publish는 사용자가 명시적으로 요청하지 않으면 실행하지 않는다.
* 하드웨어가 없는 환경에서는 build와 정적 검증까지만 수행한다.

## 8. Raspberry Pi 및 Pico W 규칙

Pi와 Pico W 관련 변경에서는 `validate-raspberry` Skill을 사용하고 `hardware_reviewer`에게 protocol과 safety 검토를 위임한다.

Pi와 Pico W 관련 변경에서는 양쪽 UART protocol을 함께 확인한다.

주요 protocol은 다음과 같다.

* `PING`
* `STOP`
* `MOVE`
* `DRIVE`
* `ENC_RESET`
* `ENC_STREAM`
* `EVENT,ENC`

다음 사항을 확인한다.

* UART baud rate 일치
* 명령 field 순서
* speed 범위
* encoder field 순서
* timeout
* failsafe stop
* GPIO pin 정의
* Raspberry Pi 송신 형식과 Pico W parser 호환

사용자의 명시적 요청 없이 다음 작업을 실행하지 않는다.

* 실제 serial 장치에 이동 명령 전송
* GPIO 출력 변경
* Pico W firmware flash
* OpenOCD program
* 실제 모터 구동
* 스피커 또는 MOSFET 출력

## 9. Git 정책

Codex는 Git repository 상태나 원격 저장소 버전에 영향을 주는 작업을 실행하지 않는다.

다음 명령은 실행하지 않는다.

* `git add`
* `git commit`
* `git push`
* `git pull`
* `git fetch`
* `git merge`
* `git rebase`
* `git cherry-pick`
* `git revert`
* `git reset`
* `git restore`
* `git checkout`
* `git switch`
* `git stash`
* `git tag`
* `git clean`
* branch 생성 또는 삭제

다음과 같은 읽기 전용 명령은 사용할 수 있다.

* `git status`
* `git diff`
* `git log`
* `git show`
* `git grep`
* `git ls-files`
* `git ls-tree`
* `git rev-parse`
* `git blame`
* `git remote -v`
* `git branch --show-current`
* `git branch --list`

branch 생성, add, commit, push, pull 및 merge는 사용자가 직접 수행한다.

## 10. GitHub MCP 정책

GitHub MCP는 원격 저장소 조회와 협업 정보 확인에 사용한다.

허용되는 주요 작업:

* 원격 branch 및 파일 조회
* repository tree 조회
* 코드 검색
* commit과 diff 조회
* PR, Issue, review 및 comment 조회
* GitHub Actions 상태와 log 조회

사용자 승인 후 가능한 작업:

* Issue 생성 또는 수정
* Issue comment 작성
* PR 생성
* PR comment 또는 review 작성
* label 및 assignee 변경

다음 기능은 사용하지 않는다.

* 원격 파일 생성, 수정 또는 삭제
* commit 생성
* branch 생성 또는 삭제
* PR merge
* tag 또는 release 생성
* workflow 파일 수정
* repository 설정 변경

## 11. 보안 및 생성물 관리

다음 파일과 데이터는 Git에 포함하지 않는다.

* `.env`
* password, token, secret
* 모델 weight
* ROS build 결과
* Pico SDK build 결과
* runtime log
* 수신 frame
* 임시 출력물
* 백업 파일
* 자동 생성 지도

비밀값이 코드나 출력에 포함되면 그대로 노출하지 않고 마스킹한다.

기존 Git 추적 파일을 제거하거나 `.gitignore`를 수정하는 작업도 사용자의 명시적 요청 범위 안에서만 수행한다.

## 12. 검증 결과 보고

작업 완료 시 다음 형식으로 보고한다.

* 변경한 파일
* 핵심 변경 내용
* 실행한 Skill
* 실행한 Sub-Agent와 맡긴 역할
* 실행한 검사
* 검사 결과
* 실행하지 못한 검사 또는 Sub-Agent
* 실제 하드웨어에서 추가로 확인할 항목
* 발견했지만 요청 범위상 수정하지 않은 문제

테스트 성공, 정적 검증 성공, Browser 검증 성공, 실제 하드웨어 검증 성공을 서로 구분해서 작성한다.
