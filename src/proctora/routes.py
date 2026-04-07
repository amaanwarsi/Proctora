from __future__ import annotations

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request

from proctora.database.repository import ExamTokenError


main = Blueprint("main", __name__)


@main.get("/")
def index():
    return render_template("index.html")


@main.get("/workspace")
def workspace():
    token = request.args.get("token", "").strip()
    if not token:
        abort(400, description="A valid exam token is required.")

    database = current_app.extensions["database"]
    try:
        exam = database.resolve_exam_by_token(token)
    except ExamTokenError as exc:
        abort(404, description=str(exc))

    return render_template(
        "workspace.html",
        exam_url=exam.exam_url,
        exam_name=exam.name,
        exam_token=token,
    )


@main.get("/confirmation")
def confirmation():
    return render_template("confirmation.html")


@main.get("/health")
def health():
    return {"status": "ok", "app": current_app.config["APP_NAME"]}


@main.get("/alerts")
def alerts():
    service = current_app.extensions["proctoring_service"]
    return jsonify({"alerts": service.alerts.as_list()})


@main.get("/video-feed")
def video_feed():
    service = current_app.extensions["proctoring_service"]
    return Response(
        service.generate_video_feed(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )
