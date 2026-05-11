import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = os.environ.get("DB_PATH", "./skillhub.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Idempotent: add new columns without dropping existing data."""
    new_cols = [
        ("source_url",      "TEXT"),
        ("execute_url",     "TEXT"),
        ("last_synced_at",  "DATETIME"),
    ]
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(skills)"))}
        for col, col_type in new_cols:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE skills ADD COLUMN {col} {col_type}"))
        conn.commit()
