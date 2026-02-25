from sqlalchemy.orm import sessionmaker
from app.db.engine import get_engine

SessionLocal = sessionmaker(
    bind=get_engine(), autoflush=False, autocommit=False, future=True)
