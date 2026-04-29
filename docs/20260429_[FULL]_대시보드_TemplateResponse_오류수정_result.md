# 20260429 [FULL] 대시보드 TemplateResponse 오류 수정 결과

## 1. 작업 요약

통합 서버 `/` 접속 시 발생하던 500 오류를 수정했다.

오류:

```text
TypeError: unhashable type: 'dict'
```

## 2. 원인

현재 GPU 서버의 FastAPI/Starlette 환경에서는 `TemplateResponse`가 다음 형태를 기대한다.

```python
templates.TemplateResponse(request, "index.html")
```

기존 코드는 구버전 호환 방식이었다.

```python
templates.TemplateResponse("index.html", {"request": request})
```

이 때문에 context dict가 템플릿 이름처럼 해석되어 Jinja2 내부에서 `unhashable type: 'dict'` 오류가 발생했다.

## 3. 수정 파일

```text
server/app.py
```

수정 내용:

```python
return templates.TemplateResponse(request, "index.html")
```

## 4. 검증

수행:

```bash
python -m py_compile server/app.py
```

결과:

```text
문법 검사 통과
```

## 5. 재실행 방법

기존 서버를 종료한 뒤 다시 실행한다.

```bash
cd ~/capstone
uvicorn server.app:app --host 0.0.0.0 --port 21063
```

확인:

```bash
curl http://localhost:21063/
```

브라우저:

```text
http://10.108.90.21:21063
```

## 6. IP 로그 설명

Uvicorn 로그의 다음 값은 서버 포트가 아니라 접속한 클라이언트의 IP와 임시 포트다.

```text
10.107.80.56:9588
```

서버는 여전히 `0.0.0.0:21063`에서 요청을 받고 있고, `9588`은 브라우저 또는 클라이언트 OS가 임시로 사용한 outbound port다.

