from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

# Fix PostgreSQL connection issues (2025 best practices)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Fix "server closed connection unexpectedly"
    pool_size=10,        # Connection pool size
    max_overflow=20,     # Max overflow connections
    pool_timeout=30,     # Connection timeout
    pool_recycle=1800    # Recycle connections every 30min
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()