# 메인 권한 검사 및 로그아웃 결과

## 구현 결과

- 비로그인 사용자의 `/main` 접근은 첫 등록 라우트에서 `/login`으로 302 리디렉션된다.
- 사이드 패널에 로그아웃 버튼을 추가했다.
- 로그아웃 버튼은 CSRF 토큰을 받은 뒤 `/api/auth/logout`을 호출하고, 성공 시 `/login`으로 이동한다.
- 대시보드 JavaScript URL의 캐시 버전을 갱신해 기존 브라우저 캐시로 `logout()` 함수가 누락되는 문제를 방지했다.

## 변경 파일

- `frontend/templates/index.html`
- `frontend/services/static/style.css`
- `frontend/services/static/script.js`

## 검증

- `python -m py_compile server/app.py server/auth_service.py` 성공
- 첫 `/main` 라우트가 `auth_main_page`이고 로그아웃 API가 `logout_user`임을 확인
- 로그아웃 버튼과 `logout()` 함수 존재 확인
