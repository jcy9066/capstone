from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from frontend.routes.pages import pages_bp
from frontend.routes.status import status_bp
from frontend.routes.stream import stream_bp
from frontend.routes.telegram import telegram_bp


ROOT_DIR = Path(__file__).resolve().parents[1]


def create_app():
    # capstone/.env 파일을 로드합니다.
    load_dotenv(ROOT_DIR / ".env")

    app = Flask(
        __name__,
        template_folder=str(ROOT_DIR / "templates"),
        static_folder=str(ROOT_DIR / "static"),
    )

    app.register_blueprint(pages_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(stream_bp)
    app.register_blueprint(telegram_bp)

    return app