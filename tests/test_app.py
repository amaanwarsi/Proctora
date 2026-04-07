from pathlib import Path

from proctora.app import create_app
from proctora.database.repository import DeviceReuseBlockedError, SessionConflictError


def build_test_app(tmp_path: Path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "test.sqlite3"),
        }
    )


def test_health_endpoint(tmp_path):
    app = build_test_app(tmp_path)
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_workspace_requires_valid_token(tmp_path):
    app = build_test_app(tmp_path)
    database = app.extensions["database"]
    database.seed_exam_token(
        token="demo-token",
        exam_name="Physics Mock",
        duration=90,
        exam_url="https://example.com/exam",
    )
    client = app.test_client()

    ok_response = client.get("/workspace?token=demo-token")
    missing_response = client.get("/workspace")
    invalid_response = client.get("/workspace?token=bad-token")

    assert ok_response.status_code == 200
    assert missing_response.status_code == 400
    assert invalid_response.status_code == 404


def test_session_lock_and_results_payload(tmp_path):
    app = build_test_app(tmp_path)
    database = app.extensions["database"]
    database.seed_exam_token(
        token="lock-token",
        exam_name="Math Mock",
        duration=120,
        exam_url="https://example.com/math",
    )

    session_id = database.start_session(
        candidate_name="Amaan Warsi",
        exam_token="lock-token",
        device_signature="device-123",
    )
    database.increment_violation(
        session_id=session_id,
        violation_type="fullscreen_exit",
        increment=2,
    )
    database.increment_violation(
        session_id=session_id,
        violation_type="fullscreen_exit",
        increment=1,
    )
    payload = database.complete_session(
        session_id=session_id,
        final_status="submitted",
        event_timeline=[{"event_type": "finished", "payload": {"source": "test"}}],
    )

    assert payload["final_status"] == "submitted"
    assert payload["violation_summary"]["fullscreen_exit"]["count"] == 3

    with database.connect() as connection:
        row = connection.execute(
            "SELECT final_status FROM exam_results WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        assert row["final_status"] == "submitted"

    try:
        database.start_session(
            candidate_name="Amaan Warsi",
            exam_token="lock-token",
            device_signature="device-123",
        )
    except DeviceReuseBlockedError:
        pass
    else:
        raise AssertionError("Device reuse should be blocked after completion.")


def test_duplicate_active_session_is_blocked(tmp_path):
    app = build_test_app(tmp_path)
    database = app.extensions["database"]
    database.seed_exam_token(
        token="active-lock-token",
        exam_name="English Mock",
        duration=75,
        exam_url="https://example.com/english",
    )

    database.start_session(
        candidate_name="Candidate One",
        exam_token="active-lock-token",
        device_signature="device-active",
    )

    try:
        database.start_session(
            candidate_name="Candidate Two",
            exam_token="active-lock-token",
            device_signature="device-active",
        )
    except SessionConflictError:
        pass
    else:
        raise AssertionError("Duplicate active sessions should be blocked.")
