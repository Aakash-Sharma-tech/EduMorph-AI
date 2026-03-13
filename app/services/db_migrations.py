from sqlalchemy import inspect, text


def _add_column_if_missing(db, table_name: str, column_name: str, column_sql: str):
    inspector = inspect(db.engine)
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    if column_name in cols:
        return False
    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))
    db.session.commit()
    return True


def ensure_schema(db):
    """
    Minimal SQLAlchemy-backed schema migration for this MVP.
    Flask-SQLAlchemy's create_all() won't add new columns to existing tables,
    so we patch older SQLite databases forward safely at startup.
    """
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    # If tables don't exist yet, create_all() will handle them.
    if "quiz" in tables:
        _add_column_if_missing(db, "quiz", "code", "code VARCHAR(8)")
        _add_column_if_missing(db, "quiz", "is_active", "is_active BOOLEAN DEFAULT 0")
        _add_column_if_missing(db, "quiz", "source_type", "source_type VARCHAR(32)")
        _add_column_if_missing(db, "quiz", "topic", "topic VARCHAR(128)")
        _add_column_if_missing(db, "quiz", "difficulty", "difficulty VARCHAR(32)")
        _add_column_if_missing(db, "quiz", "num_questions", "num_questions INTEGER")
        _add_column_if_missing(db, "quiz", "question_types", "question_types VARCHAR(128)")

        # Ensure we have a unique index for code (SQLite won't enforce via ALTER TABLE).
        db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_quiz_code ON quiz (code)"))
        db.session.commit()

    if "user" in tables:
        _add_column_if_missing(db, "user", "current_streak", "current_streak INTEGER DEFAULT 0")
        _add_column_if_missing(db, "user", "longest_streak", "longest_streak INTEGER DEFAULT 0")
        _add_column_if_missing(db, "user", "last_active_date", "last_active_date DATE")
        
        # Leaderboard & Ranking System
        _add_column_if_missing(db, "user", "total_tests_taken", "total_tests_taken INTEGER DEFAULT 0")
        _add_column_if_missing(db, "user", "total_marks_scored", "total_marks_scored INTEGER DEFAULT 0")
        _add_column_if_missing(db, "user", "average_score", "average_score FLOAT DEFAULT 0.0")
        _add_column_if_missing(db, "user", "calculated_rank", "calculated_rank INTEGER")

    if "quiz_result" in tables:
        _add_column_if_missing(db, "quiz_result", "time_taken_seconds", "time_taken_seconds INTEGER")
        _add_column_if_missing(db, "quiz_result", "violation_count", "violation_count INTEGER DEFAULT 0")
        _add_column_if_missing(db, "quiz_result", "violation_logs", "violation_logs TEXT")

    # StudyPlan, AnalyzeQuizAttempt, BookRecommendation tables are new; create_all will create them if missing.
