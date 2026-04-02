import cv2
import argparse
import os
from core.trigger import CascadingTrigger
from utils.telegram_notifier import TelegramNotifier

class LocalVideoReader:
    def __init__(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"에러: 영상 파일이 없습니다 -> {path}")
        self.cap = cv2.VideoCapture(path)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30

    def get_frame(self):
        ret, frame = self.cap.read()
        return frame if ret else None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=str, required=True, help="테스트 영상 경로")
    args = parser.parse_args()

    print("\n=== 방범 순찰 로봇 행동 분석 파이프라인 선택 ===")
    print("1. YOLO11n - ByteTrack - RTMPose - ST-GCN")
    print("2. YOLO11x - ByteTrack - RTMPose - ST-GCN")
    print("3. DINO - Bot-SORT - ViTPose(H) - ST-GCN++")
    print("4. YOLO11x - Bot-SORT - RTMPose - ST-GCN++")
    print("5. YOLO11x-Pose - Bot-SORT - (통합) - ST-GCN++")
    print("6. YOLO26m - Bot-SORT - RTMPose - ST-GCN++")
    print("7. YOLO26m - Bot-SORT - RTMPose - PoseConv3D")
    print("8. YOLO26m-Pose - Bot-SORT - (통합) - ST-GCN++")
    print("9. YOLO26m-Pose - Bot-SORT - (통합) - PoseConv3D")
    
    choice = input("\n구동할 파이프라인 번호를 입력하십시오 (1-9): ").strip()

    if choice == '1':
        pipeline_name = "YOLO11n_ByteTrack_RTMPose_STGCN"
        from models.detector_yolo import YOLODetector
        from models.action_rtmpose_stgcn import ActionRecognizer
        detector = YOLODetector(weight="weights/yolo11n.pt", tracker="bytetrack")
        action_analyzer = ActionRecognizer()
    elif choice == '2':
        pipeline_name = "YOLO11x_ByteTrack_RTMPose_STGCN"
        from models.detector_yolo import YOLODetector
        from models.action_rtmpose_stgcn import ActionRecognizer
        detector = YOLODetector(weight="weights/yolo11x.pt", tracker="bytetrack")
        action_analyzer = ActionRecognizer()
    elif choice == '3':
        pipeline_name = "DINO_BotSORT_ViTPose_STGCNpp"
        from models.detector_dino import DINODetector
        from models.action_vitpose_stgcnpp import ActionRecognizer
        detector = DINODetector()
        action_analyzer = ActionRecognizer()
    elif choice == '4':
        pipeline_name = "YOLO11x_BotSORT_RTMPose_STGCNpp"
        from models.detector_yolo import YOLODetector
        from models.action_rtmpose_stgcnpp import ActionRecognizer
        detector = YOLODetector(weight="weights/yolo11x.pt", tracker="botsort")
        action_analyzer = ActionRecognizer()
    elif choice == '5':
        pipeline_name = "YOLO11xPose_BotSORT_STGCNpp"
        from models.detector_yolo import YOLOPoseDetector
        from models.action_yolopose_stgcnpp import ActionRecognizer
        detector = YOLOPoseDetector(weight="weights/yolo11x-pose.pt", tracker="botsort")
        action_analyzer = ActionRecognizer()
    elif choice == '6':
        pipeline_name = "YOLO26m_BotSORT_RTMPose_STGCNpp"
        from models.detector_yolo import YOLODetector
        from models.action_rtmpose_stgcnpp import ActionRecognizer
        detector = YOLODetector(weight="weights/yolo26m.pt", tracker="botsort")
        action_analyzer = ActionRecognizer()
    elif choice == '7':
        pipeline_name = "YOLO26m_BotSORT_RTMPose_PoseConv3D"
        from models.detector_yolo import YOLODetector
        from models.action_rtmpose_posec3d import ActionRecognizer
        detector = YOLODetector(weight="weights/yolo26m.pt", tracker="botsort")
        action_analyzer = ActionRecognizer()
    elif choice == '8':
        pipeline_name = "YOLO26mPose_BotSORT_STGCNpp"
        from models.detector_yolo import YOLOPoseDetector
        from models.action_yolopose_stgcnpp import ActionRecognizer
        detector = YOLOPoseDetector(weight="weights/yolo26m-pose.pt", tracker="botsort")
        action_analyzer = ActionRecognizer()
    elif choice == '9':
        pipeline_name = "YOLO26mPose_BotSORT_PoseConv3D"
        from models.detector_yolo import YOLOPoseDetector
        from models.action_yolopose_posec3d import ActionRecognizer
        detector = YOLOPoseDetector(weight="weights/yolo26m-pose.pt", tracker="botsort")
        action_analyzer = ActionRecognizer()
    else:
        print("잘못된 입력입니다. 프로그램을 종료합니다.")
        return

    trigger = CascadingTrigger()
    notifier = TelegramNotifier()
    reader = LocalVideoReader(args.source)
    
    out_dir = os.path.join("output", pipeline_name)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"result_{os.path.basename(args.source)}")
    writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'mp4v'), reader.fps, (reader.width, reader.height))

    action_display_buffer = {}
    print(f"\n🚀 [{pipeline_name}] 분석을 시작합니다...")

    while True:
        frame = reader.get_frame()
        if frame is None: break

        tracked_boxes = detector.track(frame)
        obj_states = trigger.get_object_states(tracked_boxes)
        display_frame = frame.copy()

        for obj in tracked_boxes:
            oid = obj['id']
            cls_id = obj.get('cls', 0)
            state = obj_states.get(oid, 0) 
            
            if state == 0: continue
                
            color = (0, 165, 255)
            label = ""
            skeleton = None

            if cls_id == 0:
                skeleton, action = action_analyzer.process(frame, obj)
                
                if action:
                    action_display_buffer[oid] = action
                
                if oid in action_display_buffer:
                    current_action = action_display_buffer[oid]
                    if current_action['is_danger']:
                        color = (0, 0, 255)
                        label = f"!!! {current_action['label']} !!! {current_action['score']*100:.0f}%"
                        notifier.send_alert_async(f"⚠️ 위험 행동 감지: {current_action['label']}", frame.copy())
                    else:
                        label = f"[{current_action['label']}] {current_action['score']*100:.0f}%"
            else:
                label = "WEAPON"

            x1, y1, x2, y2 = map(int, obj['box'])
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
            
            if skeleton is not None:
                action_analyzer.draw_skeleton(display_frame, skeleton, color)
                
            if label:
                cv2.putText(display_frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        writer.write(display_frame)

    reader.cap.release()
    writer.release()
    print(f"✅ 분석 완료. 결과 파일이 저장되었습니다: {out_path}")

if __name__ == "__main__":
    main()