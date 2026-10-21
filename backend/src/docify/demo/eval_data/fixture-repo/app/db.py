from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_session():
    """FastAPI dependency that yields a database session and always closes it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
