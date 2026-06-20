from ultralytics import YOLO
import os

from perception.device import resolve_cuda_device

class DetectorMOT:
    def __init__(self, weight_path="weights/yolov10x.pt", device=None):
        if not os.path.exists(weight_path):
            raise FileNotFoundError(f"🚨 에러: YOLO 가중치 파일이 없습니다. 로컬 다운로드를 확인하십시오 -> {weight_path}")
            
        self.model = YOLO(weight_path)
        self.device = resolve_cuda_device(device)
        self.target_classes = [0]

    def track(self, frame):
        return self.model.track(
            frame, 
            persist=True, 
            tracker="bytetrack.yaml", 
            half=True, 
            verbose=False,
            classes=self.target_classes,
            conf=0.25,
            imgsz=640,
            device=self.device
        )