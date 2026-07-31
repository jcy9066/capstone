# JWT 이메일 인증 전환 결과

## 완료 사항

- 이메일 인증번호 발송과 코드 검증 과정에서 `email_verifications` 테이블을 읽거나 쓰지 않도록 전환했다.
- 인증번호 원문은 저장하거나 JWT에 넣지 않고, 서버 비밀값 기반 HMAC 증명값만 JWT에 포함한다.
- 발송 단계의 인증 JWT와 검증 완료 JWT는 각각 만료 시간을 갖는다.
- 두 JWT는 API 응답 본문이나 JavaScript에 노출하지 않고 `HttpOnly`, `SameSite=Strict` 쿠키로만 전달한다. HTTPS 환경에서는 `COOKIE_SECURE=true`로 Secure 쿠키가 된다.
- 최종 회원가입 API에서만 검증 완료 JWT를 확인한 뒤 기존 `users` 테이블에 사용자를 INSERT한다.
- 재발송 횟수와 인증번호 오입력 횟수 제한을 이메일 인증 흐름에서 제거했다.

## DB 영향

- 테이블 생성, ALTER, DROP, 마이그레이션 실행을 하지 않았다.
- 이메일 인증 요청과 인증번호 검증은 DB를 사용하지 않는다.
- 기존 사용자 중복 확인 및 최종 가입은 기존 `users` 테이블만 사용한다.

## 검증

- `python -m py_compile server/auth_service.py server/app.py` 성공
- `python -m unittest tests.test_auth_service -v` 성공
- 가짜 SMTP 발송기를 이용한 DB 없는 JWT 발급·코드 검증 흐름 성공

## 실행 전 확인

- WSL에서 실행한다면 프로젝트 루트의 `.env`에 Gmail SMTP 설정과 `EMAIL_VERIFICATION_SECRET`이 있어야 한다.
- WSL Python 환경에는 `requirements.txt`의 패키지가 설치되어 있어야 한다.
- 실제 SMTP 전송은 비밀값을 사용하므로 자동 실행하지 않았으며, 서버를 재시작한 뒤 `/login`에서 인증번호 발송으로 확인한다.
