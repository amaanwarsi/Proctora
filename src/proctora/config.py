from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    APP_NAME = os.getenv("PROCTORA_APP_NAME", "Proctora")
    DEBUG = os.getenv("PROCTORA_DEBUG", "false").lower() == "true"
    HOST = os.getenv("PROCTORA_HOST", "127.0.0.1")
    PORT = int(os.getenv("PROCTORA_PORT", "5000"))
    DATABASE_PATH = os.getenv("PROCTORA_DATABASE_PATH", "instance/proctora.sqlite3")

    TAB_CHECK_INTERVAL = float(os.getenv("PROCTORA_TAB_CHECK_INTERVAL", "0.5"))
    HEAD_SHIFT_THRESHOLD = int(os.getenv("PROCTORA_HEAD_SHIFT_THRESHOLD", "20"))
    NO_FACE_THRESHOLD = int(os.getenv("PROCTORA_NO_FACE_THRESHOLD", "30"))
    MAX_ALLOWED_FACES = int(os.getenv("PROCTORA_MAX_ALLOWED_FACES", "1"))
    VOICE_THRESHOLD = int(os.getenv("PROCTORA_VOICE_THRESHOLD", "5000"))
    ALERT_COOLDOWN_SECONDS = float(
        os.getenv("PROCTORA_ALERT_COOLDOWN_SECONDS", "3")
    )
    CAMERA_INDEX = int(os.getenv("PROCTORA_CAMERA_INDEX", "0"))
