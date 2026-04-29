import cv2
import numpy as np
from flask import Flask, render_template, request, Response, jsonify
import requests
import os
from dotenv import load_dotenv
import time

# .env 파일 로드
load_dotenv()

app = Flask(__name__)

# 영상 프레임 및 로봇 상태를 저장할 전역 변수
current_frame = None
robot_status = {
    "cpu_usage": "0.0",
    "cpu_temp": "0.0",
    "battery": "100",
    "ram_usage": "0.0",
    "internet": "원활"
}

# 텔레그램 설정값
# 보안을 위한 .env 파일 격리?
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

@app.route('/send_telegram', methods=['POST'])
def send_telegram():
    # 텔레그램으로 보낼 메시지 내용
    message = "🚨 [긴급] 순찰 로봇 위험 감지! 관제 센터에서 신고가 접수되었습니다."
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"status": "error"}), 500
    except Exception as e:
        print(f"텔레그램 전송 오류: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/')
def index():
    # 관제 센터 메인 웹페이지를 띄워줍니다.
    return render_template('index.html')

@app.route('/update_status', methods=['POST'])
def update_status():
    global robot_status
    # 라즈베리 파이(pi_server.py)에서 1초마다 보내는 데이터를 받습니다.
    data = request.get_json() 
    if data:
        robot_status['cpu_usage'] = data.get('cpu_usage', robot_status['cpu_usage'])
        robot_status['cpu_temp'] = data.get('cpu_temp', robot_status['cpu_temp'])
        robot_status['battery'] = data.get('battery', robot_status['battery'])
        robot_status['ram_usage'] = data.get('ram_usage', robot_status['ram_usage'])
        robot_status['internet'] = data.get('internet', robot_status['internet'])
    return jsonify({"message": "Status updated successfully"}), 200

@app.route('/get_status', methods=['GET'])
def get_status():
    # index.html에서 1초마다 이 주소로 접근해 최신 상태를 가져갑니다.
    return jsonify(robot_status)

@app.route('/upload', methods=['POST'])
def upload_frame():
    global current_frame
    nparr = np.frombuffer(request.data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is not None:
        # 향후 YOLOv8 적용 위치
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            current_frame = buffer.tobytes()

    return 'OK', 200

# 라즈베리 카메라 전용 코드인데 노트북으로 할 때도 이걸로 해야 되는데...?
def generate_frames():
    global current_frame
    while True:
        if current_frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + current_frame + b'\r\n')
            time.sleep(0.03)
        else:
            time.sleep(0.1)

# ???뭔 코드지지
# app.py 상단에 추가
# camera = cv2.VideoCapture(0) 
# def generate_frames():
#     while True:
#         success, frame = camera.read()  # 카메라 읽기
#         if not success:
#             break
#         else:
#             # 여기서 YOLOv8 탐지 로직을 넣을 수 있습니다.
#             ret, buffer = cv2.imencode('.jpg', frame)
#             frame_bytes = buffer.tobytes()
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("🚀🚀🚀로봇 관제 서버를 시작합니다🚀🚀🚀")
    print("접속 주소: http://localhost:5000")
    # 호스트를 0.0.0.0으로 개방하여 라즈베리 파이가 접근할 수 있게 합니다.
    app.run(host='0.0.0.0', port=5000, debug=True)

