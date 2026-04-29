# 20260429 [FULL] 대시보드 TemplateResponse 오류 수정 계획

## 1. 문제

통합 서버 접속 시 `/` 라우트에서 500 오류가 발생했다.

오류:

```text
TypeError: unhashable type: 'dict'
```

발생 위치:

```text
server/app.py
templates.TemplateResponse("index.html", {"request": request})
```

## 2. 원인

현재 설치된 FastAPI/Starlette 버전에서는 `Jinja2Templates.TemplateResponse` 호출 시 `request`를 첫 번째 인자로 받는 시그니처를 사용한다.

기존 코드의 호출 방식은 구버전 호환 형태라서, 현재 환경에서는 `"index.html"`이 request 자리로, context dict가 template name 자리로 해석되어 Jinja2가 dict를 템플릿 이름으로 캐시하려다 실패한다.

## 3. 수정 방향

`server/app.py`의 `/` 라우트를 현재 Starlette 시그니처에 맞게 수정한다.

```python
return templates.TemplateResponse(request, "index.html")
```

또는 호환성이 필요하면:

```python
return templates.TemplateResponse("index.html", {"request": request})
```

대신 현재 실행 환경 기준으로는 첫 번째 방식이 맞다.

## 4. 검증

```bash
python -m py_compile server/app.py
```

서버 재시작 후:

```bash
curl http://localhost:21063/
```

HTML이 반환되면 정상이다.

