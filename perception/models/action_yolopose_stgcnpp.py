import numpy as np
import cv2
import logging
import torch
import glob
import os
from mmaction.apis import init_recognizer, inference_recognizer
from mmengine.registry import DefaultScope
from perception.device import resolve_cuda_device
from perception.models.action_batch import process_keypoint_many
from perception.models.action_policy import classify_target_action

def find_weight(pattern):
    files = glob.glob(pattern)
    if not files: raise FileNotFoundError(f"에러: 가중치 파일 없음 -> {pattern}")
    return files[0]

class ActionRecognizer:
    def __init__(self, device=None):
        device = resolve_cuda_device(device)
        logging.getLogger('mmengine').setLevel(logging.ERROR)
        
        print("⏳ 로컬 환경에서 ST-GCN++ 모델을 적재합니다... (MMPose 생략)")
        action_config = find_weight('weights/stgcnpp_8xb16-joint-u100*.py')
        action_checkpoint = find_weight('weights/stgcnpp_8xb16-joint-u100*.pth')

        with DefaultScope.overwrite_default_scope('mmaction'):
            self.action_model = init_recognizer(action_config, action_checkpoint, device=device)

        self.action_buffer = {} 
        self.skeleton_links = [(15, 13), (13, 11), (16, 14), (14, 12), (11, 12), (5, 11), (6, 12), (5, 6), (5, 7), (6, 8), (7, 9), (8, 10), (1, 2), (0, 1), (0, 2), (1, 3), (2, 4)]
        self.target_actions = {42: {'name': 'FALLING', 'danger': True}, 49: {'name': 'PUNCHING', 'danger': True}, 50: {'name': 'KICKING', 'danger': True}, 51: {'name': 'PUSHING', 'danger': True}}

    def process_many(self, frame, objs):
        return process_keypoint_many(self, frame, objs, total_frames=100)

    def process(self, frame, obj):
        kpts = obj.get('keypoints')
        scores = obj.get('keypoints_scores')
        
        if kpts is None or len(kpts) == 0:
            return None, None
            
        obj_id = obj['id']
        if obj_id not in self.action_buffer: 
            self.action_buffer[obj_id] = {'kpts': [], 'scores': []}
            
        self.action_buffer[obj_id]['kpts'].append(kpts)
        self.action_buffer[obj_id]['scores'].append(scores)
        
        cur_kpts = self.action_buffer[obj_id]['kpts']
        cur_scores = self.action_buffer[obj_id]['scores']
        pad_len = 100 - len(cur_kpts)
        
        pad_kpts = cur_kpts + [cur_kpts[-1]] * pad_len if pad_len > 0 else cur_kpts
        pad_scores = cur_scores + [cur_scores[-1]] * pad_len if pad_len > 0 else cur_scores
            
        action_res = self._classify(pad_kpts, pad_scores, frame.shape)
        
        if len(self.action_buffer[obj_id]['kpts']) >= 100:
            self.action_buffer[obj_id]['kpts'].pop(0)
            self.action_buffer[obj_id]['scores'].pop(0)

        return kpts, action_res

    def _classify(self, kpts, scores, shape):
        anno = dict(
            frame_dir='', label=-1, img_shape=(shape[0], shape[1]), 
            original_shape=(shape[0], shape[1]), start_index=0, modality='Pose', 
            total_frames=100, keypoint=np.expand_dims(np.array(kpts), axis=0), 
            keypoint_score=np.expand_dims(np.array(scores), axis=0)
        )
        try:
            with DefaultScope.overwrite_default_scope('mmaction'):
                result = inference_recognizer(self.action_model, anno)
            max_idx = torch.argmax(result.pred_score).item()
            max_score = result.pred_score[max_idx].item()
            action = classify_target_action(max_idx, max_score, self.target_actions)
            if action:
                return action
        except Exception: 
            pass
        return None

    def draw_skeleton(self, frame, kpts, color):
        if kpts is None: return
        for x, y in kpts: cv2.circle(frame, (int(x), int(y)), 2, color, -1)
        for s, e in self.skeleton_links:
            if tuple(kpts[s]) != (0, 0) and tuple(kpts[e]) != (0, 0):
                cv2.line(frame, tuple(map(int, kpts[s])), tuple(map(int, kpts[e])), color, 1)
