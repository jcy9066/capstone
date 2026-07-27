import numpy as np
import cv2
import logging
import torch
import os

import mmpose
import mmaction
from mmpose.apis import init_model as init_pose_model
from mmpose.apis import inference_topdown
from mmaction.apis import init_recognizer, inference_recognizer
from perception.device import resolve_cuda_device
from perception.models.action_policy import classify_target_action
from perception.models.action_batch import process_topdown_many

class ActionRecognizer:
    def __init__(self, device=None):
        device = resolve_cuda_device(device)
        logging.getLogger('mmengine').setLevel(logging.ERROR)
        
        mmpose_base = os.path.dirname(mmpose.__file__)
        mmaction_base = os.path.dirname(mmaction.__file__)
        
        pose_config = os.path.join(mmpose_base, '.mim', 'configs', 'body_2d_keypoint', 'rtmpose', 'coco', 'rtmpose-m_8xb256-420e_coco-256x192.py')
        action_config = os.path.join(mmaction_base, '.mim', 'configs', 'skeleton', 'posec3d', 'slowonly_r50_8xb16-u48-240e_ntu60-xsub-keypoint.py')
        
        pose_checkpoint = 'weights/rtmpose-m_simcc-coco_pt-aic-coco_420e-256x192-d8dd5ca4_20230127.pth'
        action_checkpoint = 'weights/slowonly_r50_8xb16-u48-240e_ntu60-xsub-keypoint_20220815-38db104b.pth'
        
        if not os.path.exists(pose_checkpoint):
            raise FileNotFoundError(f"🚨 에러: RTMPose 가중치 파일이 없습니다 -> {pose_checkpoint}")
        if not os.path.exists(action_checkpoint):
            raise FileNotFoundError(f"🚨 에러: PoseConv3D 가중치 파일이 없습니다 -> {action_checkpoint}")

        print("⏳ 로컬 환경에서 RTMPose를 적재합니다...")
        self.pose_model = init_pose_model(pose_config, pose_checkpoint, device=device)
        
        print("⏳ 로컬 환경에서 PoseConv3D를 적재합니다...")
        self.action_model = init_recognizer(action_config, action_checkpoint, device=device)
        print("✅ 100% 오프라인 모델 로드 성공!")

        self.action_buffer = {} 
        self.skeleton_links = [
            (15, 13), (13, 11), (16, 14), (14, 12), (11, 12), (5, 11), (6, 12),
            (5, 6), (5, 7), (6, 8), (7, 9), (8, 10), (1, 2), (0, 1), (0, 2), (1, 3), (2, 4)
        ]

        self.target_actions = {
            41: {'name': 'STAGGERING', 'danger': False},   
            42: {'name': 'FALLING', 'danger': True},       
            49: {'name': 'PUNCHING', 'danger': True},      
            50: {'name': 'KICKING', 'danger': True},       
            51: {'name': 'PUSHING', 'danger': True},       
            58: {'name': 'APPROACHING', 'danger': False},  
        }

    def process_many(self, frame, objs):
        return process_topdown_many(self, frame, objs, total_frames=48, pose_scope=None)

    def process(self, frame, obj):
        x1, y1, x2, y2 = map(int, obj['box'])
        bboxes = np.array([[x1, y1, x2, y2]])
        
        pose_results = inference_topdown(self.pose_model, frame, bboxes, bbox_format='xyxy')
        
        if not pose_results or len(pose_results) == 0:
            return None, None
            
        keypoints = pose_results[0].pred_instances.keypoints[0]
        kpt_scores = pose_results[0].pred_instances.keypoint_scores[0]
        
        obj_id = obj['id']
        if obj_id not in self.action_buffer:
            self.action_buffer[obj_id] = {'keypoints': [], 'scores': []}
            
        self.action_buffer[obj_id]['keypoints'].append(keypoints)
        self.action_buffer[obj_id]['scores'].append(kpt_scores)
        
        # --- 즉시 추론을 위한 동적 패딩(Dynamic Padding) 로직 ---
        current_kpts = self.action_buffer[obj_id]['keypoints']
        current_scores = self.action_buffer[obj_id]['scores']
        
        pad_len = 48 - len(current_kpts)
        if pad_len > 0:
            # 48프레임이 안 될 경우, 마지막 프레임의 자세를 남은 길이만큼 복제하여 배열 완성
            padded_kpts = current_kpts + [current_kpts[-1]] * pad_len
            padded_scores = current_scores + [current_scores[-1]] * pad_len
        else:
            padded_kpts = current_kpts
            padded_scores = current_scores
            
        # 48프레임을 채울 때까지 기다리지 않고 매 프레임 즉각적으로 행동 분석 수행
        action_result = self._classify_real_action(padded_kpts, padded_scores, frame.shape)
        
        # 슬라이딩 윈도우 갱신 (최대 48프레임 유지)
        if len(self.action_buffer[obj_id]['keypoints']) >= 48:
            self.action_buffer[obj_id]['keypoints'].pop(0)
            self.action_buffer[obj_id]['scores'].pop(0)

        return keypoints, action_result

    def _classify_real_action(self, keypoints_list, scores_list, img_shape):
        if self.action_model is None:
            return None

        fake_anno = dict(
            frame_dir='', label=-1, img_shape=(img_shape[0], img_shape[1]),
            original_shape=(img_shape[0], img_shape[1]), start_index=0, modality='Pose',
            total_frames=len(keypoints_list),
            keypoint=np.expand_dims(np.array(keypoints_list), axis=0), 
            keypoint_score=np.expand_dims(np.array(scores_list), axis=0)
        )

        try:
            result = inference_recognizer(self.action_model, fake_anno)
            scores = result.pred_score
            max_idx = torch.argmax(scores).item()
            max_score = scores[max_idx].item()
            
            # Two-stage policy returns suspicious or danger based on action score.
            action = classify_target_action(max_idx, max_score, self.target_actions)
            if action:
                return action
                
        except Exception:
            pass
            
        return None

    def draw_skeleton(self, frame, keypoints, color):
        if keypoints is None: return
        for kp in keypoints:
            x, y = map(int, kp)
            cv2.circle(frame, (x, y), 2, color, -1)
        for start, end in self.skeleton_links:
            pt1 = tuple(map(int, keypoints[start]))
            pt2 = tuple(map(int, keypoints[end]))
            if pt1 != (0, 0) and pt2 != (0, 0):
                cv2.line(frame, pt1, pt2, color, 1)
