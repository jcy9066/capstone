# AGENTS.md

`dabom_capstone`에서 Codex가 따라야 하는 프로젝트 공통 규칙이다.

## 1. 기준 구조

- Server: `server/app.py`
- Frontend: `frontend/templates/`, `frontend/services/static/`
- ROS 2: `navigation/ros/patrol_navigation/`
- Raspberry Pi: `raspberry/robot_command_client.py`
- Motor control: `raspberry/controllers/motor_controller.py`
- Pico W: `raspberry/pico_w_sdk/main.c`
- Tests: `tests/`

문서와 코드가 충돌하면 현재 실행 경로와 실제 참조 관계를 우선한다.
과거 Flask/MicroPython/backup 구현은 현재 기준으로 간주하지 않는다.

## 2. 구현 Workflow

코드 또는 설정 변경 시 Primary/Main Agent는 다음 순서를 지킨다.

1. 요청 범위를 확정한다.
2. `implement-feature`를 적용한다.
3. 수정 전에 `code_explorer`에게 현재 범위의 실행 경로와 영향 파일만 조사시킨다.
4. 조사 결과를 받은 뒤 필요한 파일만 수정한다.
5. 변경 영역에 맞는 validation Skill을 실행한다.
6. 필요한 reviewer를 병렬 실행하되 같은 diff/범위의 결과는 재사용한다.
7. 모든 영역 검증 후 `review-change`와 `test_reviewer`를 수행한다.
8. 필수 검증이 PASS이면 해당 작업 파일만 `git add`하고 새 commit을 만든다.
9. 여러 독립 작업은 작업별로 구현 → 검증 → commit한다.
10. 변경/검증/commit/미검증 항목만 간결하게 보고한다.

Validation routing:

- `server/` → `validate-server`
- `frontend/` → `validate-dashboard`
- `server/app.py` → `validate-server` + `validate-dashboard`
- `navigation/` → `validate-navigation`
- `raspberry/` → `validate-raspberry`
- source/config 변경 → `review-change`

## 3. 범위 및 안전

- 요청하지 않은 기능, refactor, rename, 문서를 임의로 추가하지 않는다.
- 기존 구현을 검색한 뒤 수정하고 중복 구현을 만들지 않는다.
- 파일 제거 전 실제 참조를 확인한다.
- 실제 하드웨어가 없으면 static/mock/build 결과와 실환경 결과를 구분한다.
- 사용자의 명시적 요청 없이 실제 motor, GPIO, serial movement, firmware flash,
  `/cmd_vel`, Telegram 전송, 경고 방송, 지도/사용자/운영 DB 삭제를 실행하지 않는다.
- `.env`, password, token, secret, model weight, build/log/runtime 산출물을 commit하지 않는다.

## 4. Token / Context 절약 규칙

항상 필요한 정보만 읽고 반환한다.

- 전체 repository/file/log dump보다 `rg`, 경로 제한 검색, 부분 읽기를 우선한다.
- 동일 파일과 동일 검증 결과를 불필요하게 다시 읽거나 반복하지 않는다.
- 기본 Git 확인은 `status --short`, `diff --stat`, 필요한 파일의 targeted diff를 우선한다.
- 테스트는 관련 test부터 `-q`로 실행하고, 전체 suite는 최종 회귀 확인이 필요할 때만 실행한다.
- 성공 로그 전체를 반환하지 않는다. 실패한 명령은 오류 핵심과 필요한 주변 문맥만 반환한다.
- Sub-Agent 결과는 최대 15줄로 제한한다.
- Sub-Agent는 원본 log, 전체 diff, 전체 source를 부모에게 복사하지 않는다.
- 결과는 `PASS/WARN/FAIL`, 근거 파일/symbol, blocking issue, skipped 항목만 전달한다.
- 이미 같은 diff와 범위를 검토한 Sub-Agent 결과가 있으면 재사용한다.

## 5. RTK 사용

RTK(Rust Token Killer)가 PATH에 있으면 shell 출력이 큰 지원 명령에 우선 사용한다.

권장:

```text
rtk git status
rtk git log -n 10
rtk git diff
PYTHONPATH="$PWD" rtk pytest -q
rtk grep "pattern" path
rtk find "pattern" path
rtk read path
```

규칙:

- RTK는 shell 출력 압축용이며 Git 권한 정책을 변경하지 않는다.
- `rtk git add`와 `rtk git commit`은 아래 Git 정책 범위에서만 허용한다.
- `rtk git push/pull/fetch/merge/...`도 동일하게 금지한다.
- Windows + Git Bash에서 Python test는 project root import 보장을 위해 `PYTHONPATH="$PWD"`를 붙인다.
- RTK pytest가 실패하면 동일 범위에서 `PYTHONPATH="$PWD" python -m pytest -q`로 한 번만 fallback한다.
- RTK가 없거나 해당 명령을 지원하지 않거나 한 번 실패하면 raw compact command로 한 번만 fallback한다.
- pathspec 등 RTK filter가 잘못 해석되는 명령은 raw targeted command를 사용한다.
- Codex가 `rtk init`, 설치, 업데이트를 자동 실행하지 않는다.
- 절감 확인이 필요할 때만 `rtk gain` 또는 `rtk gain --history`를 실행한다.

## 6. Sub-Agent

- `code_explorer`: 수정 전 실행 경로/영향 범위 조사
- `dashboard_reviewer`: Playwright browser 검증
- `ros_reviewer`: ROS/SLAM/AMCL/Nav2/TF 검토
- `hardware_reviewer`: Pi/Pico/UART/failsafe 검토
- `test_reviewer`: 최종 diff/regression/test gap 검토

Sub-Agent는 기본적으로 read-only reviewer다. 애플리케이션 source/config는 Primary/Main
Agent만 수정한다. 현재 thread가 해당 reviewer이면 같은 reviewer를 다시 생성하지 않는다.

## 7. Git 정책

허용되는 상태 변경:

- `git add`
- 새 `git commit`

조건:

- 현재 작업에 속하는 파일만 stage한다.
- validation과 `review-change`가 PASS인 작업만 commit한다.
- `git commit --amend`는 금지한다.
- commit message는 한 줄 `type: Summary`, 50자 이하, 끝에 `.` 없음.
- 허용 type:
  `feat`, `fix`, `docs`, `style`, `design`, `test`, `refactor`, `build`,
  `ci`, `perf`, `chore`, `rename`, `remove`

예:

```text
feat: Add dashboard state synchronization
fix: Resolve dashboard asset versioning
```

금지:

- `push`, `pull`, `fetch`, `merge`, `rebase`, `cherry-pick`, `revert`
- `reset`, `restore`, `checkout`, `switch`, `stash`, `tag`, `clean`
- `am`, `apply`, `bisect`, `clone`, `init`, `mv`, `rm`, `worktree`
- branch 생성/삭제
- 기존 history rewrite

읽기 전용 Git 명령은 허용한다.

## 8. GitHub MCP

GitHub MCP는 repository 조회를 기본 read-only로 사용한다.

허용:

- branch/file/tree/code/commit/diff/PR/Issue/Actions 조회
- 사용자 승인 후 Issue/PR/comment/review/label/assignee 협업 작업

금지:

- 원격 file 생성/수정/삭제
- 원격 commit/ref/branch 생성 또는 변경
- PR merge, tag/release, workflow/repository 설정 변경

로컬 `git add`/`git commit`은 GitHub MCP가 아니라 로컬 Git CLI 정책을 따른다.

## 9. 결과 보고

최종 보고는 가능하면 20줄 이내로 유지하고 다음만 포함한다.

- 변경 파일/핵심 변경
- 실행한 Skill/Sub-Agent
- PASS/FAIL/WARN/SKIP
- 생성 commit hash/message
- 실제 환경에서 남은 검증
- 범위 밖에서 발견한 blocking issue
