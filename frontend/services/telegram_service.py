import requests

from frontend.config import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN


def send_telegram_message():
    # 텔레그램으로 보낼 메시지 내용
    message = "🚨 [긴급] 순찰 로봇 위험 감지! 관제 센터에서 신고가 접수되었습니다."
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }

    try:
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            return True

        return False

    except Exception as e:
        print(f"텔레그램 전송 오류: {e}")
        return False