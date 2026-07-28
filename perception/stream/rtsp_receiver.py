import cv2
import threading
import queue

class RTSPReceiver:
    def __init__(self, rtsp_url):
        self.cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        self.q = queue.Queue(maxsize=3)
        self.running = True
        
        # 프레임 수신 스레드 시작
        self.thread = threading.Thread(target=self._read_frames)
        self.thread.daemon = True
        self.thread.start()

    def _read_frames(self):
        while self.running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                continue
            # 큐가 꽉 차있으면 가장 오래된 프레임을 버리고 최신 프레임 유지 (지연 방지)
            if self.q.full():
                self.q.get()
            self.q.put(frame)

    def get_frame(self):
        if not self.q.empty():
            return self.q.get()
        return None

    def stop(self):
        self.running = False
        self.cap.release()