from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///./marketplace.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def run_sqlite_migrations() -> None:
    """
    Lightweight SQLite migrations for demo environments without Alembic.
    Safely adds newly introduced columns if they don't exist.
    """
    if engine.url.get_backend_name() != "sqlite":
        return

    with engine.begin() as conn:
        agents_cols = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(agents)").fetchall()
        }
        if agents_cols:
            if "provider" not in agents_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE agents ADD COLUMN provider VARCHAR DEFAULT 'huggingface'"
                )
            if "framework" not in agents_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE agents ADD COLUMN framework VARCHAR DEFAULT 'custom'"
                )
            if "model_id" not in agents_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE agents ADD COLUMN model_id VARCHAR"
                )
            if "call_count" not in agents_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE agents ADD COLUMN call_count INTEGER DEFAULT 0"
                )

        logs_cols = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(query_logs)").fetchall()
        }
        if logs_cols:
            if "selected_agent_provider" not in logs_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE query_logs ADD COLUMN selected_agent_provider VARCHAR DEFAULT 'huggingface'"
                )
            if "selected_agent_framework" not in logs_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE query_logs ADD COLUMN selected_agent_framework VARCHAR DEFAULT 'custom'"
                )
            if "feedback_score" not in logs_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE query_logs ADD COLUMN feedback_score INTEGER"
                )

        # Enforce huggingface as default provider for existing demo data.
        conn.exec_driver_sql(
            "UPDATE agents SET provider = 'huggingface' WHERE provider IS NULL OR provider = '' OR provider = 'http'"
        )
        conn.exec_driver_sql(
            "UPDATE query_logs SET selected_agent_provider = 'huggingface' "
            "WHERE selected_agent_provider IS NULL OR selected_agent_provider = '' OR selected_agent_provider = 'http'"
        )

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
