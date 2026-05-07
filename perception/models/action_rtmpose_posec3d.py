import numpy as np
import cv2
import logging
import torch
import os
import glob
import mmpose
import mmaction
from mmpose.apis import init_model as init_pose_model
from mmpose.apis import inference_topdown
from mmaction.apis import init_recognizer, inference_recognizer
from mmengine.registry import DefaultScope

def find_weight(pattern):
    files = glob.glob(pattern)
    if not files: raise FileNotFoundError(f"에러: 가중치 파일 없음 -> {pattern}")
    return files[0]

class ActionRecognizer:
    def __init__(self, device=None):
        device = (device or os.getenv("DEVICE", f"cuda:{os.getenv('CUDA_DEVICE_INDEX', '0').strip()}")).strip().lower()
        logging.getLogger('mmengine').setLevel(logging.ERROR)
        
        print("⏳ 로컬 환경에서 RTMPose 모델을 적재합니다...")
        pose_config = os.path.join(os.path.dirname(mmpose.__file__), '.mim', 'configs', 'body_2d_keypoint', 'rtmpose', 'coco', 'rtmpose-m_8xb256-420e_coco-256x192.py')
        pose_checkpoint = find_weight('weights/rtmpose-m_simcc*.pth')
        
        print("⏳ 로컬 환경에서 PoseConv3D 모델을 적재합니다...")
        action_config = find_weight('weights/slowonly_r50_8xb16-u48*.py')
        action_checkpoint = find_weight('weights/slowonly_r50_8xb16-u48*.pth')

        with DefaultScope.overwrite_default_scope('mmpose'):
            self.pose_model = init_pose_model(pose_config, pose_checkpoint, device=device)
            
        with DefaultScope.overwrite_default_scope('mmaction'):
            self.action_model = init_recognizer(action_config, action_checkpoint, device=device)
            
        print("✅ RTMPose & PoseConv3D 로컬 적재 및 스코프 분리 완료!")

        self.action_buffer = {} 
        self.skeleton_links = [(15, 13), (13, 11), (16, 14), (14, 12), (11, 12), (5, 11), (6, 12), (5, 6), (5, 7), (6, 8), (7, 9), (8, 10), (1, 2), (0, 1), (0, 2), (1, 3), (2, 4)]
        self.target_actions = {41: {'name': 'STAGGERING', 'danger': False}, 42: {'name': 'FALLING', 'danger': True}, 49: {'name': 'PUNCHING', 'danger': True}, 50: {'name': 'KICKING', 'danger': True}, 51: {'name': 'PUSHING', 'danger': True}, 58: {'name': 'APPROACHING', 'danger': False}}

    def process(self, frame, obj):
        x1, y1, x2, y2 = map(int, obj['box'])
        
        with DefaultScope.overwrite_default_scope('mmpose'):
            pose_results = inference_topdown(self.pose_model, frame, np.array([[x1, y1, x2, y2]]), bbox_format='xyxy')
        
        if not pose_results or len(pose_results) == 0:
            return None, None
            
        kpts = pose_results[0].pred_instances.keypoints[0]
        scores = pose_results[0].pred_instances.keypoint_scores[0]
        
        obj_id = obj['id']
        if obj_id not in self.action_buffer: 
            self.action_buffer[obj_id] = {'kpts': [], 'scores': []}
            
        self.action_buffer[obj_id]['kpts'].append(kpts)
        self.action_buffer[obj_id]['scores'].append(scores)
        
        # PoseConv3D 동적 패딩 (48 프레임)
        cur_kpts = self.action_buffer[obj_id]['kpts']
        cur_scores = self.action_buffer[obj_id]['scores']
        pad_len = 48 - len(cur_kpts)
        
        pad_kpts = cur_kpts + [cur_kpts[-1]] * pad_len if pad_len > 0 else cur_kpts
        pad_scores = cur_scores + [cur_scores[-1]] * pad_len if pad_len > 0 else cur_scores
            
        action_res = self._classify(pad_kpts, pad_scores, frame.shape)
        
        if len(self.action_buffer[obj_id]['kpts']) >= 48:
            self.action_buffer[obj_id]['kpts'].pop(0)
            self.action_buffer[obj_id]['scores'].pop(0)

        return kpts, action_res

    def _classify(self, kpts, scores, shape):
        anno = dict(
            frame_dir='', label=-1, img_shape=(shape[0], shape[1]), 
            original_shape=(shape[0], shape[1]), start_index=0, modality='Pose', 
            total_frames=48, keypoint=np.expand_dims(np.array(kpts), axis=0), 
            keypoint_score=np.expand_dims(np.array(scores), axis=0)
        )
        try:
            with DefaultScope.overwrite_default_scope('mmaction'):
                result = inference_recognizer(self.action_model, anno)
            max_idx = torch.argmax(result.pred_score).item()
            max_score = result.pred_score[max_idx].item()
            
            if max_idx in self.target_actions and max_score > 0.35:
                return {"label": self.target_actions[max_idx]['name'], "score": max_score, "is_danger": self.target_actions[max_idx]['danger']}
        except Exception: 
            pass
        return None

    def draw_skeleton(self, frame, kpts, color):
        if kpts is None: return
        for x, y in kpts: cv2.circle(frame, (int(x), int(y)), 2, color, -1)
        for s, e in self.skeleton_links:
            if tuple(kpts[s]) != (0, 0) and tuple(kpts[e]) != (0, 0):
                cv2.line(frame, tuple(map(int, kpts[s])), tuple(map(int, kpts[e])), color, 1)
