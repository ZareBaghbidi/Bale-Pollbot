from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

DB_NAME = "pollbot.db"
DATABASE_URL = f"sqlite:///{DB_NAME}"


def get_engine() -> Engine:
    return create_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )
