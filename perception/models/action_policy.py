try:
    from perception.env_config import env_float
except ModuleNotFoundError:  # Direct perception script execution.
    from env_config import env_float

SUSPICIOUS_ACTION_THRESHOLD = env_float(
    "ACTION_SUSPICIOUS_THRESHOLD", minimum=0.0, maximum=1.0
)
DANGER_ACTION_THRESHOLD = env_float(
    "ACTION_DANGER_THRESHOLD", minimum=0.0, maximum=1.0
)

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
