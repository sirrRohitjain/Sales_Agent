import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Supabase URL adaptation for SQLAlchemy + psycopg3
raw_url = os.getenv("SUPABASE_DB_URL", os.getenv("DATABASE_URL"))
if raw_url and raw_url.startswith("postgresql://"):
    DATABASE_URL = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    DATABASE_URL = raw_url

# ── Engine with connection pooling ─────────────────────────────────
try:
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=10,           # max persistent connections
        max_overflow=20,        # extra connections when pool is full
        pool_pre_ping=True,     # test connection before using
        pool_recycle=300,       # recycle connections every 5 min
        echo=False,             # set True to log all SQL queries
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.warning(f"⚠️  Database connection failed: {e}. Running in demo mode.")
    engine = None
    SessionLocal = None

@contextmanager
def get_db() -> Session:
    """
    Context manager for DB sessions.
    Usage:
        with get_db() as db:
            db.execute(text("SELECT 1"))
    """
    if SessionLocal is None:
        raise RuntimeError("Database not connected. Set DATABASE_URL or SUPABASE_DB_URL.")
    
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"DB error: {e}")
        raise
    finally:
        db.close()

def test_connection():
    """Test DB connectivity on startup."""
    if engine is None:
        logger.warning("⚠️  Database not configured")
        return False
    
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL (Supabase) connected successfully")
        return True
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        return False
    
if __name__ == "__main__":
    if test_connection():
        print("Database connection successful!")  

    
