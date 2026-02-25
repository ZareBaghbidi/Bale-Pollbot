from app.db.engine import get_engine
from app.db.models import Base

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
