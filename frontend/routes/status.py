from flask import Blueprint, Response, jsonify, request

from frontend.services.camera_service import (
    build_camera_status,
    generate_frames,
    upload_frame_bytes,
)


stream_bp = Blueprint("stream", __name__)


@stream_bp.route("/upload", methods=["POST"])
def upload_frame():
    upload_frame_bytes(request.data)
    return "OK", 200


@stream_bp.route("/api/stream_status", methods=["GET"])
def get_stream_status():
    return jsonify(build_camera_status())


@stream_bp.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )