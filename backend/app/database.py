"""
Database configuration and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,        # Stable pool size (default was 5)
    max_overflow=20,     # Allow burst up to 40 connections (default was 10)
    pool_recycle=3600,   # Recycle connections after 1h to avoid stale handles
    pool_timeout=30,     # Fail fast if pool exhausted (default 30s, kept explicit)
    echo=settings.DEBUG
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session.

    P7: Added explicit rollback on unhandled exceptions to prevent
    partial commits from corrupting data. On success, the session
    closes normally (routes handle their own commits).
    On exception, any uncommitted changes are rolled back before close.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
