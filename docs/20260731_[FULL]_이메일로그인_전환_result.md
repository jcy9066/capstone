# 이메일 로그인 전환 결과

## 구현 결과

- 로그인 식별자를 전체 이메일 주소로 전환했다.
- 회원가입 화면에서 별도 로그인 ID 입력란과 ID 중복 확인을 제거했다.
- 이메일 인증 후 비밀번호, 비밀번호 2차 확인, 이름, 전화번호, 사번만 입력하도록 구성했다.
- 회원가입 INSERT 및 로그인 조회가 `users.login_id` 열을 사용하지 않도록 변경했다.
- 기존 이메일 인증 JWT·HttpOnly 쿠키 흐름은 유지했다.
- 테이블 생성·수정·마이그레이션은 수행하지 않았다.

## 변경 파일

- `server/auth_service.py`
- `frontend/templates/login.html`
- `frontend/services/static/login_email_auth.js`

## 검증

- `python -m py_compile server/auth_service.py server/app.py` 성공
- `python -m unittest tests.test_auth_service -v` 성공 (3건)
- 가짜 DB로 회원가입 SQL을 검증하여 `login_id` 미참조 및 기존 열만 INSERT함을 확인
- 이 Windows 환경에는 Node.js가 없어 브라우저 JavaScript 자동 문법 검사는 실행하지 못함
