import os
import glob
import torch
import numpy as np
import logging
from mmdet.apis import init_detector, inference_detector
from ultralytics.trackers.bot_sort import BOTSORT
from ultralytics.utils import IterableSimpleNamespace
from mmengine.registry import DefaultScope
from ultralytics.engine.results import Boxes
from perception.device import resolve_cuda_device

def find_weight(pattern):
    files = glob.glob(pattern)
    if not files: raise FileNotFoundError(f"에러: 가중치 파일 없음 -> {pattern}")
    return files[0]

class DINODetector:
    def __init__(self, device=None):
        device = resolve_cuda_device(device)
        logging.getLogger('mmengine').setLevel(logging.ERROR)
        
        print("⏳ 로컬 환경에서 DINO (Swin-L) 모델을 적재합니다...")
        config_path = find_weight('weights/dino-5scale_swin-l*.py')
        checkpoint_path = find_weight('weights/dino-5scale_swin-l*.pth')
        
        with DefaultScope.overwrite_default_scope('mmdet'):
            self.model = init_detector(config_path, checkpoint_path, device=device)
        
        bot_sort_args = IterableSimpleNamespace(
            tracker_type='botsort', track_high_thresh=0.3, track_low_thresh=0.1,
            new_track_thresh=0.4, track_buffer=30, match_thresh=0.8,
            gmc_method='sparseOptFlow', proximity_thresh=0.5, appearance_thresh=0.25,
            with_reid=False, fuse_score=True
        )
        self.tracker = BOTSORT(bot_sort_args, frame_rate=30)
        self.target_classes = [0]

    def track(self, frame):
        with DefaultScope.overwrite_default_scope('mmdet'):
            result = inference_detector(self.model, frame)
        
        pred = result.pred_instances
        mask = (pred.scores > 0.25) & (torch.isin(pred.labels, torch.tensor(self.target_classes, device=pred.labels.device)))
        
        boxes = pred.bboxes[mask]
        scores = pred.scores[mask]
        labels = pred.labels[mask]
        
        tracked_objects = []
        if len(boxes) > 0:
            # .cpu()를 명시적으로 호출하여 추적기의 Numpy 연산 충돌 방지
            det_tensor = torch.cat([boxes, scores.unsqueeze(1), labels.unsqueeze(1).float()], dim=1).cpu()
            ultralytics_boxes = Boxes(det_tensor, frame.shape[:2])
            
            tracks = self.tracker.update(ultralytics_boxes, frame)
            
            for t in tracks:
                if hasattr(t, 'tlbr'):
                    x1, y1, x2, y2 = t.tlbr
                    track_id = t.track_id
                    cls_id = getattr(t, 'cls', 0)
                else:
                    x1, y1, x2, y2, track_id, cls_id, score, _ = t
                    
                tracked_objects.append({
                    'id': int(track_id),
                    'box': np.array([x1, y1, x2, y2]),
                    'cls': int(cls_id),
                    'center': ((x1+x2)/2, (y1+y2)/2)
                })
                
        return tracked_objects
