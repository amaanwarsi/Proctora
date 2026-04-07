-- Proctora MySQL 8 migration script
-- This migration adds the normalized exam/session schema without deleting legacy tables.
-- Legacy tables such as students/tests/detections are intentionally preserved for compatibility.

START TRANSACTION;

CREATE TABLE IF NOT EXISTS exams (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    duration INT NOT NULL,
    settings JSON NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS exam_tokens (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    exam_id BIGINT UNSIGNED NOT NULL,
    token VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NULL DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_exam_tokens_token (token),
    KEY ix_exam_tokens_exam_id (exam_id),
    CONSTRAINT fk_exam_tokens_exam
        FOREIGN KEY (exam_id) REFERENCES exams(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS candidates (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sessions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    candidate_id BIGINT UNSIGNED NOT NULL,
    exam_id BIGINT UNSIGNED NOT NULL,
    device_signature VARCHAR(255) NOT NULL,
    status ENUM('active', 'submitted', 'cancelled', 'quit') NOT NULL DEFAULT 'active',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL DEFAULT NULL,
    active_device_signature VARCHAR(255)
        GENERATED ALWAYS AS (
            CASE WHEN status = 'active' THEN device_signature ELSE NULL END
        ) STORED,
    PRIMARY KEY (id),
    UNIQUE KEY uq_sessions_active_exam_device (exam_id, active_device_signature),
    KEY ix_sessions_exam_id (exam_id),
    KEY ix_sessions_device_signature (device_signature),
    KEY ix_sessions_candidate_id (candidate_id),
    CONSTRAINT fk_sessions_candidate
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_sessions_exam
        FOREIGN KEY (exam_id) REFERENCES exams(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS violations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_id BIGINT UNSIGNED NOT NULL,
    type ENUM('face', 'voice', 'tab_switch', 'fullscreen_exit') NOT NULL,
    count INT NOT NULL DEFAULT 0,
    last_triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_violations_session_type (session_id, type),
    KEY ix_violations_session_id (session_id),
    CONSTRAINT fk_violations_session
        FOREIGN KEY (session_id) REFERENCES sessions(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS exam_results (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_id BIGINT UNSIGNED NOT NULL,
    final_status ENUM('submitted', 'cancelled', 'quit') NOT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_exam_results_session_id (session_id),
    KEY ix_exam_results_session_id (session_id),
    CONSTRAINT fk_exam_results_session
        FOREIGN KEY (session_id) REFERENCES sessions(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS events_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_id BIGINT UNSIGNED NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_events_log_session_id (session_id),
    CONSTRAINT fk_events_log_session
        FOREIGN KEY (session_id) REFERENCES sessions(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

COMMIT;

-- Notes:
-- 1. Token-based access should always resolve exams through exam_tokens.token.
-- 2. Device reuse after completion is enforced in backend query logic to avoid breaking legacy session data.
-- 3. Violation counts should be updated with INSERT ... ON DUPLICATE KEY UPDATE using uq_violations_session_type.
-- 4. Legacy backfill from students/tests should be run separately after verifying those tables exist.
