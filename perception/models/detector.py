from ultralytics import YOLO
import os

class DetectorMOT:
    def __init__(self, weight_path="weights/yolov10x.pt"):
        if not os.path.exists(weight_path):
            raise FileNotFoundError(f"🚨 에러: YOLO 가중치 파일이 없습니다. 로컬 다운로드를 확인하십시오 -> {weight_path}")
            
        self.model = YOLO(weight_path)
        # 0: 사람, 34: 야구방망이, 43: 칼, 76: 가위
        self.target_classes = [0, 34, 43, 76] 

    def track(self, frame):
        return self.model.track(
            frame, 
            persist=True, 
            tracker="bytetrack.yaml", 
            half=True, 
            verbose=False,
            classes=self.target_classes,
            conf=0.25,
            imgsz=640 
        )