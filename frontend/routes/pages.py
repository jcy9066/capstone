from flask import Blueprint, redirect, render_template, url_for


pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    # 첫 접속은 로그인 화면으로 보냅니다. 실제 인증 검사는 아직 연결하지 않습니다.
    return redirect(url_for("pages.login"))


@pages_bp.route("/login")
def login():
    # 프론트엔드 전용 로그인 화면입니다.
    return render_template("login.html")


@pages_bp.route("/main")
def main():
    # 관제 센터 메인 웹페이지를 띄워줍니다. 권한 검사는 추후 인증 연동 시 추가합니다.
    return render_template("index.html")
