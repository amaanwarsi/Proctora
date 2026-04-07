from __future__ import annotations

from flask import Flask

from proctora.config import Config
from proctora.database import DatabaseRepository
from proctora.routes import main
from proctora.services.alerts import AlertStore
from proctora.services.proctoring import ProctoringService


def create_app(
    test_config: dict | None = None, *, start_monitors: bool = True
) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    database = DatabaseRepository(app.config["DATABASE_PATH"])
    database.initialize()
    app.extensions["database"] = database

    alerts = AlertStore()
    proctoring_service = ProctoringService(app.config, alerts)
    app.extensions["proctoring_service"] = proctoring_service

    app.register_blueprint(main)
    if start_monitors and not app.config.get("TESTING", False):
        proctoring_service.start_background_monitors()
    return app
