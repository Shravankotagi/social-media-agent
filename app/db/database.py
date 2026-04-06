"""
app/db/database.py — SQLAlchemy engine with SQLite fallback for cloud deployment.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool, QueuePool
from app.utils.logger import log

def _get_database_url() -> str:
    # Check for explicit DATABASE_URL first (cloud deployment)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    # Fall back to MySQL config
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "agent_user")
    password = os.getenv("MYSQL_PASSWORD", "agent_password")
    database = os.getenv("MYSQL_DATABASE", "social_agent")
    return f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"

DATABASE_URL = _get_database_url()

# SQLite needs special config
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_health() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.error("db.health_check_failed", error=str(exc))
        return False