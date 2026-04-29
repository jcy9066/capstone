import requests
import threading
import cv2
from config import settings

class TelegramNotifier:
    def __init__(self):
        self.token = settings.TELEGRAM_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_alert_async(self, message, frame=None):
        """메인 스레드 지연을 막기 위해 텔레그램 전송을 백그라운드에서 실행합니다."""
        thread = threading.Thread(target=self._send_process, args=(message, frame))
        thread.daemon = True
        thread.start()

    def _send_process(self, message, frame):
        try:
            if frame is not None:
                _, buffer = cv2.imencode('.jpg', frame)
                files = {'photo': buffer.tobytes()}
                data = {'chat_id': self.chat_id, 'caption': message}
                requests.post(f"{self.base_url}/sendPhoto", data=data, files=files)
            else:
                data = {'chat_id': self.chat_id, 'text': message}
                requests.post(f"{self.base_url}/sendMessage", data=data)
        except Exception as e:
            print(f"Telegram 전송 실패: {e}")