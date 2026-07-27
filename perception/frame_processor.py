import cv2

from .core.trigger import CascadingTrigger
from .utils.telegram_notifier import TelegramNotifier
from .models.violence_heuristic import ViolenceHeuristic


class FrameProcessor:
    def __init__(self, detector, action_analyzer, notifier=None):
        self.detector = detector
        self.action_analyzer = action_analyzer
        self.trigger = CascadingTrigger()
        self.notifier = notifier if notifier is not None else TelegramNotifier()
        self.action_display_buffer = {}
        self.violence_heuristic = ViolenceHeuristic()

    def process(self, frame):
        tracked_boxes = self.detector.track(frame)
        obj_states = self.trigger.get_object_states(tracked_boxes)
        display_frame = frame.copy()
        detections = []
        danger = False

        for obj in tracked_boxes:
            oid = obj["id"]
            cls_id = obj.get("cls", 0)
            state = obj_states.get(oid, 0)

            detection = {
                "id": oid,
                "cls": cls_id,
                "box": [float(v) for v in obj["box"]],
                "state": state,
                "label": "",
                "score": None,
                "danger": False,
            }

            if state == 0:
                detections.append(detection)
                continue

            color = (0, 165, 255)
            label = ""
            skeleton = None

            if cls_id == 0:
                skeleton, action = self.action_analyzer.process(frame, obj)

                if action:
                    self.action_display_buffer[oid] = action

                if oid in self.action_display_buffer:
                    current_action = self.action_display_buffer[oid]
                    detection["label"] = current_action["label"]
                    detection["score"] = float(current_action["score"])
                    detection["danger"] = bool(current_action["is_danger"])

                    if current_action["is_danger"]:
                        danger = True
                        color = (0, 0, 255)
                        label = f"!!! {current_action['label']} !!! {current_action['score'] * 100:.0f}%"
                        self.notifier.send_alert_async(
                            f"위험 행동 감지: {current_action['label']}",
                            frame.copy(),
                        )
                    else:
                        label = f"[{current_action['label']}] {current_action['score'] * 100:.0f}%"
            else:
                danger = True
                detection["label"] = "WEAPON"
                detection["danger"] = True
                label = "WEAPON"

            x1, y1, x2, y2 = map(int, obj["box"])
            # Bounding box visualization disabled. Keep this line for easy rollback.
            # cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)

            if skeleton is not None:
                self.action_analyzer.draw_skeleton(display_frame, skeleton, color)

            if label:
                cv2.putText(
                    display_frame,
                    label,
                    (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                )

            detections.append(detection)

        return {
            "frame": display_frame,
            "detections": detections,
            "danger": danger,
        }

