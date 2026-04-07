SQLITE_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    duration INTEGER NOT NULL,
    settings TEXT NOT NULL DEFAULT '{}',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exam_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at TEXT,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    device_signature TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'submitted', 'cancelled', 'quit')),
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE RESTRICT,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('face', 'voice', 'tab_switch', 'fullscreen_exit')),
    count INTEGER NOT NULL DEFAULT 0,
    last_triggered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exam_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL UNIQUE,
    final_status TEXT NOT NULL CHECK (final_status IN ('submitted', 'cancelled', 'quit')),
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_exam_tokens_token
    ON exam_tokens(token);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_active_exam_device
    ON sessions(exam_id, device_signature)
    WHERE status = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS uq_violations_session_type
    ON violations(session_id, type);

CREATE INDEX IF NOT EXISTS ix_sessions_exam_id
    ON sessions(exam_id);

CREATE INDEX IF NOT EXISTS ix_sessions_device_signature
    ON sessions(device_signature);

CREATE INDEX IF NOT EXISTS ix_violations_session_id
    ON violations(session_id);

CREATE INDEX IF NOT EXISTS ix_exam_results_session_id
    ON exam_results(session_id);

CREATE INDEX IF NOT EXISTS ix_events_log_session_id
    ON events_log(session_id);
"""
