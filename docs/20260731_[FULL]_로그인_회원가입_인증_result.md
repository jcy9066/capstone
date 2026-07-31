# 20260731 [FULL] 로그인·회원가입·이메일 인증 구현 결과

## 1. 완료 내용

- FastAPI 통합 서버에 MySQL 기반 회원가입·로그인 API를 추가했다.
- `/login`에서 전용 no-reply SMTP 계정의 실제 인증번호 발송과 서버 측 검증 흐름을 연결했다.
- 이메일 인증 전에는 로그인 ID, 비밀번호, 비밀번호 확인, 가입 버튼을 비활성화한다.
- 이메일 인증 성공 후에만 가입 입력 영역을 활성화한다.
- 로그인 ID, 이메일, 사번 중복을 UI 보조 API와 가입 직전 DB 검증에서 모두 확인한다.
- 비밀번호는 bcrypt 해시만 `users.password_hash`에 저장하고, 로그인 시 해시를 비교한다.
- 삭제 계정은 로그인되지 않으며, 성공 시 `users.login_at`을 갱신하고 서명된 세션을 생성한다.
- `/main`은 로그인 세션이 없는 사용자를 `/login`으로 이동시킨다.
- CSRF 토큰, 인증번호 만료·일회성 사용·시도 횟수·재전송 제한·IP 기반 요청 제한을 적용했다.

## 2. 수정·생성 파일

- `server/app.py`: 인증 API, 세션, CSRF, 로그인 보호 및 Windows에서 ROS 미설치 시 브리지 생략 처리를 추가했다.
- `server/database.py`: 환경 변수 기반 MySQL 트랜잭션 접근을 추가했다.
- `server/email_service.py`: no-reply SMTP 인증 메일 발송을 추가했다.
- `server/auth_service.py`: 서버 측 입력 검증, 이메일 인증, 중복 검증, 가입, 로그인을 추가했다.
- `frontend/services/static/login_auth.js`: 로그인·가입 UI와 API 호출을 추가했다.
- `frontend/services/static/login_auth.css`: 인증 화면 보조 UI 스타일을 추가했다.
- `frontend/templates/login.html`: 새 인증 UI 스크립트를 연결했다.
- `data/database/20260731_add_users_login_id_and_email_verifications.sql`: 운영 DB를 삭제하지 않는 마이그레이션을 추가했다.
- `data/database/init_schema.sql`: 신규 설치용 `login_id`, `email_verifications` 정의를 반영했다.
- `.env.example`: DB, no-reply SMTP, 세션, 인증 제한 환경 변수 예시를 추가했다.
- `requirements.txt`: PyMySQL, bcrypt, itsdangerous와 UTF-8 선언을 추가했다.
- `tests/test_auth_service.py`: 로그인 ID·비밀번호·사번 입력 정책 테스트를 추가했다.

## 3. 운영 적용 순서

1. 실제 비밀값을 포함한 `.env`를 `.env.example` 기준으로 작성한다. `.env`는 커밋하지 않는다.
2. 전용 발신 계정의 SMTP 값에 `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`을 설정한다.
3. 운영 MySQL에서 `data/database/20260731_add_users_login_id_and_email_verifications.sql`을 한 번 실행한다.
4. `init_schema.sql`은 DB 전체를 삭제하므로 운영 DB에 실행하지 않는다.
5. HTTPS 운영에서는 `COOKIE_SECURE=true`를 유지한다. HTTPS 없이 로컬 기능만 점검할 때만 `COOKIE_SECURE=false`를 사용한다.

## 4. 검증 결과

- `python -m unittest tests.test_auth_service tests.test_dry_run_planner -v`: 13개 통과.
- `python -m py_compile server/app.py server/auth_service.py server/database.py server/email_service.py`: 통과.
- 모델 추론을 비활성화한 로컬 Uvicorn 서버에서 `/login` 200, 인증 UI 스크립트 연결, 세션 쿠키 발급, `/api/auth/csrf` 토큰 발급을 확인했다.
- 현재 작업 환경에는 실제 MySQL 및 no-reply SMTP 자격 증명이 없으므로, 실제 이메일 발송·운영 DB INSERT/로그인은 위 운영 적용 순서 후 점검해야 한다.
