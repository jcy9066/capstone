import cv2
import requests
import numpy as np

# 서버 주소 (로컬에서 실행하므로 localhost)
SERVER_URL = "http://localhost:5000/upload"

# 0번은 노트북 기본 웹캠입니다.
cap = cv2.VideoCapture(0)

print("📸 노트북 카메라 전송을 시작합니다. (종료: ctrl-c 키)")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 영상 크기 조절 (서버 부하를 줄이기 위해 선택 사항)
    frame = cv2.resize(frame, (640, 480))

    # 이미지를 jpg 형식으로 인코딩
    _, img_encoded = cv2.imencode('.jpg', frame)
    
    try:
        # app.py의 /upload 라우트로 바이너리 데이터 전송
        response = requests.post(SERVER_URL, data=img_encoded.tobytes(), timeout=1)
    except Exception as e:
        print(f"전송 오류: {e}")

    # 노트북 화면에도 창을 띄워 확인하고 싶다면 아래 주석 해제
    # cv2.imshow('Laptop Camera Test', frame)
    # if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()