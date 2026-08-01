# 저장 지도 이름 변경 결과

## 구현 완료

- 저장 지도 선택 창의 각 지도 카드를 우클릭하면 새 지도 이름을 입력할 수 있다.
- 이름 변경 성공 후 목록을 다시 조회해 새 이름을 즉시 표시한다.
- `POST /api/navigation/maps/rename` API를 추가했다. 로그인과 CSRF 검증을 모두 적용한다.
- 서버는 지도 이름 규칙과 파일 충돌을 검사한 뒤 `.pgm`, `.yaml`, `.meta.json`, `.raw.json`을 함께 이름 변경한다.
- YAML의 `image` 참조, 메타데이터의 지도 이름 및 파일 경로, 저장된 현재 선택/활성 지도 상태를 갱신한다.
- 작업 중 오류가 나면 새 파일을 제거하고 백업한 원래 파일을 되돌리도록 처리했다.

## 변경 파일

- `server/navigation_map_service.py`
- `server/navigation_map_api.py`
- `frontend/services/static/navigation_map_control.js`

## 검증

- `python -m py_compile server/navigation_map_service.py server/navigation_map_api.py` 성공
- 임시 디렉터리에서 지도 이름 변경, 메타데이터/YAML/상태 갱신, 잘못된 이름 거부를 확인
- FastAPI에 `/api/navigation/maps/rename` 라우트가 등록되고 기존 저장 지도 조회가 유지되는 것을 확인

## 실행 시 유의사항

배포 중인 FastAPI 서버에는 재시작 후 기능이 반영된다. 서버는 이 작업으로 재시작하지 않았다.
