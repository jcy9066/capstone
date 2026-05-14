import sys
from pathlib import Path

# python frontend/app.py 방식으로 실행해도 frontend 패키지를 찾도록 root 경로를 추가합니다.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from frontend import create_app


app = create_app()

if __name__ == "__main__":
    # 호스트를 0.0.0.0으로 개방하여 라즈베리 파이가 접근할 수 있게 합니다.
    app.run(host="0.0.0.0", port=5000, debug=True)