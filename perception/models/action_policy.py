import os
SUSPICIOUS_ACTION_THRESHOLD = float(os.getenv("ACTION_SUSPICIOUS_THRESHOLD", "0.20"))
DANGER_ACTION_THRESHOLD = float(os.getenv("ACTION_DANGER_THRESHOLD", "0.50"))

def classify_target_action(action_idx, score, target_actions):
    action_info = target_actions.get(action_idx)
    action = None
    reason = "non_target" if action_info is None else "below_suspicious_threshold"

    if action_info is not None:
        is_configured_danger = bool(action_info.get("danger"))
        if is_configured_danger and score >= DANGER_ACTION_THRESHOLD:
            action = {
                "label": action_info["name"],
                "score": score,
                "is_danger": True,
                "confidence_level": "danger",
            }
            reason = "danger"
        elif score >= SUSPICIOUS_ACTION_THRESHOLD:
            action = {
                "label": action_info["name"],
                "score": score,
                "is_danger": False,
                "confidence_level": "suspicious",
            }
            reason = "suspicious"

    return action
