from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proctora.app import create_app


app = create_app(start_monitors=False)


if __name__ == "__main__":
    runtime_app = create_app(start_monitors=True)
    runtime_app.run(
        host=runtime_app.config["HOST"],
        port=runtime_app.config["PORT"],
        debug=runtime_app.config["DEBUG"],
    )
