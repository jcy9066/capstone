from flask import Blueprint, jsonify

from frontend.services.telegram_service import send_telegram_message


telegram_bp = Blueprint("telegram", __name__)


@telegram_bp.route("/send_telegram", methods=["POST"])
def send_telegram():
    success = send_telegram_message()

    if success:
        return jsonify({"status": "success"}), 200

    return jsonify({"status": "error"}), 500