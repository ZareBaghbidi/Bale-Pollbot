from app.db.engine import get_engine
from app.db.models import Base
from sqlalchemy import inspect, text

from .users import *
from .classes import *
from .polls import *
from .questions import *
from .tasks import *
from .votes import *
from .invoices import *
from .payments import *

__all__ = (
    users.__all__ +
    classes.__all__ +
    polls.__all__ +
    questions.__all__ +
    tasks.__all__ +
    votes.__all__ +
    invoices.__all__ +
    payments.__all__
)


def init_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    # create_all does not add columns to an existing SQLite database.
    invoice_columns = {
        column["name"] for column in inspect(engine).get_columns("invoices")
    }
    with engine.begin() as connection:
        if "reminder_interval_days" not in invoice_columns:
            connection.execute(text(
                "ALTER TABLE invoices ADD COLUMN reminder_interval_days INTEGER"))
        if "next_reminder_at" not in invoice_columns:
            connection.execute(text(
                "ALTER TABLE invoices ADD COLUMN next_reminder_at INTEGER"))
