from flask import Blueprint, render_template


pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    # 관제 센터 메인 웹페이지를 띄워줍니다.
    return render_template("index.html")